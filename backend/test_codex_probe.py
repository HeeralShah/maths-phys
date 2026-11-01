import unittest
import contextlib
import io
import json
from pathlib import Path

from backend.codex_probe import (CodexProbeError, output_estimated_tokens,
                                 probe_codex, run_probe, validate_trial_gate)


class FakeRpc:
    def __init__(self):
        self.calls = []

    def request(self, method, params=None):
        self.calls.append((method, params))
        if method == "initialize":
            return {"userAgent": "test"}
        if method == "account/read":
            return {"account": {"type": "chatgpt", "planType": "plus", "email": "private@example.test"},
                    "requiresOpenaiAuth": True}
        if method == "account/rateLimits/read":
            return {"rateLimits": {"limitId": "codex", "primary": {
                "usedPercent": 33, "windowDurationMins": 300}, "secondary": {"usedPercent": 10}}}
        if method == "model/list":
            return {"data": [{"id": "gpt-test", "displayName": "Test Model",
                              "inputModalities": ["text", "image"],
                              "defaultReasoningEffort": "medium"}], "nextCursor": None}
        raise AssertionError(f"unexpected app-server request: {method}")

    def notify(self, method, params=None):
        self.calls.append((method, params))


class FakeProcess:
    def __init__(self, output):
        self.stdout = io.StringIO(output)
        self.stdin = io.StringIO()
        self.returncode = 0
        self.terminated = False

    def terminate(self): self.terminated = True
    def wait(self, timeout=None): return 0
    def kill(self): self.terminated = True


def fake_popen_factory(commands):
    def popen(command, **kwargs):
        commands.append(command)
        output = "\n".join([
            json.dumps({"id": 1, "result": {}}),
            json.dumps({"id": 2, "result": {"account": {"type": "chatgpt", "planType": "plus", "email": "secret@example.test"}, "requiresOpenaiAuth": True}}),
            json.dumps({"id": 3, "result": {"rateLimits": {"limitId": "codex", "primary": {"usedPercent": 41}}}}),
            json.dumps({"id": 4, "result": {"data": [{"id": "listed-model", "displayName": "Listed"}], "nextCursor": None}}),
        ]) + "\n"
        return FakeProcess(output)
    return popen


class CodexProbeTests(unittest.TestCase):
    def setUp(self):
        self.ledger = {
            "currency": "GBP",
            "total_cap_gbp": 20,
            "spent_gbp": 0,
            "providers": {"codex": {
                "auth_mode": "chatgpt",
                "paid_credit_extension_disabled": True,
            }},
        }

    def test_probe_uses_read_only_account_quota_and_catalog_methods(self):
        rpc = FakeRpc()
        result = probe_codex(rpc)
        self.assertEqual(result["cli_auth_method"], "chatgpt")
        self.assertEqual(result["plan_type"], "plus")
        self.assertEqual(result["quota"]["primary_used_percent"], 33)
        self.assertEqual(result["available_models"][0]["id"], "gpt-test")
        self.assertFalse(result["model_request_made"])
        self.assertNotIn("private@example.test", repr(result))
        methods = [method for method, _ in rpc.calls]
        self.assertEqual(methods, ["initialize", "initialized", "account/read",
                                   "account/rateLimits/read", "model/list"])

    def test_json_lines_process_transport_uses_only_read_methods_and_hides_auth_details(self):
        commands = []
        result = run_probe("fake-codex", popen_factory=fake_popen_factory(commands))
        self.assertEqual(result["cli_auth_method"], "chatgpt")
        self.assertEqual(result["quota"]["primary_used_percent"], 41)
        self.assertEqual(result["available_models"][0]["id"], "listed-model")
        self.assertNotIn("secret@example.test", repr(result))
        self.assertEqual(commands[0][1:3], ["-c", 'web_search="disabled"'])
        self.assertIn("mcp_servers={}", commands[0])

    def test_trial_gate_requires_explicit_model_chatgpt_and_credit_guard(self):
        probe = probe_codex(FakeRpc())
        validate_trial_gate(probe, "gpt-test", self.ledger, True)
        with self.assertRaisesRegex(CodexProbeError, "exact requested model"):
            validate_trial_gate(probe, "not-listed", self.ledger, True)
        with self.assertRaisesRegex(CodexProbeError, "paid credit extension"):
            validate_trial_gate(probe, "gpt-test", self.ledger, False)

    def test_trial_gate_refuses_api_billing_or_invalid_budget(self):
        probe = probe_codex(FakeRpc())
        api_probe = dict(probe, cli_auth_method="apiKey")
        with self.assertRaisesRegex(CodexProbeError, "API-key billing"):
            validate_trial_gate(api_probe, "gpt-test", self.ledger, True)
        over_budget = {**self.ledger, "total_cap_gbp": 20.01}
        with self.assertRaisesRegex(CodexProbeError, "no greater than £20"):
            validate_trial_gate(probe, "gpt-test", over_budget, True)
        used_up = {**self.ledger, "spent_gbp": 20}
        validate_trial_gate(probe, "gpt-test", used_up, True)
        exhausted = {**self.ledger, "spent_gbp": 20.01}
        with self.assertRaisesRegex(CodexProbeError, "no greater than £20"):
            validate_trial_gate(probe, "gpt-test", exhausted, True)

    def test_estimated_output_size_is_only_a_post_response_check(self):
        self.assertEqual(output_estimated_tokens("abcd"), 1)
        self.assertEqual(output_estimated_tokens("abcdefgh"), 2)

    def test_runner_requires_explicit_complete_trial_flags_without_starting_transport(self):
        from scripts.codex_trial import main
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            status = main(["--run"])
        self.assertEqual(status, 2)
        self.assertIn("--case", errors.getvalue())
        self.assertIn("--budget-ledger", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
