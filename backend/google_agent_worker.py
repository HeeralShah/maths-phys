"""Opt-in boundary for a custom Google ADK agent on Agent Runtime.

This module is intentionally not a durable worker.  It does not import the
Google SDK, inspect credentials, open a database, or make a network request at
import time.  The application's durable worker may inject this adapter after it
has claimed a user-requested job and reserved that job's local cost budget.

The deployed resource is our ADK application (a ``ReasoningEngine``), not the
prebuilt Gemini API Antigravity managed agent.  Complete chapter pages cross the
boundary as a native PDF rather than OCR text or screenshots.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILLS_ROOT = REPO_ROOT / "agent-skills" / ".claude" / "skills"
MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 1_000
ARTIFACT_TAG = "study-artifact"
RESOURCE_RE = re.compile(
    r"^projects/(?P<project>[^/]+)/locations/(?P<location>[^/]+)/reasoningEngines/(?P<id>[^/]+)$"
)
SKILL_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")


class ArtifactError(ValueError):
    """The deployed agent did not return a valid provider-neutral artifact."""


def _flag(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _positive_int(value: Any, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if parsed < 1:
        raise RuntimeError(f"{name} must be positive")
    return parsed


def _positive_float(value: Any, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} must be numeric") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise RuntimeError(f"{name} must be finite and positive")
    return parsed


def announced_non_global_prices(
    model: str, today: dt.date | None = None
) -> tuple[float, float, float]:
    """Return documented input/output/cached USD rates per million tokens.

    These are planning defaults from the published schedule reviewed on
    2026-11-01.  Every rate is environment-overridable because model names and
    preview prices change.  Unknown models deliberately use the higher rate.
    """

    today = today or dt.date.today()
    normalized = model.strip().casefold()
    if "argon" in normalized:
        return (4.40, 22.0, 0.22) if today >= dt.date(2026, 12, 1) else (2.20, 11.0, 0.11)
    if "3.8" in normalized and "flash" in normalized:
        return (1.65, 8.25, 0.165) if today >= dt.date(2027, 1, 1) else (0.825, 4.125, 0.0825)
    return 4.40, 22.0, 0.44


@dataclass(frozen=True)
class GoogleAgentRuntimeSettings:
    """Explicit configuration for one offline and optional research runtime."""

    project_id: str
    location: str
    runtime_resource_name: str
    model: str
    max_llm_calls: int
    max_total_tokens: int
    job_budget_usd: float
    total_budget_usd: float
    research_runtime_resource_name: str | None = None
    timeout_seconds: float = 540.0
    input_usd_per_million: float | None = None
    output_usd_per_million: float | None = None
    cached_usd_per_million: float | None = None
    search_usd_each: float = 0.014
    runtime_vcpus: float = 1.0
    runtime_memory_gib: float = 2.0
    runtime_vcpu_hour_usd: float = 0.085
    runtime_gib_hour_usd: float = 0.009

    def __post_init__(self) -> None:
        announced = announced_non_global_prices(self.model)
        for name, default in zip(
            ("input_usd_per_million", "output_usd_per_million", "cached_usd_per_million"),
            announced,
        ):
            if getattr(self, name) is None:
                object.__setattr__(self, name, default)
        for name in ("project_id", "location", "runtime_resource_name", "model"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")
        match = RESOURCE_RE.fullmatch(self.runtime_resource_name)
        if not match or match.group("project") != self.project_id or match.group("location") != self.location:
            raise ValueError("offline runtime resource must match the configured project and location")
        if self.research_runtime_resource_name:
            research = RESOURCE_RE.fullmatch(self.research_runtime_resource_name)
            if not research or research.group("project") != self.project_id or research.group("location") != self.location:
                raise ValueError("research runtime resource must match the configured project and location")
            if self.research_runtime_resource_name == self.runtime_resource_name:
                raise ValueError("offline and research runtime resources must be different")
        if self.max_llm_calls < 1 or self.max_total_tokens < 1:
            raise ValueError("max_llm_calls and max_total_tokens must be positive")
        numeric = (
            self.job_budget_usd,
            self.total_budget_usd,
            self.timeout_seconds,
            self.input_usd_per_million,
            self.output_usd_per_million,
            self.cached_usd_per_million,
            self.search_usd_each,
            self.runtime_vcpus,
            self.runtime_memory_gib,
            self.runtime_vcpu_hour_usd,
            self.runtime_gib_hour_usd,
        )
        if any(not math.isfinite(value) or value < 0 for value in numeric):
            raise ValueError("budgets, rates, resources, and timeouts must be finite and non-negative")
        if self.job_budget_usd <= 0 or self.total_budget_usd <= 0:
            raise ValueError("job and total budgets must be positive")
        if self.job_budget_usd > self.total_budget_usd:
            raise ValueError("job budget cannot exceed total budget")
        if self.timeout_seconds <= 0 or self.runtime_vcpus <= 0 or self.runtime_memory_gib <= 0:
            raise ValueError("timeout and runtime sizing must be positive")
        if self.timeout_seconds >= 600:
            raise ValueError(
                "streaming timeout must stay below Agent Runtime's 600-second limit; "
                "use an explicitly designed long-running query transport instead"
            )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "GoogleAgentRuntimeSettings":
        env = os.environ if environ is None else environ
        if not _flag(env.get("MATHSPHYS_AGENT_ENABLED")):
            raise RuntimeError("agent execution is disabled; enable it only for an explicit paid action")
        if str(env.get("MATHSPHYS_AGENT_PROVIDER", "")).strip().casefold() != "google-adk":
            raise RuntimeError("MATHSPHYS_AGENT_PROVIDER must explicitly be 'google-adk'")
        project = str(env.get("GOOGLE_CLOUD_PROJECT", "")).strip()
        location = str(env.get("GOOGLE_CLOUD_LOCATION", "")).strip()
        resource = str(env.get("MATHSPHYS_GOOGLE_RUNTIME", "")).strip()
        model = str(env.get("MATHSPHYS_AGENT_MODEL", "")).strip()
        if not all((project, location, resource, model)):
            raise RuntimeError(
                "GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, MATHSPHYS_GOOGLE_RUNTIME, "
                "and MATHSPHYS_AGENT_MODEL are required"
            )
        default_input, default_output, default_cached = announced_non_global_prices(model)
        return cls(
            project_id=project,
            location=location,
            runtime_resource_name=resource,
            research_runtime_resource_name=(str(env.get("MATHSPHYS_GOOGLE_RESEARCH_RUNTIME", "")).strip() or None),
            model=model,
            max_llm_calls=_positive_int(env.get("MATHSPHYS_AGENT_MAX_LLM_CALLS"), "MATHSPHYS_AGENT_MAX_LLM_CALLS"),
            max_total_tokens=_positive_int(env.get("MATHSPHYS_AGENT_MAX_TOTAL_TOKENS"), "MATHSPHYS_AGENT_MAX_TOTAL_TOKENS"),
            job_budget_usd=_positive_float(env.get("MATHSPHYS_AGENT_JOB_BUDGET_USD"), "MATHSPHYS_AGENT_JOB_BUDGET_USD"),
            total_budget_usd=_positive_float(env.get("MATHSPHYS_AGENT_TOTAL_BUDGET_USD"), "MATHSPHYS_AGENT_TOTAL_BUDGET_USD"),
            timeout_seconds=_positive_float(env.get("MATHSPHYS_AGENT_TIMEOUT_SECONDS", "540"), "MATHSPHYS_AGENT_TIMEOUT_SECONDS"),
            input_usd_per_million=float(env.get("MATHSPHYS_GOOGLE_INPUT_USD_PER_MILLION", default_input)),
            output_usd_per_million=float(env.get("MATHSPHYS_GOOGLE_OUTPUT_USD_PER_MILLION", default_output)),
            cached_usd_per_million=float(env.get("MATHSPHYS_GOOGLE_CACHED_USD_PER_MILLION", default_cached)),
        )

    def budget_for(self, job: Mapping[str, Any]) -> float:
        payload = _job_payload(job)
        requested = payload.get("budget_usd", self.job_budget_usd)
        try:
            budget = float(requested)
        except (TypeError, ValueError) as exc:
            raise ValueError("job budget_usd must be numeric") from exc
        if (
            not math.isfinite(budget)
            or budget <= 0
            or budget > self.job_budget_usd
            or budget > self.total_budget_usd
        ):
            raise ValueError("job budget_usd must fit configured per-job and total limits")
        return budget

    def runtime_cost(self, elapsed_seconds: float) -> float:
        hours = max(0.0, elapsed_seconds) / 3600
        return hours * (
            self.runtime_vcpus * self.runtime_vcpu_hour_usd
            + self.runtime_memory_gib * self.runtime_gib_hour_usd
        )

    def token_cap_for(self, budget_usd: float, research: bool) -> int:
        """Reserve worst-case output pricing and runtime before sending a job.

        The deployed ADK callback, not this request field, must enforce this cap
        across all model and sub-agent calls.  This calculation makes the
        envelope conservative; the durable worker remains the hard local gate.
        """

        runtime_reserve = self.runtime_cost(self.timeout_seconds)
        search_reserve = self.search_usd_each * 4 if research else 0.0
        available = budget_usd - runtime_reserve - search_reserve
        if available <= 0:
            raise ValueError("job budget is smaller than its runtime/tool reserve")
        worst_rate = max(float(self.input_usd_per_million), float(self.output_usd_per_million))
        affordable = int(available * 1_000_000 / worst_rate)
        cap = min(self.max_total_tokens, affordable)
        if cap < 1_000:
            raise ValueError("job budget cannot fund the minimum 1,000-token managed run")
        return cap


@dataclass(frozen=True)
class NativePdfChapter:
    data: bytes
    physical_pages: tuple[int, ...]
    source_sha256: str
    original_page_count: int


@dataclass(frozen=True)
class RuntimeInvocation:
    resource_name: str
    user_id: str
    message: Mapping[str, Any]
    run_config: Mapping[str, Any]


@dataclass(frozen=True)
class RuntimeResult:
    events: tuple[Any, ...]
    elapsed_seconds: float


class RuntimeTransport(Protocol):
    def invoke(self, invocation: RuntimeInvocation, timeout_seconds: float) -> RuntimeResult: ...


class AgentPlatformTransport:
    """Lazy transport for an already deployed ADK ``ReasoningEngine``."""

    def __init__(
        self,
        project_id: str,
        location: str,
        *,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self._client_factory = client_factory

    def _client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        try:
            import agentplatform
        except ImportError as exc:
            raise RuntimeError(
                "Install backend/requirements-google.txt before invoking a deployed Google ADK agent"
            ) from exc
        return agentplatform.Client(project=self.project_id, location=self.location)

    def invoke(self, invocation: RuntimeInvocation, timeout_seconds: float) -> RuntimeResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("synchronous AgentPlatformTransport cannot run inside an active event loop")

        client = self._client()
        runtime = client.runtimes.get(name=invocation.resource_name)

        async def collect() -> tuple[Any, ...]:
            events: list[Any] = []
            stream = runtime.async_stream_query(
                user_id=invocation.user_id,
                message=dict(invocation.message),
                run_config=dict(invocation.run_config),
            )
            async for event in stream:
                events.append(event)
            return tuple(events)

        started = time.monotonic()
        events = asyncio.run(asyncio.wait_for(collect(), timeout=timeout_seconds))
        return RuntimeResult(events=events, elapsed_seconds=time.monotonic() - started)


def _job_payload(job: Mapping[str, Any]) -> dict[str, Any]:
    value = job.get("payload", {})
    if isinstance(value, str):
        try:
            value = json.loads(value or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("job payload is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise ValueError("job payload must be an object")
    return dict(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pages_from_revision(context: Mapping[str, Any]) -> list[int]:
    pages: list[int] = []
    revision = context.get("revision")
    refs = revision.get("source_refs", []) if isinstance(revision, Mapping) else []
    for ref in refs if isinstance(refs, Sequence) else []:
        if not isinstance(ref, Mapping):
            continue
        candidate = ref.get("page", ref.get("page_number"))
        if candidate is not None:
            try:
                pages.append(int(candidate))
            except (TypeError, ValueError):
                continue
    return pages


def build_native_pdf_chapter(job: Mapping[str, Any], context: Mapping[str, Any]) -> NativePdfChapter:
    """Verify and copy selected physical pages into an in-memory native PDF."""

    source = context.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("prepare/revise context must contain its registered source")
    metadata = source.get("metadata")
    local_file = metadata.get("local_file") if isinstance(metadata, Mapping) else None
    if not isinstance(local_file, Mapping) or not local_file.get("path"):
        raise ValueError("source has no registered local PDF")
    path = Path(str(local_file["path"])).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.casefold() != ".pdf":
        raise ValueError("registered PDF is unavailable")
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError("registered file does not have a PDF signature")
    digest = _sha256_file(path)
    expected = str(local_file.get("sha256", "")).strip()
    if expected and digest != expected:
        raise ValueError("registered PDF changed since it was added")

    payload = _job_payload(job)
    requested = payload.get("pages")
    if requested is None and str(job.get("job_type")) == "revise":
        requested = _pages_from_revision(context)
    if requested is not None and (
        not isinstance(requested, list) or any(isinstance(item, bool) for item in requested)
    ):
        raise ValueError("pages must be a list of physical one-based page numbers")

    try:
        registered_page_count = int(local_file.get("page_count", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("registered PDF page count is invalid") from exc
    if registered_page_count < 1:
        raise ValueError("registered PDF page count is missing")
    if requested:
        try:
            pages = tuple(sorted({int(item) for item in requested}))
        except (TypeError, ValueError) as exc:
            raise ValueError("pages must contain integers") from exc
    elif payload.get("whole_document") is True:
        pages = tuple(range(1, registered_page_count + 1))
    else:
        raise ValueError("chapter preparation must explicitly name pages or whole_document=true")
    if not pages or pages[0] < 1 or pages[-1] > registered_page_count:
        raise ValueError(f"selected pages must be between 1 and {registered_page_count}")
    if len(pages) > MAX_PDF_PAGES:
        raise ValueError(f"native PDF input cannot exceed {MAX_PDF_PAGES} selected pages")

    if pages == tuple(range(1, registered_page_count + 1)):
        data = path.read_bytes()
        if len(data) > MAX_PDF_BYTES:
            raise ValueError(f"native PDF input cannot exceed {MAX_PDF_BYTES // (1024 * 1024)} MB")
        return NativePdfChapter(data, pages, digest, registered_page_count)

    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to create a native selected-page chapter PDF") from exc

    source_doc = fitz.open(path)
    try:
        page_count = source_doc.page_count
        if page_count != registered_page_count:
            raise ValueError("registered PDF page count no longer matches the source")
        chapter = fitz.open()
        try:
            for page_number in pages:
                chapter.insert_pdf(source_doc, from_page=page_number - 1, to_page=page_number - 1)
            data = chapter.tobytes(garbage=4, deflate=True)
        finally:
            chapter.close()
    finally:
        source_doc.close()

    if len(data) > MAX_PDF_BYTES:
        raise ValueError(f"native PDF input cannot exceed {MAX_PDF_BYTES // (1024 * 1024)} MB")
    return NativePdfChapter(data, pages, digest, page_count)


def load_skills(skill_names: Sequence[str], root: Path = DEFAULT_SKILLS_ROOT) -> dict[str, str]:
    """Load only explicitly named, contained SKILL.md files for the task envelope."""

    base = root.resolve(strict=True)
    result: dict[str, str] = {}
    total = 0
    for name in dict.fromkeys(skill_names):
        if not SKILL_RE.fullmatch(name):
            raise ValueError(f"invalid skill name: {name!r}")
        path = (base / name / "SKILL.md").resolve(strict=True)
        path.relative_to(base)
        if not path.is_file():
            raise ValueError(f"skill is not a file: {name}")
        content = path.read_text(encoding="utf-8")
        total += len(content.encode("utf-8"))
        if total > 2 * 1024 * 1024:
            raise ValueError("selected skill instructions exceed the 2 MB request limit")
        result[name] = content
    return result


def _sanitized(value: Any, parent_key: str | None = None) -> Any:
    """Remove machine-local PDF paths and rendered images from cloud context."""

    if isinstance(value, Mapping):
        if parent_key == "local_file":
            return {key: _sanitized(value[key], key) for key in ("sha256", "page_count") if key in value}
        output: dict[str, Any] = {}
        for key, child in value.items():
            if key in {"image_base64", "pdf_bytes"}:
                continue
            output[str(key)] = _sanitized(child, str(key))
        return output
    if isinstance(value, (list, tuple)):
        return [_sanitized(item, parent_key) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_task_envelope(
    job: Mapping[str, Any],
    context: Mapping[str, Any],
    skills: Mapping[str, str],
    chapter: NativePdfChapter | None,
    *,
    research: bool,
    max_total_tokens: int,
    max_llm_calls: int,
    budget_usd: float,
) -> dict[str, Any]:
    payload = _job_payload(job)
    envelope: dict[str, Any] = {
        "contract": "maths-phys-study-agent/v1",
        "job": {
            "id": str(job.get("id", "")),
            "type": str(job.get("job_type", "")),
            "entity_id": str(job.get("entity_id", "")),
            "payload": _sanitized(payload),
        },
        "context": _sanitized(context),
        "skills": dict(skills),
        "controls": {
            "research_enabled": research,
            "max_total_tokens": max_total_tokens,
            "max_llm_calls": max_llm_calls,
            "reserved_budget_usd": budget_usd,
            "publish_partial_output": False,
        },
        "requirements": [
            "Treat the attached PDF as the source of truth and preserve source order and notation.",
            "Return one complete provider-neutral JSON artifact only after internal validation.",
            "Keep source content separate from anchored annotations and proposed corrections.",
            "Do not publish or mutate durable study state; the local application validates and commits output.",
        ],
    }
    if chapter is not None:
        envelope["chapter"] = {
            "mime_type": "application/pdf",
            "physical_pages": list(chapter.physical_pages),
            "source_sha256": chapter.source_sha256,
            "original_page_count": chapter.original_page_count,
        }
    if research:
        envelope["research"] = {"allowed_domains": payload.get("research_domains", [])}
    return envelope


def build_runtime_message(chapter: NativePdfChapter | None, envelope: Mapping[str, Any]) -> dict[str, Any]:
    parts: list[dict[str, Any]] = []
    if chapter is not None:
        parts.append({"inline_data": {"mime_type": "application/pdf", "data": chapter.data}})
    parts.append({"text": json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))})
    return {"role": "user", "parts": parts}


def _to_plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _to_plain(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(child) for child in value]
    if hasattr(value, "model_dump"):
        return _to_plain(value.model_dump(exclude_none=True))
    if hasattr(value, "to_dict"):
        return _to_plain(value.to_dict())
    if hasattr(value, "__dict__"):
        return _to_plain({key: child for key, child in vars(value).items() if not key.startswith("_")})
    return str(value)


def _mapping_lookup(value: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in value:
            return value[name]
    return default


def _find_usage(value: Any) -> Mapping[str, Any] | None:
    plain = _to_plain(value)
    if isinstance(plain, Mapping):
        for key in ("usage_metadata", "usageMetadata", "usage"):
            candidate = plain.get(key)
            if isinstance(candidate, Mapping) and any("token" in str(name).casefold() for name in candidate):
                return candidate
        for child in plain.values():
            found = _find_usage(child)
            if found is not None:
                return found
    elif isinstance(plain, list):
        for child in plain:
            found = _find_usage(child)
            if found is not None:
                return found
    return None


def _count_searches(value: Any) -> int:
    plain = _to_plain(value)
    if isinstance(plain, Mapping):
        total = 0
        for key, child in plain.items():
            if key in {"web_search_queries", "webSearchQueries"} and isinstance(child, list):
                total += len(child)
            else:
                total += _count_searches(child)
        return total
    if isinstance(plain, list):
        return sum(_count_searches(child) for child in plain)
    return 0


def _integer(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class GoogleUsage:
    input_tokens: int
    output_tokens: int
    thought_tokens: int
    cached_tokens: int
    total_tokens: int
    search_requests: int
    elapsed_seconds: float
    estimated_cost_usd: float | None
    raw_usage: tuple[Mapping[str, Any], ...]


def capture_usage(
    result: RuntimeResult, settings: GoogleAgentRuntimeSettings
) -> GoogleUsage:
    records = tuple(record for event in result.events if (record := _find_usage(event)) is not None)
    input_tokens = output_tokens = thought_tokens = cached_tokens = total_tokens = 0
    for record in records:
        input_tokens += _integer(
            _mapping_lookup(record, "prompt_token_count", "promptTokenCount", "input_tokens", "inputTokens")
        )
        output_tokens += _integer(
            _mapping_lookup(record, "candidates_token_count", "candidatesTokenCount", "output_tokens", "outputTokens")
        )
        thought_tokens += _integer(
            _mapping_lookup(record, "thoughts_token_count", "thoughtsTokenCount", "thought_tokens", "thoughtTokens")
        )
        cached_tokens += _integer(
            _mapping_lookup(record, "cached_content_token_count", "cachedContentTokenCount", "cached_tokens", "cachedTokens")
        )
        total_tokens += _integer(_mapping_lookup(record, "total_token_count", "totalTokenCount", "total_tokens", "totalTokens"))
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens + thought_tokens
    searches = sum(_count_searches(event) for event in result.events)
    if records and (input_tokens or output_tokens or thought_tokens or cached_tokens or total_tokens):
        uncached_input = max(0, input_tokens - cached_tokens)
        estimated = (
            uncached_input * settings.input_usd_per_million
            + cached_tokens * settings.cached_usd_per_million
            + (output_tokens + thought_tokens) * settings.output_usd_per_million
        ) / 1_000_000
        estimated += searches * settings.search_usd_each
        estimated += settings.runtime_cost(result.elapsed_seconds)
    else:
        estimated = None
    return GoogleUsage(
        input_tokens,
        output_tokens,
        thought_tokens,
        cached_tokens,
        total_tokens,
        searches,
        result.elapsed_seconds,
        estimated,
        records,
    )


def _candidate_texts(events: Sequence[Any]) -> list[str]:
    values: list[str] = []

    def visit(value: Any) -> None:
        plain = _to_plain(value)
        if isinstance(plain, str):
            values.append(plain)
        elif isinstance(plain, Mapping):
            for key, child in plain.items():
                if key in {"text", "output_text", "outputText"} and isinstance(child, str):
                    values.append(child)
                elif not isinstance(child, (bytes, bytearray)):
                    visit(child)
        elif isinstance(plain, list):
            for child in plain:
                visit(child)

    for event in events:
        visit(event)
    return values


def _json_objects(text: str) -> list[dict[str, Any]]:
    if len(text) > 20_000_000:
        raise ArtifactError("agent output is too large to inspect safely")
    chunks = [text]
    chunks[:0] = re.findall(rf"<{ARTIFACT_TAG}>\s*(.*?)\s*</{ARTIFACT_TAG}>", text, re.I | re.S)
    chunks[:0] = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, re.I | re.S)
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    for chunk in chunks:
        try:
            parsed = json.loads(chunk.strip())
            if isinstance(parsed, dict):
                objects.append(parsed)
        except json.JSONDecodeError:
            pass
        for match in re.finditer(r"\{", chunk):
            try:
                parsed, _ = decoder.raw_decode(chunk[match.start() :])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                objects.append(parsed)
    return objects


def extract_json_artifact(events: Sequence[Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for text in _candidate_texts(events):
        candidates.extend(_json_objects(text))
    if not candidates:
        raise ArtifactError("deployed ADK agent returned no JSON artifact")

    def score(item: Mapping[str, Any]) -> tuple[int, int]:
        keys = {"package", "plan", "complete", "edition", "files", "signoff_id"}
        wrapper = 10 if "package" in item or "plan" in item else 0
        return wrapper + len(keys.intersection(item)), len(json.dumps(item, ensure_ascii=False))

    return max(candidates, key=score)


def validate_json_artifact(
    artifact: dict[str, Any], job: Mapping[str, Any]
) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        raise ArtifactError("agent artifact must be a JSON object")
    job_type = str(job.get("job_type", ""))
    if job_type in {"prepare", "revise"}:
        package = artifact.get("package", artifact)
        if not isinstance(package, Mapping) or package.get("complete") is not True:
            raise ArtifactError("chapter artifact must explicitly declare complete=true")
        edition = package.get("edition")
        if not isinstance(edition, Mapping) or not isinstance(edition.get("units"), list) or not edition["units"]:
            raise ArtifactError("chapter artifact must contain one or more edition units")
    elif job_type == "signoff":
        plan = artifact.get("plan", artifact)
        if not isinstance(plan, Mapping) or not isinstance(plan.get("files"), list):
            raise ArtifactError("signoff artifact must contain a files list")
    else:
        raise ArtifactError("unsupported durable job type")
    return artifact


class GoogleAgentRuntimeAdapter:
    """Provider adapter with an injectable transport and no durable writes."""

    def __init__(
        self,
        settings: GoogleAgentRuntimeSettings,
        *,
        transport: RuntimeTransport | None = None,
        skills_root: Path = DEFAULT_SKILLS_ROOT,
        artifact_extractor: Callable[[Sequence[Any]], dict[str, Any]] = extract_json_artifact,
        artifact_validator: Callable[[dict[str, Any], Mapping[str, Any]], dict[str, Any]] = validate_json_artifact,
    ) -> None:
        self.settings = settings
        self.transport = transport or AgentPlatformTransport(settings.project_id, settings.location)
        self.skills_root = skills_root
        self._artifact_extractor = artifact_extractor
        self._artifact_validator = artifact_validator
        self.last_usage: GoogleUsage | None = None

    def _resource_for(self, payload: Mapping[str, Any]) -> tuple[str, bool]:
        research = payload.get("allow_web_research") is True
        if research:
            if not self.settings.research_runtime_resource_name:
                raise ValueError("web research requires a separately configured research runtime")
            domains = payload.get("research_domains", [])
            if not isinstance(domains, list) or any(not isinstance(item, str) or not item.strip() for item in domains):
                raise ValueError("research_domains must be a list of non-empty domain strings")
            return self.settings.research_runtime_resource_name, True
        return self.settings.runtime_resource_name, False

    def generate(
        self,
        job: dict[str, Any],
        context: dict[str, Any],
        tools: Any,
        skill_names: list[str],
        budget_usd: float,
    ) -> tuple[dict[str, Any], float | None]:
        """Invoke the deployed agent after the caller has reserved ``budget_usd``.

        ``tools`` is deliberately unused at this boundary.  Runtime tools/MCP
        are deployed with the ADK application; this adapter never exposes local
        filesystem callables over an ad-hoc network bridge.
        """

        del tools
        configured_budget = self.settings.budget_for(job)
        if not math.isfinite(budget_usd) or budget_usd <= 0 or budget_usd > configured_budget:
            raise ValueError("reserved budget must be positive and within the job's configured budget")
        payload = _job_payload(job)
        resource_name, research = self._resource_for(payload)
        token_cap = self.settings.token_cap_for(budget_usd, research)
        chapter = None
        if str(job.get("job_type")) in {"prepare", "revise"}:
            chapter = build_native_pdf_chapter(job, context)
        skills = load_skills(skill_names, self.skills_root)
        envelope = build_task_envelope(
            job,
            context,
            skills,
            chapter,
            research=research,
            max_total_tokens=token_cap,
            max_llm_calls=self.settings.max_llm_calls,
            budget_usd=budget_usd,
        )
        invocation = RuntimeInvocation(
            resource_name=resource_name,
            user_id=f"maths-phys-job-{str(job.get('id', 'unknown'))}",
            message=build_runtime_message(chapter, envelope),
            run_config={"max_llm_calls": self.settings.max_llm_calls},
        )
        result = self.transport.invoke(invocation, self.settings.timeout_seconds)
        usage = capture_usage(result, self.settings)
        self.last_usage = usage
        if usage.total_tokens > token_cap:
            raise RuntimeError("deployed ADK agent exceeded the requested total-token envelope")
        artifact = self._artifact_extractor(result.events)
        return self._artifact_validator(artifact, job), usage.estimated_cost_usd


__all__ = [
    "AgentPlatformTransport",
    "ArtifactError",
    "GoogleAgentRuntimeAdapter",
    "GoogleAgentRuntimeSettings",
    "GoogleUsage",
    "NativePdfChapter",
    "RuntimeInvocation",
    "RuntimeResult",
    "RuntimeTransport",
    "build_native_pdf_chapter",
    "build_runtime_message",
    "capture_usage",
    "extract_json_artifact",
    "validate_json_artifact",
]
