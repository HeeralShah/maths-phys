"""Read-only Codex CLI/app-server readiness probe.

This module never starts a thread or a model turn. It intentionally returns a
small allow-listed account/model summary, never email addresses or credentials.
"""
from __future__ import annotations

import json
import math
import queue
import shutil
import subprocess
import threading
from typing import Any, Callable


class CodexProbeError(RuntimeError):
    pass


class JsonRpcProcess:
    """Minimal JSON-lines app-server transport with bounded request waits."""

    def __init__(self, binary: str = "codex", popen_factory: Callable = subprocess.Popen,
                 timeout_seconds: float = 10.0):
        resolved = shutil.which(binary) if binary == "codex" else binary
        if not resolved:
            raise CodexProbeError("Codex CLI was not found on PATH")
        self.timeout_seconds = timeout_seconds
        self.process = popen_factory(
            [resolved, "-c", 'web_search="disabled"', "-c", "mcp_servers={}", "app-server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
            bufsize=1,
        )
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._events: list[dict] = []
        self._next_id = 1
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    def _read_stdout(self) -> None:
        try:
            for line in self.process.stdout:
                self._lines.put(line)
        finally:
            self._lines.put(None)

    def request(self, method: str, params: dict | None = None) -> dict:
        request_id = self._next_id
        self._next_id += 1
        request = {"method": method, "id": request_id}
        if params is not None:
            request["params"] = params
        try:
            self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise CodexProbeError("Codex app-server input closed") from exc
        while True:
            try:
                line = self._lines.get(timeout=self.timeout_seconds)
            except queue.Empty as exc:
                raise CodexProbeError(f"timed out waiting for app-server {method} response") from exc
            if line is None:
                raise CodexProbeError(f"Codex app-server exited during {method}")
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise CodexProbeError(f"app-server {method} failed")
                return message.get("result") or {}
            self._events.append(message)

    def next_event(self, timeout_seconds: float) -> dict:
        if self._events:
            return self._events.pop(0)
        try:
            line = self._lines.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise CodexProbeError("timed out waiting for model turn completion") from exc
        if line is None:
            raise CodexProbeError("Codex app-server exited during model turn")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise CodexProbeError("Codex app-server emitted malformed JSON") from exc

    def notify(self, method: str, params: dict | None = None) -> None:
        request = {"method": method}
        if params is not None:
            request["params"] = params
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

    def close(self) -> None:
        try:
            self.process.terminate()
            self.process.wait(timeout=2)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass


def probe_codex(rpc: Any) -> dict:
    """Read auth, quota and model catalogue through documented app-server methods."""
    rpc.request("initialize", {"clientInfo": {
        "name": "maths-phys-readiness-probe",
        "title": "Maths and Physics SDK readiness probe",
        "version": "0.1.0",
    }})
    rpc.notify("initialized", {})
    account_result = rpc.request("account/read", {"refreshToken": False})
    limits_result = rpc.request("account/rateLimits/read", {})
    models_result = rpc.request("model/list", {"limit": 100, "includeHidden": False})

    account = account_result.get("account") or {}
    rate_limits = limits_result.get("rateLimits") or {}
    primary = rate_limits.get("primary") or {}
    models = []
    for entry in models_result.get("data", []):
        if not isinstance(entry, dict):
            continue
        models.append({
            "id": entry.get("id") or entry.get("model"),
            "display_name": entry.get("displayName"),
            "input_modalities": entry.get("inputModalities", ["text", "image"]),
            "default_reasoning_effort": entry.get("defaultReasoningEffort"),
        })
    return {
        "cli_auth_method": account.get("type"),
        "plan_type": account.get("planType"),
        "requires_openai_auth": account_result.get("requiresOpenaiAuth"),
        "quota": {
            "limit_id": rate_limits.get("limitId"),
            "primary_used_percent": primary.get("usedPercent"),
            "primary_window_minutes": primary.get("windowDurationMins"),
            "secondary_used_percent": (rate_limits.get("secondary") or {}).get("usedPercent"),
        },
        "available_models": models,
        "model_catalog_next_cursor": models_result.get("nextCursor"),
        "probe_methods": ["account/read", "account/rateLimits/read", "model/list"],
        "model_request_made": False,
    }


def run_probe(binary: str = "codex", timeout_seconds: float = 10.0,
              popen_factory: Callable = subprocess.Popen) -> dict:
    rpc = JsonRpcProcess(binary, popen_factory=popen_factory, timeout_seconds=timeout_seconds)
    try:
        return probe_codex(rpc)
    finally:
        rpc.close()


def validate_trial_gate(probe: dict, model: str, ledger: dict,
                        credits_disabled_confirmed: bool) -> None:
    """Require the approved GBP cap plus an explicit included-usage-only guard."""
    if not model or model not in {entry.get("id") for entry in probe.get("available_models", [])}:
        raise CodexProbeError("the exact requested model is not available for this signed-in account")
    if probe.get("cli_auth_method") != "chatgpt":
        raise CodexProbeError("Codex trial runner requires the existing ChatGPT sign-in, not API-key billing")
    if not credits_disabled_confirmed:
        raise CodexProbeError("confirm in ChatGPT settings that paid credit extension is disabled before a trial")
    if ledger.get("currency") != "GBP":
        raise CodexProbeError("budget ledger must use GBP")
    try:
        if isinstance(ledger.get("total_cap_gbp"), bool) or isinstance(ledger.get("spent_gbp"), bool):
            raise TypeError("boolean is not a monetary amount")
        cap = float(ledger["total_cap_gbp"])
        spent = float(ledger["spent_gbp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CodexProbeError("budget ledger needs numeric total_cap_gbp and spent_gbp") from exc
    if not math.isfinite(cap) or not math.isfinite(spent) or cap <= 0 or cap > 20 or spent < 0 or spent > cap:
        raise CodexProbeError("budget ledger must have a positive cap no greater than £20 and spent within the cap")
    providers = ledger.get("providers")
    if not isinstance(providers, dict):
        raise CodexProbeError("budget ledger must contain a providers object")
    codex_config = providers.get("codex") or {}
    if codex_config.get("auth_mode") != "chatgpt" or codex_config.get("paid_credit_extension_disabled") is not True:
        raise CodexProbeError("budget ledger must record ChatGPT auth and paid-credit extension disabled")


def output_estimated_tokens(text: str) -> int:
    """Conservative rough output check only; app-server exposes no token cap field."""
    return max(1, math.ceil(len(text.encode("utf-8")) / 4))
