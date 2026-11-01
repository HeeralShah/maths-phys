# Product requirements

Status: requirements captured; the first implementation is being corrected around the chapter and literature-map models. Statements labeled **Accepted** reflect user-directed product behavior. **Proposed** describes a working implementation default pending validation. **Open** identifies a decision that must be settled before dependent implementation.

## Product goal

Build a private personal browser application for studying mathematics and physics from the user's own sources. Keep the experience local-first, preserve the existing Obsidian vault, and make paid/agent work visible and explicitly initiated. Scope includes all listed v1 capabilities; none are designated as a later release.

## Requirements

### R1. Source library and editions — Accepted

- The user can add source files and their metadata. Uploading a source does not automatically invoke an agent or incur a paid preparation action.
- The user explicitly selects and confirms one preparation scope: normally a complete chapter, or the whole document when it is already a chapter or paper. Physical pages are provenance and boundary locators, not independent preparation products.
- A chapter edition preserves the source's original content, ordering, and notation as ordered source blocks. Paragraph layout may be reflowed for readability.
- Generated comments remain a separate anchored layer. Short explanations and intuition appear at the passage they illuminate; derivation bridges appear between the formula lines they connect; long optional detail may collapse at that same anchor.
- Complete and validate the whole selected scope before publishing the rendered edition. Internal progress checkpoints may be persisted; page-by-page or otherwise partial output must not be published or presented as complete.
- Retain source identity and provenance through the reading edition and later synthesis.

Acceptance: adding metadata alone performs no generation; explicit preparation produces one complete chapter edition with resolvable anchors, source links, and original ordering; interrupted generation leaves the prior complete revision readable and cannot masquerade as a finished edition.

### R2. Study state and visual marking — Accepted

- Support these visual families: **green** unclear, error, or foreign reference; **yellow/orange/pink plus red/rust text** explanation, intermediate work, mini-proof, or interpretation; **blue** learner-understood; **purple** source exercise.
- Store semantic annotation intent separately from colour. Generated annotations can explain or resolve a green issue but never erase the issue that prompted them.
- Only the learner may mark a checkable item blue/understood. An agent must never infer or generate current understanding.
- Imported legacy annotations retain their historical status and dates. Do not silently reinterpret them as current study assessments.
- In v1, record initial dated checks only. Later recall checks use quiet recall and a refresher of no more than one page for material currently being studied.
- Do not promise time estimates or add time-prediction badges. Difficulty is an agent's subjective assessment grounded in stated facts, with those facts shown as the reason.

Acceptance: every annotation/check is distinguishable as imported historical, agent-generated, or current learner state; comments resolve to exact source anchors; checkable items can be ticked independently inside a chapter; v1 records initial dated checks only; a current refresher stays at or below one page and only includes current-study material; agent-assessed difficulty shows its factual basis and has no predicted-duration field.

### R3. Clarification chat — Accepted

- Submitting a clarification chat starts a background revision job for the study edition.
- After it completes, the user explicitly refreshes the displayed edition.
- Refresh preserves the user's current check state and place in the material.
- Chat is not permission for implicit synthesis or a general background rewrite.

Acceptance: chat submission starts the revision job; the user explicitly refreshes after completion; refresh preserves checks and reading position.

### R4. Problems and progressive assistance — Accepted

- Provide prerecorded assistance in this sequence: orientation, small hint, strong hint, partial solution, full solution.
- Exclude solutions from ordinary context and search until the user explicitly reveals the applicable assistance level. A hint reveal is not an agent invocation.
- Problems are source-only inline, at the end of a source, or in a set. Record subject, prerequisite links, novelty, combination of ideas, workload, provenance, and learner experience.
- Novelty and workload are qualitative descriptors. Difficulty is an agent's subjective assessment grounded in stated facts; never predict time needed.

Acceptance: unopened assistance is absent from ordinary retrieval; each reveal displays only the chosen level; problem metadata supports all placements and stated dimensions with source provenance.

### R5. Research, graphs, and evidence — Accepted

- The v1 research space includes literature, results, assumptions, and an explorable evidence-backed literature map centred on one focal paper.
- Visible map nodes are bibliographic works only. Sections, results, assumptions, contributions, and methods remain paper-analysis records that filter or explain external relationships without becoming same-document graph nodes.
- Preserve a strict distinction between a bare citation fact and an evidence-backed claim that one work uses, extends, applies, generalises, corrects, or influences another.
- Apply Keshav's three-pass reading approach to reconstruct a paper's assumptions and identify downstream influential works. Preserve the evidence supporting reconstructed assumptions and influence links.
- Graph browsing, expansion, and inspection are local/read-only actions. They never implicitly start an agent or paid web work.
- Any web research or agent synthesis must be initiated through a clearly labeled explicit action and return source-linked evidence.

Acceptance: every visible node is a work; every relationship can be traced to evidence and exposes whether it is bibliographic fact, author-stated relationship, or inference; subsection filtering creates no internal nodes; expansion does not call an agent.

### R6. Atlas synthesis and signoff — Accepted

- Signoff explicitly starts background synthesis for the signed-off subsection or chapter. Synthesis incorporates checked material only.
- Later signoffs update the synthesis incrementally, retaining prior links and provenance.
- Atlas notes are small, multi-source canonical notes using one notation. After signoff, the system may improve, create, or merge notes automatically.
- Preserve manually expressed intent and support human-readable Git commit messages for significant synthesis edits.
- Unchecking a source passage does not delete or silently undo its existing Atlas contribution. A material revision to already-signed-off content requires reconfirmation before changing the synthesis.
- Preserve the original source notation in its reading edition; use normalized notation in canonical Atlas notes, with provenance connecting the two.

Acceptance: no signoff means no synthesis; synthesis excludes unchecked content; incremental updates preserve provenance; uncheck retains the current Atlas contribution; a material revision is held for reconfirmation.

### R7. Legacy vault and historical study — Accepted

- Preserve the current Obsidian workspace and useful configuration. Import/link existing content without destructive migration.
- Imported legacy study marks remain historical and unassessed for current study unless the user explicitly checks them again.
- Keep human-readable topic canon in Markdown/Obsidian and preserve source identity and notation.

Acceptance: migration is additive and reversible; old marks are dated/historical and do not satisfy current checks by implication.

### R8. Privacy, persistence, and recovery — Accepted direction; implemented defaults recorded

- Use private Git for source notes, docs, code, and schemas. Do not put original PDFs, local databases, secrets, environments, caches, or temporary output in Git.
- Persist study state, results, and graph data in SQLite; persist canonical topic notes as Markdown in the Obsidian vault.
- Provide backups that include the SQLite database, associated assets, and required encryption keys. The exact backup destination, key recovery, retention, and restore procedure remain open.
- The implemented local protection uses Windows DPAPI (or a private Fernet key elsewhere), deliberate assistance reveal and private validated backup archives. See the decision log and operational guide for recovery limits; portable Windows key recovery remains unresolved.

Acceptance: an export/restore procedure is documented and demonstrated before v1 completion; restored state includes database plus assets; secrets remain excluded from Git; exact encryption and backup decisions are recorded.

## Explicit invocation boundary

An operation that can invoke an agent, perform paid web research, or change durable synthesized study content needs a direct user action naming that operation. The following never implicitly invoke it: browsing, opening a graph node, graph expansion, navigation, check display, and hint reveal. Explicit actions include source preparation, submitting clarification chat, refreshing a revised edition, starting research, and signoff synthesis.

## Open product questions

1. Which backup destination and recovery/key custody model should be used?
2. What exact encryption scope and solution-reveal rules are desired?
3. Which structured bibliographic provider should supply citation topology alongside Google web research?
4. What source formats beyond PDFs and Markdown must v1 ingest?

These questions do not defer the listed v1 features. Our custom Google ADK agent on the managed Agent Runtime is selected, but paid execution remains opt-in until credentials and per-job cost controls are configured. Antigravity is not an application dependency. No provider trial or paid generation has run.
