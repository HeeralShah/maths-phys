# Implementation tracker

Status: application foundation is in development. Every v1 capability below is in scope; milestones are a build sequence, not a deferral list. The snapshot below distinguishes working foundations from product behavior that is still absent. No SDK trial is claimed here.

## Current implementation snapshot

### Working local workflows

- Register existing local PDFs, select physical pages explicitly, inspect their original page images and text, and import complete prepared editions atomically. Publication retains source references and annotations.
- Study saved Markdown/LaTeX units with expandable explanations, coloured marks, dated understanding checks, clarification requests and explicit refresh.
- Edit a durable learning profile; search/read the canonical Obsidian vault.
- Browse saved evidence-linked research graphs, source exercises, protected assistance, dated attempts and ordered practice sets. These interactions perform no model calls.
- Apply prepared Atlas synthesis plans from checked signoff snapshots using optimistic hashes, a recovery journal and idempotency. The optional configured worker performs synthesis after signoff without another approval step.
- Run the local launcher, create validated database/vault/PDF backups, and restore only into an empty destination. Backup/restore reject unfinished Atlas journals.
- The current machine has the real B6La Sturm-Liouville edition (refresher plus three units), three ClassicalDynamicsI source exercises and Keshav's evidence-linked reading-method map. These are prepared content, not claimed SDK benchmark outputs.

### Agent integration and remaining limits

- The optional Claude Agent SDK worker, six study skills and local tools are implemented. SDK 0.2.176/MCP 2.3.0 import and option construction were checked without model calls. Provider choice remains provisional and no paid comparison is claimed.
- Codex has a read-only readiness probe and opt-in bounded trial runner; subscription billing controls require verification before trial execution. The app-server trial is not a completed benchmark.
- Live provider-generated preparation/revision/research and full source-to-Atlas quality acceptance still need configured provider access and evaluation. Gemini comparison remains pending.
- Full cross-device solution-key recovery remains a limitation: Windows DPAPI solutions require the same user profile. Backup archives are not encrypted containers; protect them as private study data.
- Milestone checkboxes below reflect full acceptance, not the mere presence of an endpoint. Do not infer all v1 requirements are complete from this snapshot.

## M0 — Decisions and local project skeleton

- [x] Record the approved £20 total SDK trial cap across providers, cases, retries, and paid tools.
- [ ] Record exact model/version, tool permissions, and allowed web scope for each run.
- [ ] Resolve source file ownership/path behavior and supported v1 formats.
- [ ] Define backup target, restore procedure, encryption scope, and key recovery.
- [ ] Validate proposed React/TypeScript + FastAPI stack with a local vertical slice.
- [ ] Define data schema and migration/version policy for the accepted SQLite study store and Markdown vault canon.
- [ ] Keep current vault openable and unchanged by the skeleton.

Evidence: decision records, runnable local slice, schema/migration notes, and a vault preservation check.

## M1 — Source library and complete reading editions

- [ ] Source metadata/intake is inert and costs no agent action.
- [ ] Explicitly selected preparation action is visible and attributable.
- [ ] Edition generation completes before rendered output is published; internal progress checkpoints may be saved.
- [ ] Original content/order/notation and source provenance are retained.
- [ ] Failed/interrupted generation has explicit state and cannot appear complete.

Evidence: accepted source-to-edition walkthrough and persisted provenance.

## M2 — Study units, annotations, checks, and refreshers

- [ ] Agents recommend study-unit boundaries from examples; user can inspect them.
- [ ] Implement green/yellow/blue/purple marks with meanings from PRODUCT.md.
- [ ] Legacy marks retain historical dates/status and remain unassessed currently.
- [ ] Record initial dated checks only in v1; implement later quiet-recall workflow.
- [ ] Current-study refresher is no longer than one page.
- [ ] Difficulty is an agent's subjective assessment grounded in stated facts; no predicted-time fields/badges.

Evidence: representative new and imported study materials preserve correct current/historical state.

## M3 — Clarification, revision, and refresh lifecycle

- [ ] Chat submission starts a background revision job.
- [ ] Refreshing the displayed edition is explicit.
- [ ] Refresh retains checks and current reading position.
- [ ] Material revision of signed-off content asks for reconfirmation.

Evidence: a revision walkthrough covering submitted, completed, refreshed, and reconfirmation states.

## M4 — Problem library and hint ladder

- [ ] Support inline, source-end, and problem-set placements.
- [ ] Store subject, prerequisites, novelty, combination, workload, provenance, and learner experience.
- [ ] Provide orientation, small hint, strong hint, partial solution, and full solution.
- [ ] Exclude unrevealed solution content from default prompt context and search.
- [ ] Reveal only the explicitly selected level; reveal does not invoke an agent.

Evidence: retrieval/reveal walkthrough and representative metadata for each placement.

## M5 — Research, literature, results, assumptions, and graph

- [ ] Explicitly initiated research returns source-linked evidence.
- [ ] Capture literature, results, assumptions, and interpretations distinctly.
- [ ] Reconstruct assumptions using Keshav's three-pass approach and identify downstream influential works with evidence.
- [ ] Graph browse/expand is local and does not invoke agents.
- [ ] Each claim and edge retains evidence provenance.

Evidence: reviewed paper case with traceable assumptions, downstream works, and graph links.

## M6 — Signoff and incremental Atlas synthesis

- [ ] Explicit signoff starts background synthesis for subsection/chapter.
- [ ] Synthesis includes checked material only and records source/check provenance.
- [ ] Later signoffs update incrementally without losing prior provenance.
- [ ] Automatically improve/create/merge small multi-source canonical notes with one notation.
- [ ] Preserve manual intent; significant changes have human-readable Git messages.
- [ ] Unchecking retains existing Atlas contribution.
- [ ] Material revisions require reconfirmation before synthesis changes.

Evidence: multi-source signoff walkthrough including incremental update, uncheck, and reconfirmation.

## M7 — Vault preservation, privacy, backups, and v1 completion

- [ ] Existing Obsidian folders/configuration and notes are preserved.
- [ ] Private Git excludes PDFs, databases, credentials, environments, caches, temp artifacts, and local workspace state.
- [ ] Document and perform restore including SQLite, assets, vault content, and required keys.
- [ ] Validate solution protection against the agreed threat model and reveal policy.
- [ ] All M1–M6 criteria are evidenced; no listed v1 feature is omitted.

Evidence: restore record, privacy/config review, and complete v1 acceptance checklist.

## Initial implementation verification — 2026-11-01

- Seven backend unit tests pass, covering persistence, manual checks, partial sign-off, idempotency, job transitions and interrupted-job recovery.
- FastAPI application import and OpenAPI generation pass in the local virtual environment.
- Frontend TypeScript checking and Vite production build pass (`npm run build`). Browser interaction/visual verification remains pending.
- The browser shell connects to current APIs; graph/problem views and SDK processing remain explicitly unimplemented.

## Saved research/problem slice and vault relocation — 2026-11-01

- Knowledge folders and Obsidian configuration relocated together to `vault/`; 54 tracked files independently compared unchanged and worker verified all 57 moved files by SHA256. Internal wiki links remain vault-relative.
- Twelve backend tests pass, including graph evidence, cross-source endpoint inclusion, protected solutions and reveal without job creation. Full solutions use Windows DPAPI on this machine; cross-device recovery remains to be designed.
- Live HTTP smoke passed for source registration, saved edition, graph reads, problem catalogue privacy, deliberate full-solution reveal, and zero queued jobs. Synthetic smoke records used a temporary database only.
- Frontend production build passes with Markdown/LaTeX rendering, saved graph/provenance browsing, source problems and explicit clarification jobs. Browser verification recorded separately when available.
- SDK provider credentials remain unavailable in the environment; no paid comparison has run.

### Obsidian registration and CLI

Existing vault ID was repointed to `vault/` with Obsidian stopped and the global config backed up. App relaunched with the new vault active. Official `Obsidian.com` is installed (installer 1.12.7; app package 1.14.5). CLI remains disabled pending Settings > General > Advanced enablement; Windows lock screen prevents UI completion. Existing note/source hashes preserved.

### Remaining verification

Browser interaction verification was attempted but unavailable through the current UI provider. API smoke and TypeScript/Vite build passed; full visual QA remains open. Backup/restore implementation remains open; no backup feature is claimed.

## Functional build-out verification — 2026-11-01

- Tests cover complete publication, historical vs generated annotations, source provenance, material vs formatting revisions, signoff plan validation/recovery, learner profile, protected attempts/sets and adapter orchestration without paid calls. Final test counts are recorded in the delivery commit.
- Actual local imports are idempotent. Original source PDFs remain outside Git; plaintext exercise-assistance packages are kept only in ignored local state.
- Backup verification includes a real vault/database/PDF round trip and regression tests that reject absolute recovery journals, corrupt payloads and existing destinations.
- The private Git records executable workflows, skills, content explanations, decision history and operational guides. Runtime databases and provider credentials remain excluded.

## Verified delivery checkpoint

- 2026-11-01: 37 backend tests and 7 backup/restore tests pass. `pip check` reports no broken installed requirements.
- Frontend TypeScript/Vite build passes. Headless Edge walkthrough against an isolated API/database passed: rendered equations, expandable explanations and coloured annotation, decoded PDF image, dated check, persistent profile, vault wikilink navigation, ordered practice-set creation, dated attempt, local hint reveal with no job, and graph evidence opening the correct PDF page; zero browser page errors.
- Real local app restarted through `scripts/run_local.py`; the B6La source now has four prepared units and the updated display-math/prerequisite refresher. Three real Coriolis source questions and the 19-node/18-edge reading-method map are present in private local state. No current learner checks were created on the real data during testing.
- SDK import/dependency and option checks succeeded without a model request. Claude adapter is provisional; Codex probe is read-only; no benchmark winner or live generation quality is asserted.
- The source exercise assistance package is excluded from Git to preserve spoiler protection; restore the private backup to move its prepared material to another machine.
