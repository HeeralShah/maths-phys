---
status: proposed
---

# Model knowledge as statements with typed, provenance-carrying edges

Make the **statement** (definition, theorem, lemma, example, exercise, and so on) the unit of the knowledge base, stored in `study.sqlite3` beside the library catalogue of ADR 0008. Proofs, relations between statements, concept links and Lean links all hang off statements. The design, SQL and tests are in [KNOWLEDGE-SCHEMA.md](../KNOWLEDGE-SCHEMA.md).

- **Every row records where it came from.** Statements and proofs get a `provenance` row (file hash, page range, quote, method, extractor, confidence). Edges record who asserted them and which provenance row supports them.
- **Extracted is not reviewed.** Agent output is stored as a claim; `reviewed_at` is set only after a human checks it against the page.
- **Source and normalised notation are separate columns,** with the difference noted, as the repo guardrails require.
- **Lean fidelity is separate from Lean status.** A statement that compiles may still be weaker or different from the book's. Only `status` in (`proved`, `mathlib`) with `fidelity = 'matches'` counts as formally verified.
- **Learner state is separate from content,** in `statement_study`, consistent with ADR 0001.
- **The change is additive** and applies after the ADR 0008 schema. The vault stays canonical for prose; concepts only point to vault notes.

## Consequences

- A statement is tied to one work. The same result in two books is two statements joined by an `equivalent_to` edge.
- Dependency edges can be wrong. The unreviewed state is queryable, so checks and dashboards can show how much of the graph is trusted.
- `layout_object_id` cannot be a foreign key into `derived.sqlite3`; the application must verify it.
- Section structure, full-text search, concept extraction and the migration number are not designed here.
- Status is proposed. The vocabularies (statement kinds, relations, Lean statuses) are cheap to change before any migration is written.
