# Codex SDK readiness and trial runner

## Read-only readiness probe

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe scripts/codex_trial.py --probe
```

The probe starts `codex app-server` with web search disabled and MCP servers empty, then calls only `initialize`, `account/read`, `account/rateLimits/read`, and `model/list`. It reports the auth mode, plan when available, quota percentages, and models visible to that account. It does not start a thread or model turn and does not print account email, access tokens, or other credentials.

The local Codex SDK path is available through the authenticated Codex CLI app-server. This checkout uses the native JSON-RPC transport so no additional Python SDK package needs to be installed. The exact Codex CLI version and current account/model catalogue are read at runtime, not hard-coded.

## Explicit, single-case trial

The runner supports the same source cases recorded in `docs/SDK-TRIAL.md`: B6La PDF page 30 (printed page 29), MA222 notes PDF page 27 (printed page 27), or ClassicalDynamicsI PDF page 5 (printed page 14). It extracts and renders only the selected page, includes the local `prepare-edition` skill text, disables web search and MCP connections for its app-server process, requests read-only sandbox access, and returns a structured artifact. The source PDF hash and page locator are recorded in the artifact.

The app-server API exposes structured `outputSchema` but the documented `turn/start` request has no hard output-token limit. `--output-cap-tokens` therefore instructs the model and enforces only a post-response size check; it is not a billing ceiling. A wall-clock timeout terminates the local app-server process but cannot guarantee a precise cost ceiling after a model request has started.

Because ChatGPT Plus can extend usage with ChatGPT credits, no trial may start unless the user has disabled paid-credit extension in account settings and explicitly confirms this. A ledger file outside Git must also say this is the selected Codex auth mode and keep the total cap at or below £20. This runner rejects API-key auth, unlisted models, absent credit-extension confirmation, malformed/exhausted ledgers, omitted run parameters, and artifact/ledger paths inside the repository. The `--run` flag is required; there is no implicit model call.

Example private ledger (create outside the repository, e.g. in a user-selected study backup directory):

```json
{
  "currency": "GBP",
  "total_cap_gbp": 20.0,
  "spent_gbp": 0.0,
  "providers": {
    "codex": {
      "auth_mode": "chatgpt",
      "paid_credit_extension_disabled": true
    }
  }
}
```

Readiness only:

```powershell
.\.venv\Scripts\python.exe scripts/codex_trial.py --probe
```

One explicitly selected trial (the command itself initiates a model turn):

```powershell
.\.venv\Scripts\python.exe scripts/codex_trial.py --run `
  --case b6la `
  --model "MODEL_ID_FROM_PROBE" `
  --max-seconds 300 `
  --output-cap-tokens 4000 `
  --budget-ledger "D:\Study Backups\sdk-trial-ledger.json" `
  --output "D:\Study Backups\codex-b6la-p30.json" `
  --confirm-paid-credits-disabled
```

The command cannot enforce whether an account-level credit-extension setting is actually disabled; the confirmation flag is an explicit user assertion. Do not use it until that setting is checked. A completed result records no additional GBP charge only under the included-usage-only condition. No Codex trial run has been performed by this implementation task.

## Official reference material

- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk) documents the Python SDK over local app-server JSON-RPC.
- [Codex app-server](https://learn.chatgpt.com/docs/app-server) documents the account, quota, model-list, structured-output, and local-image methods used by the adapter.
- [Codex authentication](https://learn.chatgpt.com/docs/auth?surface=cli) distinguishes ChatGPT subscription access from API-key usage billing.
- [Codex pricing](https://learn.chatgpt.com/docs/pricing?codex-pricing-plans=individual) says ChatGPT and Codex share usage, Plus can extend usage with ChatGPT credits, and tasks have variable usage.
- [Web search configuration](https://learn.chatgpt.com/docs/web-search) documents `web_search = "disabled"` and its separation from command sandbox network policy.
