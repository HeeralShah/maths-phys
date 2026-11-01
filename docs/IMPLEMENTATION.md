# Implementation tracker

Status: application foundation is in development. Every v1 capability below is in scope; milestones are a build sequence, not a deferral list. The snapshot below distinguishes working foundations from product behavior that is still absent. No SDK trial is claimed here.

## Current implementation snapshot

### Implemented foundations

- Backend SQLite schema and FastAPI adapter cover source metadata/outlines, immutable saved revisions, dated manual checks, section signoff records, and explicit prepare/revise/signoff job requests.
- Section signoff snapshots only units whose latest revision is currently marked understood.
- Job records include status transitions, stable IDs, caller idempotency keys, atomic claiming primitives, and recovery of stale running leases.
- Reads and manual checks do not enqueue jobs. Source registration stores metadata/outline only; it does not upload or process source content.
- Twelve backend tests are present in `backend/test_store.py`. The documented command is `python -m unittest discover -s backend -p "test_*.py"` from the repository root.

### Not implemented or not operational

- The worker is unconfigured. Queued jobs are durable, but no agent generation, revision, or synthesis executes; the stub refuses to mark a job complete without a real worker.
- Source parsing, faithful rendered reading editions, generated edition publication, chat-driven revision plus refresh, and end-to-end signoff synthesis are not complete workflows.
- Saved evidence-linked research graph CRUD and source-exercise catalogue/reveal foundations now exist. Agent-driven research/extraction, full problem attempt tracking, backup/restore, and the full annotation/refresher experience remain incomplete.
- The frontend scaffold is in development; do not infer that a visible shell means its linked v1 workflows are operational.

The snapshot reflects repository code and test inventory; milestone checkboxes below remain open until the full acceptance criteria are evidenced.

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
