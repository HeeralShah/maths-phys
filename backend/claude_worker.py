"""Opt-in Claude Agent SDK worker for durable prepare/revise/signoff jobs.

The module has no import-time SDK or network work. A worker must be started
explicitly and refuses to claim jobs until provider, model, key, and cost limits
are configured.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .store import Store
from .vault import read_note, search_notes


REPO_ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(os.environ.get("MATHSPHYS_VAULT", REPO_ROOT / "vault")).resolve()
SKILLS_ROOT = REPO_ROOT / "agent-skills"
SKILL_NAMES = {"prepare-edition", "expand-derivation", "proof-exposition",
               "source-only-problems", "research-map", "canonical-synthesis"}


@dataclass(frozen=True)
class WorkerSettings:
    provider: str
    model: str
    max_turns: int
    job_budget_usd: float
    total_budget_usd: float
    api_key: str
    web_enabled: bool = False

    def __post_init__(self):
        if self.provider != "claude" or not self.model.strip() or not self.api_key.strip():
            raise ValueError("worker requires explicit Claude provider, model, and API key")
        if self.max_turns < 1 or not math.isfinite(self.job_budget_usd) or not math.isfinite(self.total_budget_usd):
            raise ValueError("worker turns and cost budgets must be finite and positive")
        if self.job_budget_usd <= 0 or self.total_budget_usd <= 0 or self.job_budget_usd > self.total_budget_usd:
            raise ValueError("per-job USD budget must be positive and no greater than total USD budget")

    @classmethod
    def from_env(cls, environ=None) -> "WorkerSettings":
        env = os.environ if environ is None else environ
        if env.get("MATHSPHYS_AGENT_ENABLED", "").casefold() not in ("1", "true", "yes"):
            raise RuntimeError("Agent worker is disabled; set MATHSPHYS_AGENT_ENABLED=1 after explicit configuration")
        provider = env.get("MATHSPHYS_AGENT_PROVIDER", "").strip().casefold()
        if provider != "claude":
            raise RuntimeError("MATHSPHYS_AGENT_PROVIDER must explicitly be 'claude'")
        model = env.get("MATHSPHYS_AGENT_MODEL", "").strip()
        if not model:
            raise RuntimeError("MATHSPHYS_AGENT_MODEL must name the chosen model explicitly")
        try:
            turns = int(env.get("MATHSPHYS_AGENT_MAX_TURNS", ""))
            job_budget = float(env.get("MATHSPHYS_AGENT_JOB_BUDGET_USD", ""))
            total_budget = float(env.get("MATHSPHYS_AGENT_TOTAL_BUDGET_USD", ""))
        except ValueError as exc:
            raise RuntimeError("max turns and both USD budget settings must be numeric") from exc
        if turns < 1 or not math.isfinite(job_budget) or not math.isfinite(total_budget) or job_budget <= 0 or total_budget <= 0 or job_budget > total_budget:
            raise RuntimeError("configure positive max turns and per-job/total USD budgets; job budget must not exceed total")
        api_key = env.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required before a Claude worker can claim jobs")
        return cls(provider, model, turns, job_budget, total_budget, api_key,
                   env.get("MATHSPHYS_AGENT_WEB_ENABLED", "").casefold() in ("1", "true", "yes"))

    def budget_for(self, job: dict) -> float:
        payload = json.loads(job.get("payload") or "{}")
        requested = payload.get("budget_usd", self.job_budget_usd)
        try:
            requested = float(requested)
        except (TypeError, ValueError) as exc:
            raise ValueError("job budget_usd must be numeric") from exc
        if not math.isfinite(requested) or requested <= 0 or requested > self.job_budget_usd or requested > self.total_budget_usd:
            raise ValueError("job budget_usd must be positive and within configured per-job and total limits")
        return requested


class StudyTools:
    """Read-only tools bound to the registered source and canonical vault."""
    def __init__(self, store: Store, source_id: str, vault_root: Path = VAULT_ROOT):
        self.store, self.source_id, self.vault_root = store, source_id, vault_root
        self.accessed_pages: set[int] = set()

    def source_page(self, source_id: str, page_number: int) -> dict:
        if source_id != self.source_id:
            raise ValueError("tool access is limited to the job's registered source")
        page = self.store.source_page(source_id, page_number)
        self.accessed_pages.add(page_number)
        return {k: page[k] for k in ("source_id", "page_number", "page_count", "text", "image_base64", "image_mime")}

    def vault_search(self, query: str) -> list[dict]:
        return search_notes(self.vault_root, query, limit=25)

    def vault_note(self, relative_path: str) -> dict:
        return read_note(self.vault_root, relative_path)

    def atlas_target(self, relative_path: str) -> dict:
        path = Path(relative_path)
        if path.is_absolute() or not path.parts or path.parts[0] != "02 Atlas" or path.suffix.casefold() != ".md":
            raise ValueError("target must be a relative Markdown path under 02 Atlas")
        base = self.vault_root.resolve(strict=True)
        target = (base / path).resolve()
        resolved_rel = target.relative_to(base)
        if not resolved_rel.parts or resolved_rel.parts[0] != "02 Atlas":
            raise ValueError("target must resolve within vault/02 Atlas")
        if target.exists():
            if not target.is_file(): raise ValueError("target is not a Markdown file")
            raw = target.read_bytes()
            import hashlib
            return {"path": path.as_posix(), "exists": True,
                    "sha256": hashlib.sha256(raw).hexdigest(), "content": raw.decode("utf-8")}
        return {"path": path.as_posix(), "exists": False, "sha256": None, "content": None}


def _text_tool_result(value: Any) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}


def _page_tool_result(value: dict) -> dict:
    result = {"content": [{"type": "text", "text": json.dumps({k: v for k, v in value.items() if k != "image_base64"}, ensure_ascii=False)}]}
    if value.get("image_base64"):
        result["content"].append({"type": "image", "data": value["image_base64"], "mimeType": value["image_mime"]})
    return result


def _source_context(store: Store, job: dict) -> tuple[str, dict, list[dict]]:
    payload = json.loads(job.get("payload") or "{}")
    if job["job_type"] in ("prepare", "revise"):
        source_id = payload.get("source_id")
        if not source_id and job["job_type"] == "prepare": source_id = job["entity_id"]
        source = store.get_source(str(source_id)) if source_id else None
        if not source: raise ValueError("job must reference a registered source")
        context = {"source": source, "payload": payload, "learning_profile": store.get_learning_profile()}
        if job["job_type"] == "revise":
            unit_id, revision_id = payload.get("unit_id", job["entity_id"]), payload.get("revision_id")
            revision = store.read_revision(str(revision_id)) if revision_id else None
            if not revision or revision["unit_id"] != unit_id: raise ValueError("revise job must reference its saved unit revision")
            if store.read_edition(str(unit_id))["id"] != revision["id"]:
                raise ValueError("revise job revision is no longer current; save and resubmit clarification")
            context["revision"] = revision
            context["understanding"] = store.understanding(revision["id"])
            location = next(((sec["title"], unit["title"]) for sec in source["sections"] for unit in sec["units"] if unit["id"] == unit_id), None)
            if location is None: raise ValueError("revise job unit is missing from its registered source")
            context["section_title"], context["unit_title"] = location
        return str(source_id), context, []

    if job["job_type"] != "signoff": raise ValueError("unsupported job type")
    included = payload.get("included_units", [])
    if not included: raise ValueError("signoff has no currently checked material")
    section_id = job["entity_id"]
    source = next((s for s in store.sources() if any(sec["id"] == section_id for sec in (store.get_source(s["id"]) or {}).get("sections", []))), None)
    if not source: raise ValueError("signoff section has no source")
    section = next(sec for sec in store.get_source(source["id"])["sections"] if sec["id"] == section_id)
    signoff_id = payload.get("signoff_id")
    if not signoff_id: raise ValueError("signoff job is missing its signoff snapshot")
    revisions = []
    for item in included:
        revision = store.read_revision(item["revision_id"])
        if not revision or revision["unit_id"] != item["unit_id"] or store.understanding(revision["id"]) is not True:
            raise ValueError("signoff snapshot contains unchecked or missing material")
        revisions.append(revision)
    context = {"source": source, "section": section, "signoff_id": signoff_id,
               "learning_profile": store.get_learning_profile(),
               "included_units": revisions}
    return source["id"], context, revisions


def _skills_for(job: dict) -> list[str]:
    payload = json.loads(job.get("payload") or "{}")
    if job["job_type"] == "signoff": return ["canonical-synthesis"]
    selected = payload.get("skill_name")
    if selected is not None:
        if selected not in SKILL_NAMES - {"canonical-synthesis"}:
            raise ValueError("unsupported skill for prepare/revise job")
        return list(dict.fromkeys(["prepare-edition", selected]))
    return ["prepare-edition"]


def _prompt_for(job: dict, context: dict) -> str:
    payload = context.get("payload", {})
    if job["job_type"] == "prepare":
        pages = sorted(set(int(p) for p in payload.get("pages", [])))
        if not pages or pages[0] < 1: raise ValueError("prepare job must name one or more physical PDF pages")
        return ("Run the prepare-edition skill. Read every selected physical page in ascending order with read_source_page. "
                f"Requested pages: {pages}. Source: {context['source']['title']}. Return strict JSON with complete=true, "
            "edition.title, edition.units, and optional problems and graph `{nodes,edges}`. Every included graph node/edge must have page evidence and edge local keys must resolve. Preserve source content, ordering, and notation; "
                "give every unit source_refs with page-number locators. "
                f"Learner profile (for presentation only): {json.dumps(context.get('learning_profile',{}), ensure_ascii=False)}. "
                "Do not return until the entire requested range is covered.")
    if job["job_type"] == "revise":
        rev = context["revision"]
        return ("Run the prepare-edition skill for a clarification revision. The selected unit is the only target. "
                f"Section: {context['section_title']}\nUnit: {context['unit_title']}\nCurrent content:\n{rev['content']}\nClarification request:\n{payload.get('clarification','')}\n"
                f"Existing source refs: {json.dumps(rev.get('source_refs', []), ensure_ascii=False)}. "
                f"Learner profile (for presentation only): {json.dumps(context.get('learning_profile',{}), ensure_ascii=False)}. "
                "Read the cited pages with read_source_page before changing source claims. Return a complete=true package with exactly one unit matching the selected unit IDs; do not add adjacent units or unrelated notes. "
                "containing exactly this unit, retaining its section_title and unit_title and including source_refs.")
    revision_ids = [r["id"] for r in context["included_units"]]
    source_unit_map = {u["id"]: u["title"] for section in context["source"]["sections"] for u in section["units"]}
    units = [{"unit_id": r["unit_id"], "title": source_unit_map.get(r["unit_id"], ""),
              "revision_id": r["id"], "content": r["content"], "source_refs": r.get("source_refs", [])}
             for r in context["included_units"]]
    return ("Run canonical-synthesis using only the checked signoff snapshot below. Use search_vault and inspect_atlas_target "
            "before preparing changes. Return strict JSON with signoff_id, source_revision_ids, an idempotency_key, "
            "expected_hashes for every file and files [{path,content}]. Paths must be under 02 Atlas. Preserve manual intent. "
            f"Signoff id: {context['signoff_id']}\nIncluded checked revisions: {json.dumps(units, ensure_ascii=False)}\n"
            f"Allowed source_revision_ids: {json.dumps(revision_ids)}\n"
            f"Learner profile (for presentation only; do not infer source claims): {json.dumps(context.get('learning_profile',{}), ensure_ascii=False)}")


class ClaudeSDKAdapter:
    """Lazy optional SDK adapter. Merely importing this module never calls a model."""
    def __init__(self, store: Store, settings: WorkerSettings, vault_root: Path = VAULT_ROOT):
        self.store, self.settings, self.vault_root = store, settings, vault_root

    def generate(self, job: dict, context: dict, tools: StudyTools, skill_names: list[str], budget_usd: float) -> tuple[dict, float | None]:
        try:
            from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, create_sdk_mcp_server, query, tool
        except ImportError as exc:
            raise RuntimeError("Install the optional backend/requirements-claude.txt to run Claude jobs") from exc

        @tool("read_source_page", "Read and render a page from this job's registered source PDF", {"source_id": str, "page_number": int})
        async def read_source_page(args): return _page_tool_result(tools.source_page(args["source_id"], args["page_number"]))

        @tool("search_vault", "Search canonical Markdown notes within the Obsidian vault", {"query": str})
        async def search_vault(args): return _text_tool_result(tools.vault_search(args["query"]))

        @tool("read_vault_note", "Read a canonical Markdown note by contained vault-relative path", {"relative_path": str})
        async def read_vault_note(args): return _text_tool_result(tools.vault_note(args["relative_path"]))

        @tool("inspect_atlas_target", "Read the current content and SHA-256 of a proposed canonical Atlas note path", {"relative_path": str})
        async def inspect_atlas_target(args): return _text_tool_result(tools.atlas_target(args["relative_path"]))

        payload = json.loads(job.get("payload") or "{}")
        request_web = payload.get("allow_web_research") is True
        if request_web and not self.settings.web_enabled:
            raise ValueError("web research requires MATHSPHYS_AGENT_WEB_ENABLED=1 and an explicit per-job allow_web_research=true")
        server = create_sdk_mcp_server(name="study", version="1.0.0",
            tools=[read_source_page, search_vault, read_vault_note, inspect_atlas_target])
        allowed = ["mcp__study__read_source_page", "mcp__study__search_vault",
                   "mcp__study__read_vault_note", "mcp__study__inspect_atlas_target", "Skill"]
        sdk_tools = ["Skill"]
        if request_web:
            sdk_tools += ["WebSearch", "WebFetch"]
            allowed += ["WebSearch", "WebFetch"]
        options = ClaudeAgentOptions(
            model=self.settings.model,
            max_turns=self.settings.max_turns,
            max_budget_usd=budget_usd,
            cwd=str(REPO_ROOT),
            setting_sources=["project"],
            add_dirs=[str(SKILLS_ROOT)],
            skills=skill_names,
            tools=sdk_tools,
            allowed_tools=allowed,
            mcp_servers={"study": server},
            strict_mcp_config=True,
            env={"ANTHROPIC_API_KEY": self.settings.api_key},
        )
        prompt = _prompt_for(job, context)

        async def execute():
            parsed, estimated_cost = None, None
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    if message.subtype != "success":
                        raise RuntimeError(f"Claude run ended with {message.subtype}: {message.result or message.errors}")
                    estimated_cost = message.total_cost_usd
                    parsed = json.loads(message.result or "")
            if not isinstance(parsed, dict): raise RuntimeError("Claude returned no JSON result")
            return parsed, estimated_cost
        return asyncio.run(execute())


class BudgetLimitExceeded(ValueError): pass


def reserve_budget(store: Store, job_id: str, job_budget: float, total_limit: float) -> None:
    with store._connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS agent_budget_usage(
            job_id TEXT PRIMARY KEY REFERENCES jobs(id), reserved_usd REAL NOT NULL,
            actual_usd REAL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        if db.execute("SELECT 1 FROM agent_budget_usage WHERE job_id=?", (job_id,)).fetchone():
            raise ValueError("a budget has already been reserved for this job")
        row = db.execute("SELECT COALESCE(SUM(CASE WHEN status='reserved' THEN reserved_usd ELSE actual_usd END),0) FROM agent_budget_usage").fetchone()
        committed = float(row[0] or 0)
        if committed + job_budget > total_limit:
            raise BudgetLimitExceeded("configured lifetime agent budget would be exceeded")
        import datetime
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        db.execute("INSERT INTO agent_budget_usage VALUES(?,?,?,?,?,?)", (job_id, job_budget, None, "reserved", ts, ts))


def has_budget_capacity(store: Store, job_budget: float, total_limit: float) -> bool:
    with store._connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS agent_budget_usage(
            job_id TEXT PRIMARY KEY REFERENCES jobs(id), reserved_usd REAL NOT NULL,
            actual_usd REAL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        row = db.execute("SELECT COALESCE(SUM(CASE WHEN status='reserved' THEN reserved_usd ELSE actual_usd END),0) FROM agent_budget_usage").fetchone()
        return float(row[0] or 0) + job_budget <= total_limit


def settle_budget(store: Store, job_id: str, estimate: float | None) -> None:
    with store._connection() as db:
        row = db.execute("SELECT reserved_usd FROM agent_budget_usage WHERE job_id=? AND status='reserved'", (job_id,)).fetchone()
        if not row: return
        # Unknown SDK usage conservatively consumes the whole reservation.
        actual = max(float(estimate), 0.0) if estimate is not None and math.isfinite(float(estimate)) else row[0]
        import datetime
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        db.execute("UPDATE agent_budget_usage SET actual_usd=?,status='settled',updated_at=? WHERE job_id=?", (actual, ts, job_id))


class Worker:
    def __init__(self, store: Store, settings: WorkerSettings, adapter=None, vault_root: Path = VAULT_ROOT):
        self.store, self.settings, self.adapter, self.vault_root = store, settings, adapter, vault_root
        if self.adapter is None: self.adapter = ClaudeSDKAdapter(store, settings, vault_root)

    def run_once(self) -> dict | None:
        queued = self.store.jobs("queued")
        if not queued: return None
        recovery = self.store.get_edition_publication(f"job:{queued[0]['id']}") if queued[0]["job_type"] in ("prepare", "revise") else None
        if recovery:
            claimed = self.store.claim_job()
            if claimed and claimed["id"] == queued[0]["id"]:
                return self.store.complete_job(claimed["id"], {"kind": "edition", "edition": recovery["result"], "recovered_publication": True})
            if claimed:
                self.store.requeue_job(claimed["id"], "Publication recovery claim was superseded")
        # Check settings and lifetime headroom before claiming so blocked work stays queued.
        queued_budget = self.settings.budget_for(queued[0])
        if not has_budget_capacity(self.store, queued_budget, self.settings.total_budget_usd):
            return {"id": queued[0]["id"], "status": "blocked_budget", "error": "configured lifetime agent budget has no per-job headroom"}
        job = self.store.claim_job()
        if job is None: return None
        job_id = job["id"]
        try:
            budget = self.settings.budget_for(job)
            publication_key = f"job:{job_id}"
            if job["job_type"] in ("prepare", "revise"):
                publication = self.store.get_edition_publication(publication_key)
                if publication:
                    return self.store.complete_job(job_id, {"kind": "edition", "edition": publication["result"], "recovered_publication": True})
            source_id, context, _ = _source_context(self.store, job)
            tools = StudyTools(self.store, source_id, self.vault_root)
            skill_names = _skills_for(job)
            try:
                reserve_budget(self.store, job_id, budget, self.settings.total_budget_usd)
            except BudgetLimitExceeded as exc:
                self.store.requeue_job(job_id, str(exc))
                return {"id": job_id, "status": "blocked_budget", "error": str(exc)}
            output, estimate = self.adapter.generate(job, context, tools, skill_names, budget)
            settle_budget(self.store, job_id, estimate)
            if job["job_type"] in ("prepare", "revise"):
                package = output.get("package", output)
                if package.get("complete") is not True: raise ValueError("worker output must explicitly declare complete=true")
                if job["job_type"] == "revise":
                    payload = json.loads(job["payload"])
                    unit_pair = next(((section["title"], u) for section in context["source"]["sections"] for u in section["units"] if u["id"] == payload.get("unit_id", job["entity_id"])), None)
                    units = package.get("edition", {}).get("units", [])
                    if not unit_pair or len(units) != 1 or units[0].get("section_title") != unit_pair[0] or units[0].get("unit_title") != unit_pair[1]["title"]:
                        raise ValueError("revision package must contain exactly the selected unit")
                else:
                    selected_pages = set(int(p) for p in json.loads(job["payload"]).get("pages", []))
                    if not selected_pages.issubset(tools.accessed_pages):
                        raise ValueError("worker did not inspect every requested source page")
                    cited_selected = set()
                    for unit in package.get("edition", {}).get("units", []):
                        refs = unit.get("source_refs")
                        if not isinstance(refs, list) or not refs or any(not isinstance(ref, dict) or not str(ref.get("locator", "")).strip() for ref in refs):
                            raise ValueError("every prepared unit must include page locators in source_refs")
                        cited = {ref.get("pdf_page", ref.get("source_page", ref.get("page_number", ref.get("page"))))
                                 for ref in refs if ref.get("source_file") in (None, context["source"]["metadata"].get("source_file"))}
                        cited_selected.update(page for page in cited if page in selected_pages)
                        if not cited.intersection(selected_pages):
                            raise ValueError("every prepared unit needs a primary source reference within the selected pages")
                        if any(page is not None and page not in selected_pages and page not in tools.accessed_pages for page in cited):
                            raise ValueError("worker cited a supporting PDF page it did not inspect")
                    if not selected_pages.issubset(cited_selected):
                        raise ValueError("edition package does not cover every selected page")
                imported = self.store.import_prepared_edition(source_id, package, publication_key)
                return self.store.complete_job(job_id, {"kind": "edition", "edition": imported})
            # Signoff itself authorizes synthesis; the validated, journaled plan is applied before success.
            plan = output.get("plan", output)
            if plan.get("signoff_id") != context["signoff_id"]:
                raise ValueError("synthesis plan signoff_id does not match the claimed job")
            if set(plan.get("source_revision_ids", [])) - {r["id"] for r in context["included_units"]}:
                raise ValueError("synthesis plan cites a revision outside the checked signoff snapshot")
            if not plan.get("idempotency_key"):
                plan["idempotency_key"] = f"signoff:{context['signoff_id']}"
            prepared_plan = self.store.import_synthesis_plan(job_id, self.vault_root, plan)
            applied = self.store.apply_imported_synthesis_plan(prepared_plan["id"], self.vault_root)
            return self.store.complete_job(job_id, {"kind": "synthesis", "plan_id": prepared_plan["id"], "applied": applied})
        except Exception as exc:
            try: return self.store.fail_job(job_id, str(exc))
            except ValueError: raise

    def run_forever(self, poll_seconds: float = 2.0) -> None:
        while True:
            result = self.run_once()
            if result is None or result.get("status") == "blocked_budget": time.sleep(poll_seconds)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the explicitly configured local study agent worker")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="claim and process at most one queued job")
    mode.add_argument("--loop", action="store_true", help="poll the queue until stopped")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args(argv)
    try:
        settings = WorkerSettings.from_env()
        store = Store(os.environ.get("MATHSPHYS_DB", "maths_phys.sqlite3"))
        worker = Worker(store, settings)
        if args.loop: worker.run_forever(args.poll_seconds)
        else: print(json.dumps(worker.run_once(), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"Worker not started: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
