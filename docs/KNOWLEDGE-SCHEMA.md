# Knowledge base schema

Status: proposed design, with executable SQL and tests. Nothing here is wired into `backend/migrations` yet. Decision record: [ADR 0009](adr/0009-model-knowledge-as-statements-with-typed-provenance-edges.md). It builds on the library catalogue in [LIBRARY-SCHEMA.md](LIBRARY-SCHEMA.md) (ADR 0008).

The SQL is in [docs/schema/knowledge-base.sql](schema/knowledge-base.sql). It applies after `library-study.sql`, on top of the real migrated study database. [backend/test_knowledge_schema.py](../backend/test_knowledge_schema.py) checks the constraints and views. 7 tests pass.

## Idea

The unit of knowledge is a **statement**: a definition, theorem, lemma and so on, as printed in a work. Every statement, proof and relation records where it was read (file, page, quote) and who or what extracted it. Lean links record whether a formal counterpart exists and, separately, whether it says what the book says.

## Tables

| Table | Purpose | Notes |
|---|---|---|
| `statements` | One row per definition, theorem, example, exercise and so on | `UNIQUE(work_id, label)` and `UNIQUE(work_id, ordinal)`. Holds `source_tex` (the book's notation) and `normalized_tex` (canonical Atlas notation), as AGENTS.md requires |
| `proofs` | Proofs of a statement | Several allowed: `book`, `alternative`, `sketch`, `own` |
| `provenance` | Where a statement or proof was read | Exactly one subject (CHECK). Records file hash, page range, section path, quote, method, extractor, confidence, and `reviewed_at` (null until a human checks it) |
| `statement_edges` | Typed relations between statements | `uses_definition`, `uses_result`, `generalises`, `special_case_of`, `equivalent_to`, `corollary_of`, `converse_of`, `refines`, `cites`. Each carries `asserted_by`, confidence, review time, and optionally the proof and provenance row that evidence it |
| `concepts`, `concept_edges` | Named ideas and prerequisites between them | `vault_note_path` links to the canonical Atlas note; the vault stays canonical |
| `statement_concepts` | Which statements define, are about, or mention a concept | |
| `lean_links` | Formal counterparts | `status` (does it compile or prove) and `fidelity` (does the Lean say what the book says) are separate columns. Records toolchain, Mathlib revision, axiom check and effort |
| `statement_study` | The learner's own state per statement | Kept apart from extracted content, so re-extraction never overwrites it (ADR 0001) |

Two views: `v_work_coverage` (per work: statements, definitions, results, human-reviewed, with Lean, formally verified) and `v_unformalised_dependencies` (dependencies with no faithful Lean counterpart: what to formalise first).

## How it connects

- `statements.work_id` references the existing `works`.
- `provenance.sha256` references `files` from the library schema, so provenance survives renames and duplicate copies.
- `provenance.layout_object_id` points into `derived.sqlite3` (ADR 0007). Without a foreign key across files, the application verifies it.
- An unreviewed agent edge or provenance row is a claim, not a fact: `reviewed_at` is the line between them.

## Deliberately open

- **Chapter-level structure.** Section and chapter rows are not modelled; `section_path` is text. A PDF outline could populate it.
- **Full-text search** over statements is not set up.
- **Concept extraction** (which concepts a statement defines) has no automated path designed.
- **Cross-work identity.** The same theorem in two books is two statements joined by `equivalent_to`. No merged "canonical theorem" entity yet.
- **Exercises and solutions** are statements of kind `exercise`, with proofs as `own`. Whether that is enough is untested.
- **Lean project location** is recorded per link (`project_path`); the project itself is not decided.
- A migration number and the link to annotations and editions are not designed.
