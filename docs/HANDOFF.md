# Project handoff: Maths & Physics Study Atlas

Updated 2026-11-03. This handoff consolidates the conversation's product requirements, corrections, current implementation direction, and next-session context. It is an index and working brief, not a replacement for the detailed specifications linked below.

## Short answer: are the decisions already documented?

Most durable product decisions are recorded across `docs/PRODUCT.md`, `docs/DECISIONS.md`, `docs/ARCHITECTURE.md`, `docs/ANNOTATION-GRAMMAR.md`, `docs/READER-GRAPH-REDESIGN.md`, and the ADRs. They are not yet represented consistently: the root `README.md`, `AGENTS.md`, portions of `docs/IMPLEMENTATION.md`, and the Claude section in `backend/README.md` still contain stale status or SDK-trial instructions. Use the accepted requirements and later decisions listed below as the source of truth, then reconcile those older summaries.

## User's goal

Build a private, personal, local-first study system for mathematics and physics that makes it fast to understand lecture notes and books, inspect difficult derivations, read research papers in context, and practice source problems without getting stuck without knowing why. The system should retain source provenance and the user's own annotation patterns, build an evolving topic-oriented Obsidian knowledge base, and make study history visible.

The desired reading experience is a readable, visual browser edition that keeps the source recognizable and places concise explanations, derivations, intuition, issue flags, and links at the exact point where they help. The system should explain the hard steps and avoid expanding straightforward ones into unnecessary prose.

## Accepted product requirements

### Architecture and ownership

- The first release is for one user, runs locally on the user's laptop, and keeps source files and study data under their control.
- The primary reading and problem-solving surface is a dedicated browser UI. Obsidian remains available for editing and browsing canonical knowledge notes.
- Use SQLite for durable application state and saved results; Markdown in the `vault/` Obsidian vault for the evolving canonical topic knowledge base; original source files remain user-owned file assets outside Git.
- No graph database is needed initially. Store relationships in SQLite and use them to render visual maps.
- The knowledge base is topic-oriented, can combine many sources, uses one canonical notation, and should evolve through automatic create/update/merge after an approved synthesis. Preserve manual edits and their intent in Git history with meaningful messages.
- Keep provider credentials, original PDFs, runtime databases, environments, caches, and temporary artifacts out of Git. Git is for private versioning of code, decisions, documentation, and Markdown notes. Backups are a separate requirement.

### Source preparation and reading editions

- Adding/uploading a source and cataloguing metadata must not start agent work or incur model cost. The user explicitly selects a preparation scope.
- Prepare a complete chapter in one operation. If the source document is already one chapter or one paper, use the complete document. For a book or a long lecture-note collection, choose a chapter/subsection as the scope; do not prepare an entire book as one edition.
- Keep all source content and order. Paragraphs and blocks can be reflowed or separated to improve readability, and layout can be improved, but substantive source content must not be silently changed.
- Keep source notation in the reading edition. Generated commentary is a separate, anchored layer: inline notes and intuition, derivation bridges between formula lines, near-margin callouts, expandable detail/examples, and clearly marked proposed corrections.
- Break complex formula transitions into visible algebraic manipulations. Name results/identities used between steps. If a result lies outside the selected scope, link to the relevant Atlas note/source; if applying it requires nontrivial manipulation, show that manipulation.
- Add intuition and alternative explanations from the user's own materials where useful. Identify likely source mistakes and show a correction in a distinct layer while retaining the source expression.
- Show only a complete, validated edition in the reader. Agent work and all generated UI content are prepared before rendering. Do not make agent calls during ordinary reading, graph navigation, expansion, or checking.
- A reader clarification chat starts a revision job. Once complete, the user chooses Refresh to rerender with the new explanation, graph, or annotations. Preserve checks and reading position across refresh.
- The agent may inspect nearby definitions or supporting context needed to explain a selected chapter without silently preparing those surrounding pages as editions.

### Annotation semantics, knowledge profile, and checks

The user's historical annotation conventions are the calibration source. `docs/ANNOTATION-GRAMMAR.md` records the corpus audit and details; preserve this semantic mapping:

- **Green**: something unclear, an error/mistake, or a reference to an unfamiliar/external document.
- **Yellow/orange/pink highlight with red or rust text**: the user's own explanatory work, mini-proof, intermediate derivation, or interpretation.
- **Blue**: the learner has understood this fully and can return later without more annotation. Only the learner may set current understanding; an agent must never mark understanding for them.
- **Purple**: a source exercise or “exercise for reader” not done at the time.
- Store meaning separately from colour. An explanation can address a green issue but must not erase the issue that prompted it.
- Study units should be selected by the agent, guided by skills/examples from the user's annotated materials; units may be claims, paragraphs, equation groups, proof steps, or other useful chunks.
- Place a manually tickable understanding check and date beside each suitable small unit. Maintain an editable starting-knowledge profile and use it with dated checks to judge what needs explanation. A separate rust/confidence tool based on elapsed time since checks may be developed later; the check remains the learner's own manual record.
- Historical imported blue marks and notes record prior study only. Never invent present-day check dates or imply current understanding from legacy annotations.
- A subsection can be signed off with a subset of checks: e.g. six understood of eight incorporates six; the remaining two stay open. A later signoff incorporates the remaining units incrementally without duplicate synthesis.
- Unchecking changes the current understanding record but does not delete useful Atlas knowledge. Checks are tied to the edition version; material mathematical changes require reconfirmation, while formatting-only changes do not.

### Atlas synthesis and notation

- Checking items does not silently rewrite the Atlas. Wait for the user to sign off on the chapter/subsection; then automatically synthesize the checked items without asking for approval of each note.
- Synthesis may create, improve, merge, or reorganize small topic notes to fit the existing canon. It should capture the cleanest explanations, expanded derivations, intuition, and provenance across all contributing sources.
- One notation should become canonical in the Atlas. When sources differ in conventions, explain the translation and choose the canonical form; preserve distinct cases when merging would obscure a real mathematical distinction. Keep each source's original notation in its reading edition.
- Treat manual note edits as intentional input to future synthesis, preserving their substance and revision history.

### Problems and protected solutions

- Start with source exercises only: inline exercises, exercises for the reader, chapter-end exercises, and source problem sets. Every problem links back to the original document and locator. Generated problems are outside the initial catalogue.
- Tag by subject/prerequisites; novelty (direct application, extension, new technique/unfamiliar insight); combination (one idea, linked ideas, cross-topic synthesis); workload (short argument, substantial calculation, multi-stage proof); provenance (source/document/exercise/institution/course/year); and learner experience (unattempted, attempted, hints used, independently solved).
- Difficulty is a subjective assessment grounded in observable facts and the system should state those facts. Do not predict or display solution time.
- Build practice sets from selected tags and material the user has signed off, with source links. Assistance is progressively requested in this order: orientation → small hint → stronger hint → partial working → full solution.
- Prevent accidental spoilers: solutions must stay out of ordinary search and tutor context, and only the chosen assistance level is revealed on explicit request. Encrypt stored solutions. The user wants a preventative layer but does not want password prompts; exact protection/key recovery remains an operational decision. Current Windows DPAPI/Fernet behavior and its portability limits are described in PRODUCT and GETTING-STARTED.

### Research papers and literature maps

- Research workflow is distinct from lecture-note study. A map is centered on a focal work and helps show its place in the literature: important predecessors, books/results needed to understand it, how it uses or extends earlier work, relevant assumptions, and downstream influential/heavily cited work.
- Canvas graph nodes are bibliographic works only. Never make graph edges/nodes between sections, equations, assumptions, or results within the same paper. Paper sections, results, assumptions, contributions, and methods are analysis records and filters that explain relationships to external works.
- Distinguish bare citation facts from author-stated relationships and from evidence-backed inference. Keep locators and evidence for claims/edges. Do not treat a citation alone as proof of influence or intellectual dependence.
- Use Keshav's “How to Read a Paper” as a seminal method source. Reconstruct the target paper's assumptions and map how new assumptions relate to prior works/assumptions, with evidence and epistemic status.
- UI browsing/filtering/expansion is local. Research discovery/web or scholarly lookups are explicit jobs performed before the map renders; do not make serial agent calls as a user clicks through the view. A clarification chat can request more work and explicit refresh can publish a newly prepared map.
- Current source-provider research is in `docs/research/scholarly-literature-sources.md`. Do not scrape Google Scholar; use documented bibliographic/search services and record evidence. The structured provider choice is still open in `docs/DECISIONS.md`.

### Agent/model direction and cost boundaries

- The user rejected Claude as the desired agent layer and clarified: “We are not necessarily using antigravity. We creating our own managed agent.” Own the agent harness, tools, skills, context policy, prompts, orchestration, and output validation.
- Current accepted direction is a custom Google ADK application on Google's managed Agent Runtime, with native PDF ingestion through Gemini. This is distinct from a saved AI Studio Custom Agent built on a prebuilt Antigravity configuration. The separate `google-antigravity` Python SDK and ADK Labs wrapper are research/compatibility possibilities, not the selected production dependency.
- Agent context should include the relevant existing vault notes, learner profile, annotation examples/skills, selected source scope, and explicitly permitted research/tools. Keep model work bounded and visible. The local database/vault remain the durable truth; old chat sessions are not required to recover a chapter.
- Earlier the user approved a **£20 total** cap for a sample-based provider comparison. That comparison was later retired after selecting Google's custom agent; the cap is unused and is not blanket authorization for a paid pilot. No paid model call or benchmark result is recorded. Any next paid use needs explicit user action, visible limits, and cost tracking.
- Read `docs/research/google-managed-agent-options.md` and `docs/research/google-agent-sdk-comparison.md` for current official-doc research and chapter cost estimates. No model trial should be inferred from the SDK scaffold/tests.

## Confirmed workflow decisions

- A complete selected edition is generated and validated before it appears in the browser.
- User checks are manual and version-specific.
- Signoff consumes checked units only; partial and later incremental signoff are both supported.
- Unchecking does not retract Atlas material.
- Material mathematical changes require reconfirmation; formatting changes preserve checks.
- Context-only surrounding source may be inspected without producing an edition of it.
- Conflicting conventions are reconciled to one Atlas notation, with translation explained and genuine distinct cases preserved.
- Manual Atlas editing is an intentional signal; use Git version history and human-readable change messages.
- Agent generation, paid research, and Atlas mutation happen in explicit background jobs before the UI refresh/renders results. Local reader/graph actions do not start the agent.

## Current repo and implementation snapshot

- Repository: private `HeeralShah/maths-phys`, branch `main`. Last known published commit when this handoff was prepared: `9c1986c` (“Build Google agent and study workflow foundations”, 2026-11-01). Recheck Git state before making changes.
- The vault is `vault/`; it is the Obsidian vault and should be preserved additively. Canonical topic notes are Markdown.
- Existing application is more advanced than some overview docs claim. It has local SQLite/FastAPI/React flows for saved editions, checks/signoff, Atlas plans, evidence-linked research, source problems, protected assistance and attempts. `docs/GETTING-STARTED.md` and the dated evidence sections of `docs/IMPLEMENTATION.md` describe usable workflows and constraints.
- Recent code adds v2 chapter/literature contracts and migrations, an ADK Agent Runtime adapter with native PDF handling and fake-transport tests, a source annotation grammar, reader/graph design specs, and dev-only `?readerPrototype=A|B|C` and `?graphPrototype=A|B|C` UI prototypes.
- Prior checks at commit `9c1986c`: 53 backend tests passed; Vite production build passed with a large-JavaScript-chunk warning. No paid calls. Literature prototype fixture is explicitly mock material and not a verified literature review. Browser visual QA of the new prototypes was not completed.
- The ADK worker is an opt-in boundary/scaffold, not a deployed or production-ready agent. Google credentials/runtime deployment, callback enforcement, region/retention review, real native-PDF smoke, and representative output-quality acceptance are outstanding. The worker must not be represented as already generating live editions.
- Unresolved operational/product decisions include structured bibliography provider; source format and source path/move behavior; backup destination/retention/encryption/key recovery; and exact solution-protection threat model. See PRODUCT and DECISIONS.

## Documentation inconsistencies to resolve

Treat `docs/PRODUCT.md`, accepted rows in `docs/DECISIONS.md`, ADRs `0003`–`0005`, and the detailed redesign/annotation docs as authoritative for current direction. Reconcile these stale statements before treating overview docs as accurate:

- Root `README.md` still says research graphs/problems are unimplemented, the SDK is awaiting comparison, the Claude adapter is the current option, and the worker is unconfigured in terms that predate later implementation.
- `AGENTS.md` still instructs that the £20 multi-provider comparison is authorized, although the comparison was explicitly superseded and no spend occurred. Amend the guardrail to say it is unused, retired, and not blanket authorization for paid calls.
- `backend/README.md` contains detailed, runnable Claude worker setup beside the selected Google foundation. Clearly label it retired/historical or remove it from the supported path, and ensure the main docs do not suggest Claude is the chosen provider.
- `docs/IMPLEMENTATION.md` contains dated historical checkpoints with old test counts/statuses. Keep them as history, but distinguish them visibly from the current snapshot and current acceptance checklist.
- `docs/ARCHITECTURE.md` is explicitly a proposal/baseline and has some open source-file behavior; update its status only when implemented evidence supports doing so.

## Worktree caution at handoff creation

At the time this file was prepared, Git showed an untracked directory `study-content/Academic Resources/` containing a large set of user-owned PDFs and images. Do not stage, commit, upload, reformat, or move it as part of routine documentation work. The source materials belong outside Git under the privacy decision. Confirm whether this is an intentional local source import and keep them excluded.

## Suggested skills for the next session

- `codebase-design` for sharpening the boundary between local study UI, persistent records, and pre-render agent jobs.
- `domain-modeling` for keeping annotation, edition, check, signoff, work, claim, and evidence terminology coherent.
- `research` for current primary-source research on Google Agent Runtime and scholarly metadata providers; record findings in `docs/research/`.
- `pdf` for inspecting/rendering annotated source PDFs or checking native PDF processing visually.
- `code-review` before claiming a completed implementation slice or publishing a larger change.
- `diagnosing-bugs` for reported failures, and `tdd` if the user requests test-first implementation.

## Recommended next actions

1. Recheck `git status`, remote branch, and whether the untracked Academic Resources directory is intentionally local; keep it out of commits.
2. Reconcile README, AGENTS, backend README, and historical implementation status with the accepted Google ADK direction and current functionality.
3. Present the reader and literature-map prototypes for user review, then iterate from their feedback. Do not treat mock graph relationships as research facts.
4. Continue a concrete implementation slice only after checking its acceptance criteria in PRODUCT and IMPLEMENTATION. Keep Google calls disabled until deployment, explicit user authorization, budgets, and privacy settings are ready.
5. Update the decision log/implementation evidence as each decision or acceptance check changes; commit only intended code/docs and push only after verifying no source corpus or runtime data is staged.
