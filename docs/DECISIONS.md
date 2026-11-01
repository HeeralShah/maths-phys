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
| D-16 | Build our own Gemini-powered agent with Google ADK and deploy it to Google's managed Agent Runtime, behind a provider-neutral job boundary. | Accepted 2026-11-01 | We own the agent code, skills, tools, prompts and orchestration. This supersedes the provisional Claude adapter, the planned provider contest and any proposal to depend on a prebuilt Antigravity agent. |
| D-17 | The previously authorized £20 multi-provider comparison budget remains unspent; no comparison is required after the user's provider selection. | Superseded without spend 2026-11-01 | Do not spend it implicitly; any paid Google pilot still needs configured credentials and visible job limits. |
| D-18 | Native PDF ingestion is mandatory inside our custom managed agent. Its ingestion stage sends the complete chapter PDF through Gemini's native document-understanding path before annotation and research stages consume the resulting source model. | Accepted 2026-11-01 | PDF is a first-class agent input and artifact; no lossy local text-extraction step or prebuilt-agent document limitation defines the architecture. |
| D-19 | A complete chapter (or chapter-sized whole document/paper) is the preparation and publication scope; small checkable items live inside it. | Accepted 2026-11-01 | Pages remain provenance, and partial page results never become readable editions. |
| D-20 | Reading additions are a separate layer anchored inline, interline, in the near margin, or as local overlays. | Accepted 2026-11-01 | Replace mixed Markdown cards and brittle first-text-match highlighting with structured anchors and derivation bridges. |
| D-21 | Literature-map canvas nodes are external works only; paper internals remain off-canvas analysis records and filters. | Accepted 2026-11-01 | Replace the same-document Keshav graph; preserve citation facts separately from interpreted intellectual relationships. |

## Proposed technical defaults

| ID | Proposal | Status | Validation needed |
|---|---|---|---|
| P-01 | React + TypeScript browser UI and Python + FastAPI local service. | Proposed | Validate local install/run ergonomics and file integration. |
| P-03 | Custom Google managed-agent pipeline: Google ADK orchestration on Agent Runtime, with native Gemini PDF ingestion followed by bounded annotation and research stages. | Accepted direction | Validate fidelity, actual token usage, deployment-region/privacy settings and runtime maturity before enabling private sources. |
| P-04 | Keep source files in user-managed locations; persist source metadata and references. | Proposed | Decide stable path handling and behavior when a file moves. |
| P-05 | Encrypt protected solution material and control reveal at the app boundary. | Proposed; details open | Define threat model, key custody, backup, and reveal behavior first. |

## Open decisions

| ID | Question | Gate |
|---|---|---|
| O-02 | Which structured bibliographic provider should back citation topology: OpenAlex, Semantic Scholar, Crossref, or a bounded combination? | Before enabling automated external literature-map research. |
| O-03 | Backup destination, retention, encryption, key recovery, and restore cadence? | Before claiming dependable v1 persistence. |
| O-04 | Exact encryption scope and solution reveal/storage policy? | Before storing protected solutions or implementing recovery keys. |
| O-05 | Supported source formats and local file lifecycle? | Before finalizing ingestion schema. |

## Retired SDK comparison cases (no results)

The prior controlled-comparison design named these cases:

- Sample B6La, physical PDF page 30 (printed page 29).
- `MA222_260_notes_2020-21`, page 27.
- `ClassicalDynamicsI`, page 5.

No benchmark was run and no money was spent. The user subsequently selected a custom Gemini-powered agent deployed on Google's managed agent runtime, so the provider contest is retired. The same cases remain useful as Google pipeline fidelity fixtures, not as evidence of a completed comparison.

## Implementation defaults adopted during the authorised build

- The Obsidian vault lives at `vault/`; application files live outside it. Existing vault identity and content were preserved.
- Initial source intake supports local PDFs; canonical notes remain Markdown. The app stores registered paths and source hashes rather than copying originals into Git.
- Windows full solutions use current-user DPAPI; other platforms use a private Fernet key. Backups preserve relevant data but do not create portable Windows DPAPI keys.
- Backup destinations are user-specified ZIP archives with SHA-256 manifests, consistent SQLite snapshots and source-path rebinding on restore. Active Atlas journals are refused; external vault editors should be paused.
- The prior Claude adapter is historical provisional code and is not the selected runtime. The current Google worker scaffold is not production ready until it uses the chosen ADK/Agent Runtime architecture and passes provider-neutral contract tests. No provider-generated result has been recorded.
- Subsection signoff itself authorises synthesis and application of a valid checked-only plan; no extra per-note review gate is introduced.
