---
status: proposed
---

# Catalogue the library in SQLite, with a separate rebuildable derived database

Extend the existing study store (D-15) with a content-addressed catalogue: files keyed by SHA-256, where each file has been seen or stored, which import run brought it in, and how it relates to works, topics and tags. Keep large, rebuildable data (page text, full-text index, page geometry) in a second SQLite file, `derived.sqlite3`, that is not backed up. The design, SQL and tests are in [LIBRARY-SCHEMA.md](../LIBRARY-SCHEMA.md).

- **A catalogue entry is not a study source.** Importing creates works and files only. Creating a `source` from a file is a separate explicit step, consistent with D-03.
- **Derived data is keyed by file hash, not by source.** Duplicate copies share one text index and one layout map.
- **The storage key is a generated column**, so it cannot disagree with the hash and extension.
- **The change is additive.** Existing tables stay readable; `works` gains two columns using `ALTER TABLE ADD COLUMN`, which avoids a table rebuild.
- **Topics are a shallow hierarchy plus free tags,** and hold no prose. The vault stays canonical for topic notes.
- **PDF only for v1.** Other formats are converted first and linked to their original.
- **Metadata is inferred, then curated,** because filenames and embedded titles cannot be trusted.

## Consequences

- Backup covers `study.sqlite3` only. The derived file is regenerated from the source files, which also resolves how large layout data affects backup size.
- A cross-file link cannot be a foreign key. The application must verify that each derived `sha256` exists in `files`.
- The study migration would be version 4. The derived database needs its own migration chain.
- Refines P-04 and O-05, and supplies the catalogue that ADR 0006 assumes.
- Status is proposed because four defaults (two files, topic structure, formats, metadata policy) await confirmation. They are cheap to change before any migration is written.
