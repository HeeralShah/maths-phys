-- PROPOSED schema for derived.sqlite3 (see docs/LIBRARY-SCHEMA.md and ADR 0008).
-- Everything here is rebuildable from the source files, so this database is not backed up.
-- Rows are keyed by file hash (`sha256`), matching study.sqlite3 `files.sha256`. SQLite
-- cannot enforce a foreign key across database files, so the application checks that link.

-- One row per extractor run on a file, so failures and versions are visible.
CREATE TABLE extraction_runs(
  id INTEGER PRIMARY KEY,
  sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
  extractor TEXT NOT NULL,                              -- e.g. 'pymupdf'
  version TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('complete', 'partial', 'failed')),
  error TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  UNIQUE(sha256, extractor, version)
);

CREATE TABLE page_text(
  id INTEGER PRIMARY KEY,
  sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
  page INTEGER NOT NULL CHECK(page >= 1),
  text TEXT NOT NULL,
  UNIQUE(sha256, page)
);

-- Full-text index over page_text (external content, kept in sync by triggers).
CREATE VIRTUAL TABLE page_fts USING fts5(
  text, content = 'page_text', content_rowid = 'id', tokenize = 'porter unicode61'
);
CREATE TRIGGER page_text_ai AFTER INSERT ON page_text BEGIN
  INSERT INTO page_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER page_text_ad AFTER DELETE ON page_text BEGIN
  INSERT INTO page_fts(page_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER page_text_au AFTER UPDATE ON page_text BEGIN
  INSERT INTO page_fts(page_fts, rowid, text) VALUES ('delete', old.id, old.text);
  INSERT INTO page_fts(rowid, text) VALUES (new.id, new.text);
END;

-- Page geometry. Coordinates in layout_objects are normalised to the page (0 to 1, origin top-left).
CREATE TABLE layout_pages(
  sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
  page INTEGER NOT NULL CHECK(page >= 1),
  width_pt REAL NOT NULL CHECK(width_pt > 0),
  height_pt REAL NOT NULL CHECK(height_pt > 0),
  rotation INTEGER NOT NULL DEFAULT 0 CHECK(rotation IN (0, 90, 180, 270)),
  extractor TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('complete', 'no_text_layer', 'failed')),
  PRIMARY KEY(sha256, page)
);

CREATE TABLE layout_objects(
  id INTEGER PRIMARY KEY,
  sha256 TEXT NOT NULL,
  page INTEGER NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('block', 'line', 'image', 'drawing', 'historical_mark')),
  x0 REAL NOT NULL CHECK(x0 >= 0 AND x0 <= 1),
  y0 REAL NOT NULL CHECK(y0 >= 0 AND y0 <= 1),
  x1 REAL NOT NULL CHECK(x1 >= 0 AND x1 <= 1),
  y1 REAL NOT NULL CHECK(y1 >= 0 AND y1 <= 1),
  reading_order INTEGER,
  text_hash TEXT,
  CHECK(x0 < x1 AND y0 < y1),
  FOREIGN KEY(sha256, page) REFERENCES layout_pages(sha256, page) ON DELETE CASCADE
);
CREATE INDEX idx_layout_objects_page ON layout_objects(sha256, page, reading_order);

-- Word boxes are bulky, so each page's words are one compressed blob instead of ~500 rows.
CREATE TABLE layout_words(
  sha256 TEXT NOT NULL,
  page INTEGER NOT NULL,
  words_zlib_json BLOB NOT NULL,
  PRIMARY KEY(sha256, page),
  FOREIGN KEY(sha256, page) REFERENCES layout_pages(sha256, page) ON DELETE CASCADE
) WITHOUT ROWID;
