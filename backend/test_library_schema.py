"""Checks that the proposed library schema (docs/schema/*.sql) applies cleanly and behaves as designed.

The study-side SQL is applied on top of the real, fully migrated study database, with a
pre-existing `works` row, to prove the additive ALTER TABLE statements work on populated data.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
import zlib
from pathlib import Path

from backend.store import Store

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "docs" / "schema"
SHA_A = "a" * 64
SHA_B = "b" * 64


def work_row(work_id: str, identity: str) -> tuple:
    return (work_id, identity, "book", "Title " + identity, "[]", None, "", None, None, None, "{}", None, "", "{}",
            "2026-11-14T00:00:00Z")


INSERT_WORK = ("INSERT INTO works(id,identity_key,work_type,title,authors,year,venue,doi,arxiv_id,isbn,"
               "external_ids,url,abstract,metadata_provenance,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")


class LibrarySchemaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        Store(root / "study.sqlite3")                       # real schema + migrations
        self.db = sqlite3.connect(root / "study.sqlite3")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.addCleanup(self.db.close)
        self.db.execute(INSERT_WORK, work_row("w-old", "legacy-work"))   # exists before the migration
        self.db.commit()
        self.db.executescript((SCHEMA_DIR / "library-study.sql").read_text())
        derived = sqlite3.connect(root / "derived.sqlite3")      # the second file is built on its own
        derived.executescript((SCHEMA_DIR / "library-derived.sql").read_text())
        derived.close()
        self.db.execute("ATTACH DATABASE ? AS derived", (str(root / "derived.sqlite3"),))

    def add_file(self, sha=SHA_A, ext="pdf"):
        self.db.execute("INSERT INTO files(sha256,size_bytes,ext,first_seen_at) VALUES(?,?,?,?)",
                        (sha, 100, ext, "2026-11-14T00:00:00Z"))

    # ---- study side
    def test_existing_works_get_defaults_and_stay_readable(self):
        row = self.db.execute("SELECT title, material_kind, curation_status FROM works WHERE id='w-old'").fetchone()
        self.assertEqual(row, ("Title legacy-work", "other", "inferred"))

    def test_new_works_accept_all_material_kinds_and_reject_unknown(self):
        self.db.execute(INSERT_WORK, work_row("w-1", "one"))
        for kind in ("book", "lecture_notes", "paper", "slides", "problem_sheet", "thesis", "other"):
            self.db.execute("UPDATE works SET material_kind=? WHERE id='w-1'", (kind,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE works SET material_kind='video' WHERE id='w-1'")

    def test_file_identity_and_derived_storage_key(self):
        self.add_file()
        self.assertEqual(self.db.execute("SELECT storage_key FROM files").fetchone()[0], f"sources/{SHA_A}.pdf")
        for bad_sha, bad_ext in (("A" * 64, "pdf"), ("a" * 63, "pdf"), (SHA_B, "PDF"), (SHA_B, "../x"), (SHA_B, "")):
            with self.assertRaises(sqlite3.IntegrityError, msg=(bad_sha[:4], bad_ext)):
                self.add_file(bad_sha, bad_ext)

    def test_locations_require_a_file_and_are_unique(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO file_locations(sha256,kind,uri) VALUES(?,?,?)", (SHA_A, "origin", "x"))
        self.add_file()
        self.db.execute("INSERT INTO file_locations(sha256,kind,uri) VALUES(?,?,?)", (SHA_A, "origin", "x"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO file_locations(sha256,kind,uri) VALUES(?,?,?)", (SHA_A, "origin", "x"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO file_locations(sha256,kind,uri) VALUES(?,?,?)", (SHA_A, "dropbox", "y"))

    def test_identical_content_has_one_file_row_with_many_origins(self):
        self.add_file()
        for uri in ("zip:a.zip!year3/x.pdf", "zip:a.zip!copy/x.pdf"):
            self.db.execute("INSERT INTO file_locations(sha256,kind,uri) VALUES(?,?,?)", (SHA_A, "origin", uri))
        self.assertEqual(self.db.execute("SELECT count(*) FROM files").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM file_locations").fetchone()[0], 2)

    def test_topics_are_unique_among_siblings_including_roots(self):
        self.db.execute("INSERT INTO topics(id,parent_id,name,slug,created_at) VALUES('t1',NULL,'Geometry','geometry','x')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO topics(id,parent_id,name,slug,created_at) VALUES('t2',NULL,'Geometry','geo2','x')")
        self.db.execute("INSERT INTO topics(id,parent_id,name,slug,created_at) VALUES('t3','t1','Curvature','curvature','x')")
        self.db.execute("INSERT INTO topics(id,parent_id,name,slug,created_at) VALUES('t4',NULL,'Curvature','curv-root','x')")

    def test_a_work_has_at_most_one_primary_topic(self):
        for tid in ("t1", "t2"):
            self.db.execute("INSERT INTO topics(id,parent_id,name,slug,created_at) VALUES(?,NULL,?,?,'x')", (tid, tid, tid))
        self.db.execute("INSERT INTO work_topics VALUES('w-old','t1',1)")
        self.db.execute("INSERT INTO work_topics VALUES('w-old','t2',0)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE work_topics SET is_primary=1 WHERE topic_id='t2'")

    def test_tags_are_case_insensitive_and_unique(self):
        self.db.execute("INSERT INTO tags(name) VALUES('Year3')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO tags(name) VALUES('year3')")

    def test_work_links_reject_self_links_and_duplicates(self):
        self.db.execute(INSERT_WORK, work_row("w-2", "two"))
        self.db.execute("INSERT INTO work_links(from_work_id,to_work_id,kind,created_at) VALUES('w-2','w-old','recommends','x')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO work_links(from_work_id,to_work_id,kind,created_at) VALUES('w-2','w-old','recommends','x')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO work_links(from_work_id,to_work_id,kind,created_at) VALUES('w-2','w-2','part_of','x')")

    def test_a_study_source_links_to_a_catalogued_file(self):
        self.add_file()
        self.db.execute("INSERT INTO sources(id,title,metadata,created_at) VALUES('s1','Lee','{}','x')")
        self.db.execute("INSERT INTO source_files VALUES('s1',?)", (SHA_A,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO source_files VALUES('s1',?)", (SHA_B,))

    # ---- derived side
    def test_full_text_search_follows_inserts_updates_and_deletes(self):
        self.db.execute("INSERT INTO derived.page_text(sha256,page,text) VALUES(?,?,?)",
                        (SHA_A, 1, "A smooth manifold has an atlas of charts."))
        hits = lambda q: [r[0] for r in self.db.execute(
            "SELECT rowid FROM derived.page_fts WHERE page_fts MATCH ?", (q,))]
        self.assertEqual(len(hits("manifolds")), 1)         # porter stemming
        self.db.execute("UPDATE derived.page_text SET text='Geodesics and curvature' WHERE page=1")
        self.assertEqual(hits("manifold"), [])
        self.assertEqual(len(hits("geodesic")), 1)
        self.db.execute("DELETE FROM derived.page_text")
        self.assertEqual(hits("geodesic"), [])

    def test_layout_rows_validate_geometry_and_cascade(self):
        self.db.execute("INSERT INTO derived.layout_pages VALUES(?,?,?,?,?,?,?,?)",
                        (SHA_A, 1, 439.0, 666.0, 0, "pymupdf", "1.28", "complete"))
        self.db.execute("INSERT INTO derived.layout_objects(sha256,page,kind,x0,y0,x1,y1) VALUES(?,?,?,?,?,?,?)",
                        (SHA_A, 1, "line", 0.1, 0.1, 0.9, 0.12))
        self.db.execute("INSERT INTO derived.layout_words VALUES(?,?,?)", (SHA_A, 1, zlib.compress(b"[]")))
        for bad in ((0.9, 0.1, 0.1, 0.2), (0.1, 0.1, 1.5, 0.2), (0.1, 0.3, 0.2, 0.2)):
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.execute("INSERT INTO derived.layout_objects(sha256,page,kind,x0,y0,x1,y1) VALUES(?,?,?,?,?,?,?)",
                                (SHA_A, 1, "line", *bad))
        with self.assertRaises(sqlite3.IntegrityError):     # object on a page that has no layout row
            self.db.execute("INSERT INTO derived.layout_objects(sha256,page,kind,x0,y0,x1,y1) VALUES(?,?,?,?,?,?,?)",
                            (SHA_A, 2, "line", 0.1, 0.1, 0.9, 0.2))
        self.db.execute("DELETE FROM derived.layout_pages")
        self.assertEqual(self.db.execute("SELECT count(*) FROM derived.layout_objects").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM derived.layout_words").fetchone()[0], 0)

    def test_derived_rows_join_to_catalogue_by_hash_across_files(self):
        self.add_file()
        self.db.execute("INSERT INTO derived.page_text(sha256,page,text) VALUES(?,?,?)", (SHA_A, 7, "Stokes theorem"))
        row = self.db.execute("""SELECT f.storage_key, p.page FROM derived.page_text p
                                 JOIN files f ON f.sha256 = p.sha256""").fetchone()
        self.assertEqual(row, (f"sources/{SHA_A}.pdf", 7))


if __name__ == "__main__":
    unittest.main()
