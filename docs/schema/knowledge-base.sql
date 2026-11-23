-- PROPOSED additive migration for study.sqlite3 (see docs/KNOWLEDGE-SCHEMA.md and ADR 0009).
-- Not yet wired into backend/migrations. Apply AFTER docs/schema/library-study.sql: it references
-- `files` and `works`, and changes nothing that exists.
--
-- Model: a statement (definition, theorem, ...) is the unit of knowledge. Everything else hangs off it:
--   proofs        -> informal proofs of a statement, each with provenance
--   provenance    -> where in which file (page, section, quote) something was read, and who extracted it
--   edges         -> typed, provenance-carrying relations between statements (and between concepts)
--   concepts      -> named ideas that statements define or mention; link to the vault
--   lean_links    -> formal counterparts, with fidelity (does the Lean say what the book says?) kept
--                    separate from proof status (does it compile?)
--   statement_study -> the learner's own state; kept apart from the extracted content (ADR 0001)

CREATE TABLE concepts(
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE CHECK(slug = lower(slug) AND slug NOT GLOB '*[^a-z0-9-]*'),
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  vault_note_path TEXT,                  -- canonical Atlas note, if one exists (vault stays canonical)
  created_at TEXT NOT NULL
);

CREATE TABLE concept_edges(
  id INTEGER PRIMARY KEY,
  src_concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
  dst_concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
  relation TEXT NOT NULL CHECK(relation IN ('prerequisite_of', 'specialises', 'equivalent_to', 'related_to')),
  created_at TEXT NOT NULL,
  CHECK(src_concept_id <> dst_concept_id),
  UNIQUE(src_concept_id, dst_concept_id, relation)
);

-- One row per definition, theorem, lemma, ... as printed in a work.
CREATE TABLE statements(
  id TEXT PRIMARY KEY,
  work_id TEXT NOT NULL REFERENCES works(id),
  kind TEXT NOT NULL CHECK(kind IN (
    'definition', 'axiom', 'theorem', 'proposition', 'lemma', 'corollary', 'claim',
    'example', 'counterexample', 'exercise', 'notation', 'remark', 'conjecture')),
  label TEXT NOT NULL,                   -- as printed, e.g. 'Proposition 7.4' or 'Definition 1.1'
  ordinal INTEGER NOT NULL,              -- reading order within the work, for stable listing
  title TEXT,
  source_tex TEXT NOT NULL,              -- statement in the source's own notation (reading edition)
  normalized_tex TEXT,                   -- statement in canonical Atlas notation, once normalised
  notation_note TEXT,                    -- how source and normalized notation differ
  extraction_status TEXT NOT NULL DEFAULT 'extracted'
    CHECK(extraction_status IN ('extracted', 'reviewed', 'disputed')),
  created_at TEXT NOT NULL,
  UNIQUE(work_id, label),
  UNIQUE(work_id, ordinal)
);
CREATE INDEX statements_by_kind ON statements(work_id, kind);

-- A proof of a statement. A statement may have several (the book's, an alternative, a Lean-informed one).
CREATE TABLE proofs(
  id TEXT PRIMARY KEY,
  statement_id TEXT NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('book', 'alternative', 'sketch', 'own')),
  source_tex TEXT NOT NULL,
  normalized_tex TEXT,
  extraction_status TEXT NOT NULL DEFAULT 'extracted'
    CHECK(extraction_status IN ('extracted', 'reviewed', 'disputed')),
  created_at TEXT NOT NULL
);
CREATE INDEX proofs_by_statement ON proofs(statement_id);

-- Where something was read. Exactly one subject. The page range and quote let a reader (or a check)
-- find the original text again; layout_object_id points into derived.sqlite3 without a foreign key.
CREATE TABLE provenance(
  id INTEGER PRIMARY KEY,
  statement_id TEXT REFERENCES statements(id) ON DELETE CASCADE,
  proof_id TEXT REFERENCES proofs(id) ON DELETE CASCADE,
  sha256 TEXT NOT NULL REFERENCES files(sha256),
  page_start INTEGER NOT NULL CHECK(page_start >= 1),
  page_end INTEGER NOT NULL,
  section_path TEXT,                     -- e.g. '7 > 7.2 Convergence theorems'
  quote TEXT,                            -- short verbatim excerpt for re-finding and checking
  layout_object_id INTEGER,              -- derived.layout_objects.id; verified by the application
  method TEXT NOT NULL CHECK(method IN ('manual', 'pdf_text', 'agent', 'ocr')),
  extractor TEXT,                        -- tool or model name and version
  confidence REAL CHECK(confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  reviewed_at TEXT,                      -- null until a human has checked it against the page
  created_at TEXT NOT NULL,
  CHECK(page_end >= page_start),
  CHECK((statement_id IS NOT NULL) + (proof_id IS NOT NULL) = 1)
);
CREATE INDEX provenance_by_statement ON provenance(statement_id);
CREATE INDEX provenance_by_proof ON provenance(proof_id);
CREATE INDEX provenance_by_file ON provenance(sha256, page_start);

CREATE TABLE statement_concepts(
  statement_id TEXT NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
  concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('defines', 'about', 'mentions')),
  PRIMARY KEY(statement_id, concept_id, role)
);
CREATE INDEX statement_concepts_by_concept ON statement_concepts(concept_id);

-- Typed relation between statements. 'uses' means the proof or statement needs the target.
-- Each edge records where the relation was asserted and by whom; an unreviewed agent edge is a claim, not a fact.
CREATE TABLE statement_edges(
  id INTEGER PRIMARY KEY,
  src_statement_id TEXT NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
  dst_statement_id TEXT NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
  relation TEXT NOT NULL CHECK(relation IN (
    'uses_definition', 'uses_result', 'generalises', 'special_case_of',
    'equivalent_to', 'corollary_of', 'converse_of', 'refines', 'cites')),
  proof_id TEXT REFERENCES proofs(id) ON DELETE SET NULL,   -- the proof in which the dependency occurs
  evidence_provenance_id INTEGER REFERENCES provenance(id) ON DELETE SET NULL,
  asserted_by TEXT NOT NULL CHECK(asserted_by IN ('manual', 'agent', 'text_reference')),
  confidence REAL CHECK(confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  reviewed_at TEXT,
  created_at TEXT NOT NULL,
  CHECK(src_statement_id <> dst_statement_id),
  UNIQUE(src_statement_id, dst_statement_id, relation)
);
CREATE INDEX statement_edges_by_dst ON statement_edges(dst_statement_id, relation);

-- Formal counterpart in Lean. 'status' is whether it compiles/proves; 'fidelity' is whether the Lean
-- statement says what the book says. Compiling is not correctness, so the two are never merged.
CREATE TABLE lean_links(
  id INTEGER PRIMARY KEY,
  statement_id TEXT NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
  proof_id TEXT REFERENCES proofs(id) ON DELETE SET NULL,
  link_kind TEXT NOT NULL CHECK(link_kind IN ('own_formalisation', 'mathlib_equivalent', 'mathlib_partial')),
  lean_name TEXT NOT NULL,               -- fully qualified, e.g. 'MeasureTheory.lintegral_mono'
  project_path TEXT,                     -- Lake project folder (own_formalisation only)
  file_path TEXT,
  status TEXT NOT NULL CHECK(status IN ('statement_only', 'sorry', 'proved', 'mathlib', 'failed')),
  fidelity TEXT NOT NULL DEFAULT 'unchecked'
    CHECK(fidelity IN ('unchecked', 'matches', 'weaker', 'stronger', 'different')),
  fidelity_note TEXT,
  axioms_clean INTEGER CHECK(axioms_clean IS NULL OR axioms_clean IN (0, 1)),   -- from #print axioms
  lean_toolchain TEXT,
  mathlib_rev TEXT,
  effort_minutes INTEGER CHECK(effort_minutes IS NULL OR effort_minutes >= 0),
  checked_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(statement_id, lean_name)
);
CREATE INDEX lean_links_by_status ON lean_links(status, fidelity);

-- The learner's own state, kept apart from extracted content so re-extraction never touches it.
CREATE TABLE statement_study(
  statement_id TEXT PRIMARY KEY REFERENCES statements(id) ON DELETE CASCADE,
  state TEXT NOT NULL DEFAULT 'unseen'
    CHECK(state IN ('unseen', 'read', 'understood', 'can_reprove', 'formalised')),
  note TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

-- Per work: how much has been captured, checked and formalised.
CREATE VIEW v_work_coverage AS
SELECT s.work_id,
       COUNT(*) AS statements,
       SUM(s.kind = 'definition') AS definitions,
       SUM(s.kind IN ('theorem', 'proposition', 'lemma', 'corollary')) AS results,
       SUM(EXISTS(SELECT 1 FROM provenance p WHERE p.statement_id = s.id AND p.reviewed_at IS NOT NULL)) AS reviewed,
       SUM(EXISTS(SELECT 1 FROM lean_links l WHERE l.statement_id = s.id)) AS with_lean,
       SUM(EXISTS(SELECT 1 FROM lean_links l WHERE l.statement_id = s.id
                  AND l.status IN ('proved', 'mathlib') AND l.fidelity = 'matches')) AS formally_verified
FROM statements s
GROUP BY s.work_id;

-- Dependencies of a statement that have no faithful Lean counterpart yet: what to formalise first.
CREATE VIEW v_unformalised_dependencies AS
SELECT e.src_statement_id AS statement_id, e.dst_statement_id AS dependency_id, e.relation
FROM statement_edges e
WHERE e.relation IN ('uses_definition', 'uses_result')
  AND NOT EXISTS(SELECT 1 FROM lean_links l WHERE l.statement_id = e.dst_statement_id
                 AND l.status IN ('proved', 'mathlib') AND l.fidelity = 'matches');
