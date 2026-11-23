-- PROPOSED additive migration for study.sqlite3 (see docs/LIBRARY-SCHEMA.md and ADR 0008).
-- Not yet wired into backend/migrations. Applies on top of the existing schema:
-- it reads `sources` and `works` and adds columns to `works`; it changes nothing else.

-- One row per unique byte content. The storage key is derived, so it cannot drift from the hash.
CREATE TABLE files(
  sha256 TEXT PRIMARY KEY
    CHECK(length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
  size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
  ext TEXT NOT NULL CHECK(length(ext) BETWEEN 1 AND 8 AND ext NOT GLOB '*[^a-z0-9]*'),
  mime_type TEXT,
  page_count INTEGER CHECK(page_count IS NULL OR page_count >= 0),
  text_layer TEXT NOT NULL DEFAULT 'unknown'
    CHECK(text_layer IN ('unknown', 'present', 'partial', 'absent')),
  has_annotations INTEGER CHECK(has_annotations IS NULL OR has_annotations IN (0, 1)),
  derived_from_sha256 TEXT REFERENCES files(sha256),   -- e.g. a PDF converted from slides
  first_seen_at TEXT NOT NULL,
  storage_key TEXT GENERATED ALWAYS AS ('sources/' || sha256 || '.' || ext) VIRTUAL
);

-- One row per import run (for example one Dropbox zip). Gives every file a provenance trail.
CREATE TABLE import_batches(
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,                                  -- e.g. 'Academic Resources.zip'
  origin TEXT NOT NULL,                                 -- e.g. 'dropbox-zip'
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL CHECK(status IN ('running', 'complete', 'failed'))
);

-- Where a file has been seen or stored. 'origin' rows preserve the original Dropbox path.
CREATE TABLE file_locations(
  id INTEGER PRIMARY KEY,
  sha256 TEXT NOT NULL REFERENCES files(sha256),
  kind TEXT NOT NULL CHECK(kind IN ('origin', 'bucket', 'cache')),
  uri TEXT NOT NULL,
  batch_id TEXT REFERENCES import_batches(id),
  verified_at TEXT,
  UNIQUE(sha256, kind, uri)
);
CREATE INDEX idx_file_locations_file ON file_locations(sha256, kind);

-- `works` already exists (bibliographic identity). Add the two things the catalogue needs.
-- ALTER TABLE ... ADD COLUMN with a CHECK works without rebuilding the table.
ALTER TABLE works ADD COLUMN material_kind TEXT NOT NULL DEFAULT 'other'
  CHECK(material_kind IN ('book', 'lecture_notes', 'paper', 'slides', 'problem_sheet', 'thesis', 'other'));
ALTER TABLE works ADD COLUMN curation_status TEXT NOT NULL DEFAULT 'inferred'
  CHECK(curation_status IN ('inferred', 'curated'));

CREATE TABLE work_files(
  work_id TEXT NOT NULL REFERENCES works(id),
  sha256 TEXT NOT NULL REFERENCES files(sha256),
  role TEXT NOT NULL DEFAULT 'primary'
    CHECK(role IN ('primary', 'alternate_edition', 'supplement', 'converted')),
  PRIMARY KEY(work_id, sha256)
);
CREATE INDEX idx_work_files_file ON work_files(sha256);

-- A study source is created from a catalogued file by an explicit action (D-03).
CREATE TABLE source_files(
  source_id TEXT NOT NULL REFERENCES sources(id),
  sha256 TEXT NOT NULL REFERENCES files(sha256),
  PRIMARY KEY(source_id, sha256)
);

-- Filing structure. Topics are a shallow hierarchy; they hold no prose (the vault owns that).
CREATE TABLE topics(
  id TEXT PRIMARY KEY,
  parent_id TEXT REFERENCES topics(id),
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  atlas_note_path TEXT,                                 -- optional vault-relative link
  created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_topics_sibling_name ON topics(coalesce(parent_id, ''), name);

CREATE TABLE work_topics(
  work_id TEXT NOT NULL REFERENCES works(id),
  topic_id TEXT NOT NULL REFERENCES topics(id),
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0, 1)),
  PRIMARY KEY(work_id, topic_id)
);
CREATE UNIQUE INDEX idx_work_one_primary_topic ON work_topics(work_id) WHERE is_primary = 1;
CREATE INDEX idx_work_topics_topic ON work_topics(topic_id);

-- Free-form tags for cross-cutting labels (course codes, years, 'annotated').
CREATE TABLE tags(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE work_tags(
  work_id TEXT NOT NULL REFERENCES works(id),
  tag_id INTEGER NOT NULL REFERENCES tags(id),
  PRIMARY KEY(work_id, tag_id)
);

-- Relations between works, such as a set of notes recommending a textbook.
CREATE TABLE work_links(
  id INTEGER PRIMARY KEY,
  from_work_id TEXT NOT NULL REFERENCES works(id),
  to_work_id TEXT NOT NULL REFERENCES works(id),
  kind TEXT NOT NULL
    CHECK(kind IN ('recommends', 'covers_same_material', 'companion_of', 'part_of', 'supersedes')),
  note TEXT,
  created_at TEXT NOT NULL,
  CHECK(from_work_id <> to_work_id),
  UNIQUE(from_work_id, to_work_id, kind)
);
