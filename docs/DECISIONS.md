# Decision log

This log separates accepted requirements from implementation proposals. A proposal is not an implementation fact. Update status when a choice is validated or superseded.

## Accepted direction

| ID | Decision | Status | Consequence |
|---|---|---|---|
| D-01 | The product is a personal, private, local-first browser study application. | Accepted | Optimize for one learner and preserve user ownership of local materials. |
| D-02 | Keep the existing Obsidian vault and Markdown topic canon. | Accepted | Integrate with the vault additively; do not migrate destructively. |
| D-03 | Source upload/metadata is inert; preparation requires explicit source selection and action. | Accepted | Separate intake from paid/agent generation. |
| D-04 | Complete edition generation before publishing its rendered form for study. | Accepted | Internal progress checkpoints may exist, but only a complete edition is published as available. |
| D-05 | Browsing, graph expansion, and hint reveal do not trigger agent generation. | Accepted | Keep navigation and retrieval read-only with respect to paid work. |
| D-06 | Submitting clarification chat starts background revision; refresh is explicit and preserves checks and position. | Accepted | Submission starts the job; refresh is the user's separate display action. |
| D-07 | Signoff starts explicit background synthesis using checked material only. | Accepted | Synthesis is gated by user intent and current study checks. |
| D-08 | Later signoff is incremental; unchecking retains existing Atlas; material revisions require reconfirmation. | Accepted | Maintain stable, provenance-linked synthesis and explicit revision consent. |
| D-09 | Reading editions retain source notation; canonical Atlas notes normalize notation. | Accepted | Preserve both faithful source reading and cross-source consistency. |
| D-10 | Include research graphs, literature, results, assumptions, and evidence links in v1. | Accepted | Research is part of scope, not a later milestone. |
| D-11 | Include the full problem model and five-level prerecorded hint ladder in v1. | Accepted | Hide solution content from ordinary context/search until explicit reveal. |
| D-12 | Do not provide time predictions; agent-assessed difficulty is subjective, grounded in stated facts, and accompanied by those facts. | Accepted | Show the basis of an assessment; do not estimate study duration. |
| D-13 | Private Git contains source notes, docs, code, and schemas; excludes PDFs, DBs, secrets, environments, caches, and temp artifacts. | Accepted | Use private Git for text/code history, plus a separate data backup plan. |
| D-14 | Use human-readable Git messages for meaningful synthesis changes and preserve manual intent. | Accepted | Generated changes remain inspectable and reversible. |
| D-15 | Persist structured study state, results, and graph data in SQLite; keep canonical topic notes in Markdown/Obsidian. | Accepted | Operational state belongs in SQLite; canonical prose belongs in the vault. |
| D-16 | Use an agent SDK harness with vault, tools, web, math, and skills capabilities. | Accepted | Harness shape is decided; the specific SDK remains open pending comparison. |
| D-17 | SDK comparison has a £20 total spending ceiling across all providers and sample jobs, including retries and paid tools. | Accepted by user 2026-11-01 | Track actual spend and stop before exceeding the total. |

## Proposed technical defaults

| ID | Proposal | Status | Validation needed |
|---|---|---|---|
| P-01 | React + TypeScript browser UI and Python + FastAPI local service. | Proposed | Validate local install/run ergonomics and file integration. |
| P-03 | Local agent SDK harness with explicit tools for vault, web, math, and skills. | Accepted; specific SDK open | Compare candidates under SDK-TRIAL.md and define the tool/permission contract. |
| P-04 | Keep source files in user-managed locations; persist source metadata and references. | Proposed | Decide stable path handling and behavior when a file moves. |
| P-05 | Encrypt protected solution material and control reveal at the app boundary. | Proposed; details open | Define threat model, key custody, backup, and reveal behavior first. |

## Open decisions

| ID | Question | Gate |
|---|---|---|
| O-02 | Which SDK: Claude Agent SDK, Codex SDK, or Google ADK? | After the authorized trial protocol completes within recorded budget limits. |
| O-03 | Backup destination, retention, encryption, key recovery, and restore cadence? | Before claiming dependable v1 persistence. |
| O-04 | Exact encryption scope and solution reveal/storage policy? | Before storing protected solutions or implementing recovery keys. |
| O-05 | Supported source formats and local file lifecycle? | Before finalizing ingestion schema. |

## SDK comparison cases (not results)

The controlled comparison must use the same three cases for each candidate SDK:

- Sample B6La, physical PDF page 30 (printed page 29).
- `MA222_260_notes_2020-21`, page 27.
- `ClassicalDynamicsI`, page 5.

No benchmark has been run. Do not describe any SDK as selected or any score as observed until the protocol is run and results recorded.
