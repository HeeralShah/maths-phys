# Retired multi-provider SDK trial protocol

Status: superseded without a run or spend. On 2026-11-01 the user selected a custom Gemini-powered agent, owned by this project and deployed on Google's managed Agent Runtime, and explicitly rejected Claude as the production agent layer. This file is retained as historical evaluation design; it does not authorize a provider contest or any paid call. Google pipeline validation uses visible per-job limits and the same representative sources where useful.

## Historical cases (not an active trial)

The original comparison plan considered Claude Agent SDK, Codex SDK, and Google ADK. That provider contest was retired after the user selected a custom Gemini-powered Google agent and rejected Claude as the production agent layer. The current selection is recorded in [ADR 0003](adr/0003-use-custom-google-adk-agent-runtime.md); the Google architecture and cost envelope are in [the Google agent report](research/google-agent-sdk-comparison.md). The £20 cap remains unspent and is not standing authorization for paid calls.

These three cases were defined for the retired contest and may be reused as local fidelity fixtures:

1. Sample B6La, physical PDF page 30 (printed page 29).
2. `MA222_260_notes_2020-21`, page 27.
3. `ClassicalDynamicsI`, page 5.

No SDK comparison is currently planned. If a bounded Google compatibility experiment is proposed later, it requires a concrete plan and explicit authorization before any paid call.

Do not substitute cases between SDKs. Confirm exact local source identity and page extraction before running; record hashes or stable file identifiers without copying source PDFs into the repository.

## Retired protocol (reference only)

Record all of the following before any paid activity:

- Total paid trial ceiling of £20 across every provider, sample case, retry, and paid tool.
- Whether web access is allowed and any allowed domains.
- Which account/project/credentials may be used (never record secret values).
- Exact model/version and SDK release for each run.
- Local hardware/runtime constraints and expected concurrency.
- User authorization for any non-local tool calls.

If zero-cost or local-only evaluation is possible, still record the exact allowed scope. Keep a cumulative ledger across providers and stop before the £20 total ceiling; do not automatically retry with a paid fallback if it could exceed the remaining balance.

## Controlled run procedure

1. Freeze one prompt, one output schema, one tool contract, and one evaluation rubric for all SDKs.
2. Run each of the three cases once per SDK under the same source files, page boundaries, tool permissions, and output limits. Repeat only when a documented transport/runtime failure invalidates a run; record the failed attempt and cost.
3. Require structured outputs covering source-faithful extraction, study-unit proposal, notation handling, source provenance, assumptions/claims where applicable, and explicit unresolved uncertainty.
4. Capture raw output, tool-call trace, elapsed execution time, observed cost, errors, and any manual intervention. Elapsed time here measures the SDK trial only; it is not a learner study-time prediction.
5. Blind-label outputs by candidate before human scoring where practical. Do not score an SDK based on model brand or a single fluent response.
6. Record all results in a local evaluation report outside Git if it contains source excerpts or private content; commit only a sanitized summary and rubric.

## Scoring rubric

Score each dimension 0–4 for each case and include a short evidence note. A high score requires direct evidence in the output or trace.

| Dimension | What to inspect |
|---|---|
| Source fidelity | Preserves meaning/order and distinguishes source text from interpretation. |
| Provenance | Claims and generated study content link to correct source/page evidence. |
| Notation handling | Retains original notation in reading output and can state normalized form separately. |
| Study-unit quality | Useful boundaries and examples without unsupported content. |
| Tool control | Uses only permitted tools; no hidden or unsolicited calls. |
| Failure behavior | Reports uncertainty, partial completion, and errors without claiming completion. |
| Repeatability | Stable structured output under the frozen prompt/tool contract. |
| Local integration | Fits the proposed local persistence and user-controlled workflow. |
| Cost and operations | Observed cost, setup burden, latency, and debugging visibility. |

Do not collapse scores into a winner without recording the weights and rationale. A candidate with weak tool control or provenance should not be selected solely for output quality.

## Report template

For each candidate and case record: SDK/version, model/version, date, source identifier/page, prompt/schema revision, tool permissions, run status, observed cost, elapsed trial time, raw artifact location, tool trace location, scores by dimension, evidence notes, and reviewer. End with trade-offs, operational risks, and a recommendation marked **proposed** until the user accepts it.

## Completion criteria

The trial is complete only when all three cases ran under the controlled protocol for each candidate or a specific candidate/case failure is documented; all scores have evidence notes; costs are within the approved ceiling; and the report contains a reasoned recommendation. Until then, SDK selection remains open.

## Approved historical budget — 2026-11-01

The user approved £20 total across all provider trials, including retries and paid tools. This cap is historical evaluation authorization only; it is not a standing requirement to compare rejected providers or run Google generation. Record actual usage and currency conversion if the user later authorizes a pilot. No trials have run and no money has been spent.
