"""Ordered, additive SQLite schema migrations.

The legacy schema is still created by :class:`backend.store.Store`.  New schema
changes belong here so an existing study database can be upgraded without
dropping or reinterpreting user data.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


V2_CHAPTER_AND_LITERATURE = Migration(1, "chapter_editions_and_literature_maps", (
    """CREATE TABLE source_scopes(
      id TEXT PRIMARY KEY,
      source_id TEXT NOT NULL REFERENCES sources(id),
      parent_scope_id TEXT REFERENCES source_scopes(id),
      scope_kind TEXT NOT NULL CHECK(scope_kind IN ('document','paper','chapter','custom_range')),
      title TEXT NOT NULL,
      ordinal INTEGER NOT NULL,
      start_locator TEXT NOT NULL,
      end_locator TEXT NOT NULL,
      detection_method TEXT NOT NULL,
      confirmed_at TEXT NOT NULL,
      UNIQUE(source_id,parent_scope_id,ordinal)
    )""",
    """CREATE TABLE chapter_editions(
      id TEXT PRIMARY KEY,
      scope_id TEXT NOT NULL REFERENCES source_scopes(id),
      revision INTEGER NOT NULL,
      source_sha256 TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status='complete'),
      package_hash TEXT NOT NULL,
      publication_key TEXT NOT NULL UNIQUE,
      generator TEXT NOT NULL,
      model TEXT NOT NULL,
      prompt_version TEXT NOT NULL,
      skill_versions TEXT NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(scope_id,revision)
    )""",
    """CREATE TABLE edition_blocks(
      id TEXT PRIMARY KEY,
      edition_id TEXT NOT NULL REFERENCES chapter_editions(id) ON DELETE CASCADE,
      stable_key TEXT NOT NULL,
      parent_block_id TEXT REFERENCES edition_blocks(id),
      ordinal INTEGER NOT NULL,
      block_kind TEXT NOT NULL CHECK(block_kind IN
        ('heading','paragraph','equation','figure','table','list','example','exercise','footnote')),
      source_content TEXT NOT NULL,
      source_locator TEXT NOT NULL,
      content_hash TEXT NOT NULL,
      metadata TEXT NOT NULL,
      UNIQUE(edition_id,stable_key),
      UNIQUE(edition_id,ordinal)
    )""",
    """CREATE TABLE edition_annotations(
      id TEXT PRIMARY KEY,
      edition_id TEXT NOT NULL REFERENCES chapter_editions(id) ON DELETE CASCADE,
      stable_key TEXT NOT NULL,
      origin TEXT NOT NULL CHECK(origin IN ('historical','generated','learner')),
      intent TEXT NOT NULL,
      visual_role TEXT NOT NULL,
      placement TEXT NOT NULL CHECK(placement IN
        ('inline_after','interlinear','near_margin','overlay','collapsed_detail')),
      body TEXT NOT NULL,
      payload TEXT NOT NULL,
      importance TEXT NOT NULL,
      confidence REAL,
      provenance TEXT NOT NULL,
      metadata TEXT NOT NULL,
      UNIQUE(edition_id,stable_key)
    )""",
    """CREATE TABLE annotation_anchors(
      annotation_id TEXT NOT NULL REFERENCES edition_annotations(id) ON DELETE CASCADE,
      ordinal INTEGER NOT NULL,
      anchor_kind TEXT NOT NULL CHECK(anchor_kind IN
        ('block','quote','formula','figure_region','gap')),
      block_id TEXT REFERENCES edition_blocks(id),
      after_block_id TEXT REFERENCES edition_blocks(id),
      before_block_id TEXT REFERENCES edition_blocks(id),
      exact_quote TEXT,
      prefix TEXT,
      suffix TEXT,
      formula_label TEXT,
      segment_hint TEXT,
      bbox TEXT,
      PRIMARY KEY(annotation_id,ordinal)
    )""",
    """CREATE TABLE checkable_items(
      id TEXT PRIMARY KEY,
      edition_id TEXT NOT NULL REFERENCES chapter_editions(id) ON DELETE CASCADE,
      stable_key TEXT NOT NULL,
      ordinal INTEGER NOT NULL,
      item_kind TEXT NOT NULL CHECK(item_kind IN
        ('claim','equation_group','proof_move','definition','paragraph_cluster')),
      label TEXT NOT NULL,
      anchor_spec TEXT NOT NULL,
      material_hash TEXT NOT NULL,
      UNIQUE(edition_id,stable_key),
      UNIQUE(edition_id,ordinal)
    )""",
    """CREATE TABLE study_checks_v2(
      id TEXT PRIMARY KEY,
      checkable_item_id TEXT NOT NULL REFERENCES checkable_items(id),
      understood INTEGER NOT NULL CHECK(understood IN (0,1)),
      checked_at TEXT NOT NULL,
      carried_from_check_id TEXT REFERENCES study_checks_v2(id),
      reconfirmation_reason TEXT NOT NULL
    )""",
    "CREATE INDEX idx_source_scopes_source ON source_scopes(source_id,ordinal)",
    "CREATE INDEX idx_chapter_editions_scope ON chapter_editions(scope_id,revision DESC)",
    "CREATE INDEX idx_checks_v2_item ON study_checks_v2(checkable_item_id,checked_at DESC)",
    """CREATE TABLE works(
      id TEXT PRIMARY KEY,
      identity_key TEXT NOT NULL UNIQUE,
      work_type TEXT NOT NULL CHECK(work_type IN ('paper','book','thesis','notes','proceedings','other')),
      title TEXT NOT NULL,
      authors TEXT NOT NULL,
      year INTEGER,
      venue TEXT NOT NULL,
      doi TEXT,
      arxiv_id TEXT,
      isbn TEXT,
      external_ids TEXT NOT NULL,
      url TEXT,
      abstract TEXT NOT NULL,
      metadata_provenance TEXT NOT NULL,
      created_at TEXT NOT NULL
    )""",
    """CREATE TABLE source_works(
      source_id TEXT NOT NULL REFERENCES sources(id),
      work_id TEXT NOT NULL REFERENCES works(id),
      PRIMARY KEY(source_id,work_id)
    )""",
    """CREATE TABLE paper_analyses(
      id TEXT PRIMARY KEY,
      focal_work_id TEXT NOT NULL REFERENCES works(id),
      edition_id TEXT REFERENCES chapter_editions(id),
      revision INTEGER NOT NULL,
      status TEXT NOT NULL CHECK(status='complete'),
      package_hash TEXT NOT NULL,
      generator TEXT NOT NULL,
      model TEXT NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(focal_work_id,revision)
    )""",
    """CREATE TABLE paper_records(
      id TEXT PRIMARY KEY,
      analysis_id TEXT NOT NULL REFERENCES paper_analyses(id) ON DELETE CASCADE,
      stable_key TEXT NOT NULL,
      record_type TEXT NOT NULL CHECK(record_type IN
        ('section_summary','contribution','result','method','assumption','limitation','notation')),
      label TEXT NOT NULL,
      claim TEXT NOT NULL,
      section_label TEXT NOT NULL,
      locator TEXT NOT NULL,
      metadata TEXT NOT NULL,
      UNIQUE(analysis_id,stable_key)
    )""",
    """CREATE TABLE literature_maps(
      id TEXT PRIMARY KEY,
      focal_work_id TEXT NOT NULL REFERENCES works(id),
      analysis_id TEXT NOT NULL REFERENCES paper_analyses(id),
      revision INTEGER NOT NULL,
      status TEXT NOT NULL CHECK(status='complete'),
      package_hash TEXT NOT NULL,
      publication_key TEXT NOT NULL UNIQUE,
      research_scope TEXT NOT NULL,
      cutoff_reason TEXT NOT NULL,
      provider_provenance TEXT NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(focal_work_id,revision)
    )""",
    """CREATE TABLE literature_map_works(
      map_id TEXT NOT NULL REFERENCES literature_maps(id) ON DELETE CASCADE,
      work_id TEXT NOT NULL REFERENCES works(id),
      roles TEXT NOT NULL,
      importance_reason TEXT NOT NULL,
      lane TEXT NOT NULL CHECK(lane IN
        ('focal','foundation','predecessor','contemporary','downstream','explanatory')),
      PRIMARY KEY(map_id,work_id)
    )""",
    """CREATE TABLE research_evidence_v2(
      id TEXT PRIMARY KEY,
      map_id TEXT NOT NULL REFERENCES literature_maps(id) ON DELETE CASCADE,
      stable_key TEXT NOT NULL,
      work_id TEXT REFERENCES works(id),
      source_id TEXT REFERENCES sources(id),
      evidence_kind TEXT NOT NULL CHECK(evidence_kind IN
        ('direct_text','bibliographic_metadata','provider_metadata')),
      locator TEXT NOT NULL,
      quote TEXT NOT NULL,
      url TEXT,
      provider_identifier TEXT,
      retrieved_at TEXT,
      metadata TEXT NOT NULL,
      UNIQUE(map_id,stable_key)
    )""",
    """CREATE TABLE paper_record_evidence(
      record_id TEXT NOT NULL REFERENCES paper_records(id) ON DELETE CASCADE,
      evidence_id TEXT NOT NULL REFERENCES research_evidence_v2(id),
      PRIMARY KEY(record_id,evidence_id)
    )""",
    """CREATE TABLE literature_relationships(
      id TEXT PRIMARY KEY,
      map_id TEXT NOT NULL REFERENCES literature_maps(id) ON DELETE CASCADE,
      stable_key TEXT NOT NULL,
      from_work_id TEXT NOT NULL REFERENCES works(id),
      to_work_id TEXT NOT NULL REFERENCES works(id),
      relationship_class TEXT NOT NULL CHECK(relationship_class IN ('citation','intellectual')),
      relation_type TEXT NOT NULL,
      claim TEXT NOT NULL,
      epistemic_status TEXT NOT NULL CHECK(epistemic_status IN
        ('bibliographic_fact','stated','inferred')),
      citation_status TEXT NOT NULL CHECK(citation_status IN ('cites','does_not_cite','unknown')),
      confidence REAL,
      metadata TEXT NOT NULL,
      UNIQUE(map_id,stable_key),
      UNIQUE(map_id,from_work_id,to_work_id,relationship_class,relation_type)
    )""",
    """CREATE TABLE literature_relationship_contexts(
      relationship_id TEXT NOT NULL REFERENCES literature_relationships(id) ON DELETE CASCADE,
      ordinal INTEGER NOT NULL,
      section_label TEXT NOT NULL,
      paper_record_id TEXT REFERENCES paper_records(id),
      source_anchor TEXT NOT NULL,
      PRIMARY KEY(relationship_id,ordinal)
    )""",
    """CREATE TABLE literature_relationship_evidence(
      relationship_id TEXT NOT NULL REFERENCES literature_relationships(id) ON DELETE CASCADE,
      evidence_id TEXT NOT NULL REFERENCES research_evidence_v2(id),
      PRIMARY KEY(relationship_id,evidence_id)
    )""",
    "CREATE INDEX idx_literature_maps_focal ON literature_maps(focal_work_id,revision DESC)",
    "CREATE INDEX idx_literature_relationships_map ON literature_relationships(map_id)",
))


V2_SCOPE_ORDER = Migration(2, "enforce_top_level_scope_order", (
    "CREATE UNIQUE INDEX idx_source_scopes_top_order ON source_scopes(source_id,ordinal) WHERE parent_scope_id IS NULL",
))


V2_RELATIONSHIP_GUARDS = Migration(3, "guard_work_only_relationship_semantics", (
    """CREATE TRIGGER validate_literature_relationship_insert
    BEFORE INSERT ON literature_relationships
    WHEN
      (NEW.relationship_class='citation' AND
        (NEW.relation_type NOT IN ('cites','cited_by') OR
         NEW.epistemic_status!='bibliographic_fact' OR NEW.citation_status!='cites'))
      OR
      (NEW.relationship_class='intellectual' AND
        (NEW.relation_type NOT IN ('uses_result_from','uses_method_from','extends','applies',
          'generalises','contrasts','replicates','corrects') OR
         NEW.epistemic_status NOT IN ('stated','inferred')))
      OR NOT EXISTS(SELECT 1 FROM literature_map_works
                    WHERE map_id=NEW.map_id AND work_id=NEW.from_work_id)
      OR NOT EXISTS(SELECT 1 FROM literature_map_works
                    WHERE map_id=NEW.map_id AND work_id=NEW.to_work_id)
    BEGIN
      SELECT RAISE(ABORT,'invalid literature relationship class, semantics, or work membership');
    END""",
    """CREATE TRIGGER validate_literature_relationship_update
    BEFORE UPDATE ON literature_relationships
    WHEN
      (NEW.relationship_class='citation' AND
        (NEW.relation_type NOT IN ('cites','cited_by') OR
         NEW.epistemic_status!='bibliographic_fact' OR NEW.citation_status!='cites'))
      OR
      (NEW.relationship_class='intellectual' AND
        (NEW.relation_type NOT IN ('uses_result_from','uses_method_from','extends','applies',
          'generalises','contrasts','replicates','corrects') OR
         NEW.epistemic_status NOT IN ('stated','inferred')))
      OR NOT EXISTS(SELECT 1 FROM literature_map_works
                    WHERE map_id=NEW.map_id AND work_id=NEW.from_work_id)
      OR NOT EXISTS(SELECT 1 FROM literature_map_works
                    WHERE map_id=NEW.map_id AND work_id=NEW.to_work_id)
    BEGIN
      SELECT RAISE(ABORT,'invalid literature relationship class, semantics, or work membership');
    END""",
))


MIGRATIONS = (V2_CHAPTER_AND_LITERATURE, V2_SCOPE_ORDER, V2_RELATIONSHIP_GUARDS)


def run_migrations(db: sqlite3.Connection) -> None:
    """Apply every unapplied migration transactionally and in order."""
    db.execute("""CREATE TABLE IF NOT EXISTS schema_migrations(
      version INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      applied_at TEXT NOT NULL
    )""")
    applied = {int(row[0]) for row in db.execute("SELECT version FROM schema_migrations")}
    for migration in MIGRATIONS:
        if migration.version in applied:
            continue
        try:
            db.execute("BEGIN IMMEDIATE")
            for statement in migration.statements:
                db.execute(statement)
            db.execute("INSERT INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",
                       (migration.version, migration.name, _now()))
            db.commit()
        except Exception:
            db.rollback()
            raise

