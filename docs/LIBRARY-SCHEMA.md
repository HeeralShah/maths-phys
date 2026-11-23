# Library catalogue schema

Status: proposed design, with executable SQL and tests. Nothing here is wired into `backend/migrations` yet. Decision record: [ADR 0008](adr/0008-catalogue-the-library-in-sqlite-with-a-rebuildable-derived-database.md). Storage of the file bytes is in [ADR 0006](adr/0006-store-sources-in-content-addressed-object-storage.md); page geometry in [ADR 0007](adr/0007-place-annotations-using-extracted-page-geometry.md).

The SQL is in [docs/schema/library-study.sql](schema/library-study.sql) and [docs/schema/library-derived.sql](schema/library-derived.sql). [backend/test_library_schema.py](../backend/test_library_schema.py) applies the study SQL on top of the real, fully migrated study database (with a `works` row that already exists) and checks the constraints. 13 tests pass.

## Two database files

| File | Holds | Backed up? |
|---|---|---|
| `study.sqlite3` | Everything authoritative: existing study state plus the new catalogue (files, locations, import batches, works, topics, tags) | Yes |
| `derived.sqlite3` | Page text with full-text search, page geometry, extraction runs | No. Rebuild from the source files |

Both are keyed by file hash. SQLite cannot enforce a foreign key across files, so the application checks that every `sha256` in `derived.sqlite3` exists in `files`. The two can be attached to one connection for joins.

## What is added to `study.sqlite3`

| Table | Purpose | Notes |
|---|---|---|
| `files` | One row per unique byte content | Key is `sha256`. `storage_key` is a generated column (`sources/<sha256>.<ext>`), so it cannot drift from the hash. Records `text_layer` and `has_annotations`, and `derived_from_sha256` for converted files |
| `import_batches` | One row per import run (for example a Dropbox zip) | Gives every file a provenance trail |
| `file_locations` | Where a file was seen or stored | `kind` is `origin`, `bucket` or `cache`. `origin` rows keep the original Dropbox path, including duplicates |
| `works` (existing) | Bibliographic identity | Gains `material_kind` and `curation_status` by `ALTER TABLE ADD COLUMN`, so no table rebuild is needed and slides are supported |
| `work_files` | Links a work to its files | `role` is primary, alternate edition, supplement or converted |
| `source_files` | Links a study source to a file | Making a study source from a catalogued file is the explicit step (D-03) |
| `topics`, `work_topics` | Shallow topic hierarchy | Unique among siblings; one primary topic per work. Holds no prose, with an optional vault note path |
| `tags`, `work_tags` | Free-form labels | Case-insensitive; for course codes, years and so on |
| `work_links` | Relations between works | `recommends`, `covers_same_material`, `companion_of`, `part_of`, `supersedes`. Example: the Dafermos notes recommend Lee |

## What is in `derived.sqlite3`

| Table | Purpose | Notes |
|---|---|---|
| `extraction_runs` | One row per extractor run on a file | Makes failures and versions visible |
| `page_text`, `page_fts` | Page text and an FTS5 index | External-content index kept in sync by triggers, with Porter stemming |
| `layout_pages` | Page size, rotation, extractor and version, status | Status distinguishes `no_text_layer` from `failed` |
| `layout_objects` | Block, line, image, drawing and historical-mark rectangles | Normalised 0 to 1, origin top-left; geometry is checked |
| `layout_words` | One compressed JSON blob of word boxes per page | Avoids about 500 rows per page |

## How it connects to what exists

- `sources` (study registrations) links to files through `source_files`. The old `metadata.local_file` JSON stays readable and can be backfilled.
- `works` and `source_works` are unchanged apart from the two new columns.
- `chapter_editions.source_sha256` already records a hash, so editions line up with `files.sha256` without change.
- A PDF's outline could populate `source_scopes` automatically (`detection_method = 'pdf_outline'`). Lee's outline has 288 entries, and the reader redesign already wants structural scope detection. Not designed here.

## Defaults applied, awaiting confirmation

These were open questions. The SQL assumes the recommended answer, which is cheap to change before anything is migrated.

1. **Two files** (study and derived), not one.
2. **Topics are a shallow hierarchy plus free tags.**
3. **PDF only for v1.** Other formats (slides, EPUB, DjVu) are converted to PDF first; the converted file records `derived_from_sha256` and the work links it with role `converted`.
4. **Metadata is inferred, then curated.** Fill from PDF properties and DOI or ISBN lookup, mark `curation_status = 'inferred'`, and flip to `curated` when you confirm it. This matters because filenames and embedded titles are unreliable (for example `neessnmeiwseis.pdf`).

## Not yet designed

- How annotations, editions and the layout map link (placement results back to `layout_objects`).
- Backfilling `source_files` and `source_scopes` from existing sources.
- A migration number and the derived database's own migration chain. The study migration would be version 4, after the three that exist.
