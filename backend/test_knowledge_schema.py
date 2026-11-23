"""Checks that the proposed knowledge-base schema (docs/schema/knowledge-base.sql) applies on top of
the real study database plus the library schema, and enforces its provenance and edge rules."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.store import Store

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "docs" / "schema"
SHA = "a" * 64
NOW = "2026-11-23T00:00:00Z"


class KnowledgeSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        Store(root / "study.sqlite3")
        self.db = sqlite3.connect(root / "study.sqlite3")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.addCleanup(self.db.close)
        self.db.execute(
            "INSERT INTO works(id,identity_key,work_type,title,authors,year,venue,doi,arxiv_id,isbn,"
            "external_ids,url,abstract,metadata_provenance,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("w1", "bass-rags", "book", "Real Analysis for Graduate Students", "[]", None, "", None, None, None,
             "{}", None, "", "{}", NOW))
        self.db.executescript((SCHEMA_DIR / "library-study.sql").read_text())
        self.db.executescript((SCHEMA_DIR / "knowledge-base.sql").read_text())
        self.db.execute("INSERT INTO files(sha256,size_bytes,ext,first_seen_at) VALUES(?,?,?,?)", (SHA, 1, "pdf", NOW))

    def stmt(self, sid, kind="theorem", label=None, ordinal=None):
        n = int(sid[1:])
        self.db.execute(
            "INSERT INTO statements(id,work_id,kind,label,ordinal,source_tex,created_at) VALUES(?,?,?,?,?,?,?)",
            (sid, "w1", kind, label or f"{kind} {n}", ordinal or n, "x", NOW))

    def prov(self, **kw):
        row = dict(statement_id=None, proof_id=None, sha256=SHA, page_start=3, page_end=3, method="pdf_text",
                   created_at=NOW)
        row.update(kw)
        cols = ",".join(row)
        self.db.execute(f"INSERT INTO provenance({cols}) VALUES({','.join('?' * len(row))})", tuple(row.values()))

    def test_provenance_needs_exactly_one_subject(self):
        self.stmt("s1")
        self.db.execute("INSERT INTO proofs(id,statement_id,kind,source_tex,created_at) VALUES('p1','s1','book','x',?)", (NOW,))
        self.prov(statement_id="s1")
        self.prov(proof_id="p1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.prov()
        with self.assertRaises(sqlite3.IntegrityError):
            self.prov(statement_id="s1", proof_id="p1")

    def test_provenance_page_range_and_file(self):
        self.stmt("s1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.prov(statement_id="s1", page_start=5, page_end=4)
        with self.assertRaises(sqlite3.IntegrityError):
            self.prov(statement_id="s1", sha256="b" * 64)

    def test_labels_and_order_unique_per_work(self):
        self.stmt("s1", label="Definition 1.1", ordinal=1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.stmt("s2", label="Definition 1.1", ordinal=2)
        with self.assertRaises(sqlite3.IntegrityError):
            self.stmt("s3", label="Definition 1.2", ordinal=1)

    def test_edges_no_self_loop_no_duplicate(self):
        self.stmt("s1")
        self.stmt("s2")
        ins = "INSERT INTO statement_edges(src_statement_id,dst_statement_id,relation,asserted_by,created_at) VALUES(?,?,?,?,?)"
        self.db.execute(ins, ("s2", "s1", "uses_result", "agent", NOW))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(ins, ("s2", "s1", "uses_result", "manual", NOW))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(ins, ("s1", "s1", "uses_result", "manual", NOW))
        self.db.execute(ins, ("s2", "s1", "cites", "manual", NOW))   # a different relation is fine

    def test_deleting_statement_cascades(self):
        self.stmt("s1")
        self.prov(statement_id="s1")
        self.db.execute("INSERT INTO statement_study(statement_id,updated_at) VALUES('s1',?)", (NOW,))
        self.db.execute("DELETE FROM statements WHERE id='s1'")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM provenance").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM statement_study").fetchone()[0], 0)

    def test_coverage_and_unformalised_views(self):
        self.stmt("s1", kind="definition")
        self.stmt("s2", kind="theorem")
        self.prov(statement_id="s1", reviewed_at=NOW)
        self.db.execute("INSERT INTO statement_edges(src_statement_id,dst_statement_id,relation,asserted_by,created_at)"
                        " VALUES('s2','s1','uses_definition','agent',?)", (NOW,))
        todo = self.db.execute("SELECT statement_id, dependency_id FROM v_unformalised_dependencies").fetchall()
        self.assertEqual(todo, [("s2", "s1")])
        link = "INSERT INTO lean_links(statement_id,link_kind,lean_name,status,fidelity,created_at) VALUES('s1','mathlib_equivalent','Foo',?,?,?)"
        self.db.execute(link, ("mathlib", "weaker", NOW))     # compiles but is not faithful: still a to-do
        self.assertEqual(len(self.db.execute("SELECT * FROM v_unformalised_dependencies").fetchall()), 1)
        self.db.execute("UPDATE lean_links SET fidelity='matches'")
        self.assertEqual(self.db.execute("SELECT * FROM v_unformalised_dependencies").fetchall(), [])
        row = self.db.execute("SELECT statements,definitions,results,reviewed,with_lean,formally_verified "
                              "FROM v_work_coverage WHERE work_id='w1'").fetchone()
        self.assertEqual(row, (2, 1, 1, 1, 1, 1))

    def test_lean_status_and_fidelity_vocabularies(self):
        self.stmt("s1")
        base = "INSERT INTO lean_links(statement_id,link_kind,lean_name,status,fidelity,created_at) VALUES('s1','own_formalisation',?,?,?,?)"
        self.db.execute(base, ("A", "sorry", "unchecked", NOW))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(base, ("B", "compiles", "unchecked", NOW))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(base, ("C", "proved", "looks-fine", NOW))


if __name__ == "__main__":
    unittest.main()
