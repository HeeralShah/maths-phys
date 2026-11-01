"""Small durable SQLite service for the local maths-phys workflow.

This module deliberately contains no model client. Reads and checks are local and
side-effect free; synthesis is represented by durable jobs for a separately
configured worker.
"""
from __future__ import annotations

import json
import base64
import os
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


HINT_LEVELS = ("orientation", "small_hint", "strong_hint", "partial_solution", "full_solution")
GRAPH_RELATIONS = ("cites", "requires", "extends", "assumes")


class SolutionCipher:
    """Protect full solutions with Windows DPAPI, or a local Fernet key elsewhere."""
    def __init__(self, db_path: str):
        self.key_path = Path(db_path).with_suffix(Path(db_path).suffix + ".solution.key")

    def encrypt(self, value: str) -> str:
        raw = value.encode("utf-8")
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            class Blob(ctypes.Structure):
                _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
            source_buf = ctypes.create_string_buffer(raw)
            source = Blob(len(raw), ctypes.cast(source_buf, ctypes.POINTER(ctypes.c_byte)))
            result = Blob()
            protect = ctypes.windll.crypt32.CryptProtectData
            protect.restype = wintypes.BOOL
            if not protect(ctypes.byref(source), "Maths-Phys full solution", None, None, None, 0, ctypes.byref(result)):
                raise OSError("Windows DPAPI encryption failed")
            try: return "dpapi:" + base64.b64encode(ctypes.string_at(result.pbData, result.cbData)).decode("ascii")
            finally:
                local_free = ctypes.windll.kernel32.LocalFree
                local_free.argtypes = [ctypes.c_void_p]
                local_free.restype = ctypes.c_void_p
                local_free(result.pbData)
        from cryptography.fernet import Fernet
        if self.key_path.exists(): key = self.key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream: stream.write(key)
        return "fernet:" + Fernet(key).encrypt(raw).decode("ascii")

    def decrypt(self, value: str) -> str:
        scheme, payload = value.split(":", 1)
        if scheme == "dpapi":
            raw = base64.b64decode(payload)
            import ctypes
            from ctypes import wintypes
            class Blob(ctypes.Structure):
                _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
            source_buf = ctypes.create_string_buffer(raw)
            source = Blob(len(raw), ctypes.cast(source_buf, ctypes.POINTER(ctypes.c_byte)))
            result = Blob()
            unprotect = ctypes.windll.crypt32.CryptUnprotectData
            unprotect.restype = wintypes.BOOL
            if not unprotect(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)):
                raise OSError("Windows DPAPI decryption failed for this user")
            try: return ctypes.string_at(result.pbData, result.cbData).decode("utf-8")
            finally:
                local_free = ctypes.windll.kernel32.LocalFree
                local_free.argtypes = [ctypes.c_void_p]
                local_free.restype = ctypes.c_void_p
                local_free(result.pbData)
        if scheme != "fernet": raise ValueError("unknown solution encryption scheme")
        from cryptography.fernet import Fernet
        return Fernet(self.key_path.read_bytes()).decrypt(payload.encode("ascii")).decode("utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def uid() -> str:
    return str(uuid.uuid4())


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.solution_cipher = SolutionCipher(self.path)
        self._init_db()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    @contextmanager
    def _connection(self):
        db = self._connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def _init_db(self):
        with self._connection() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS sources(
              id TEXT PRIMARY KEY, title TEXT NOT NULL, metadata TEXT NOT NULL,
              created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sections(
              id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
              title TEXT NOT NULL, ordinal INTEGER NOT NULL, metadata TEXT NOT NULL,
              UNIQUE(source_id, ordinal));
            CREATE TABLE IF NOT EXISTS units(
              id TEXT PRIMARY KEY, section_id TEXT NOT NULL REFERENCES sections(id),
              title TEXT NOT NULL, ordinal INTEGER NOT NULL, metadata TEXT NOT NULL,
              UNIQUE(section_id, ordinal));
            CREATE TABLE IF NOT EXISTS revisions(
              id TEXT PRIMARY KEY, unit_id TEXT NOT NULL REFERENCES units(id),
              revision INTEGER NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL,
              UNIQUE(unit_id, revision));
            CREATE TABLE IF NOT EXISTS checks(
              id TEXT PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES revisions(id),
              check_type TEXT NOT NULL, passed INTEGER NOT NULL, detail TEXT NOT NULL,
              created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
              id TEXT PRIMARY KEY, event_type TEXT NOT NULL, entity_type TEXT NOT NULL,
              entity_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS section_signoffs(
              id TEXT PRIMARY KEY, section_id TEXT NOT NULL REFERENCES sections(id),
              actor TEXT NOT NULL, included_units TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(
              id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
              job_type TEXT NOT NULL CHECK(job_type IN ('prepare','revise','signoff')),
              entity_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN
                ('queued','running','succeeded','failed','cancelled')),
              payload TEXT NOT NULL, result TEXT, error TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS graph_nodes(
              id TEXT PRIMARY KEY, node_type TEXT NOT NULL, label TEXT NOT NULL,
              metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS graph_edges(
              id TEXT PRIMARY KEY, from_id TEXT NOT NULL REFERENCES graph_nodes(id),
              to_id TEXT NOT NULL REFERENCES graph_nodes(id), relation TEXT NOT NULL,
              metadata TEXT NOT NULL, UNIQUE(from_id,to_id,relation));
            CREATE TABLE IF NOT EXISTS problems(
              id TEXT PRIMARY KEY, unit_id TEXT NOT NULL REFERENCES units(id),
              prompt TEXT NOT NULL, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS problem_material(
              problem_id TEXT NOT NULL REFERENCES problems(id), kind TEXT NOT NULL
                CHECK(kind IN ('hint','solution')), content TEXT NOT NULL,
              metadata TEXT NOT NULL, PRIMARY KEY(problem_id,kind));
            CREATE TABLE IF NOT EXISTS research_nodes(
              id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
              node_type TEXT NOT NULL, label TEXT NOT NULL, claim TEXT NOT NULL, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS research_evidence(
              id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
              locator TEXT NOT NULL, quote TEXT NOT NULL, source_ref TEXT, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS research_node_evidence(
              node_id TEXT NOT NULL REFERENCES research_nodes(id) ON DELETE CASCADE,
              evidence_id TEXT NOT NULL REFERENCES research_evidence(id), PRIMARY KEY(node_id,evidence_id));
            CREATE TABLE IF NOT EXISTS research_edges(
              id TEXT PRIMARY KEY, from_id TEXT NOT NULL REFERENCES research_nodes(id),
              to_id TEXT NOT NULL REFERENCES research_nodes(id), relation TEXT NOT NULL
                CHECK(relation IN ('cites','requires','extends','assumes')),
              claim TEXT NOT NULL, metadata TEXT NOT NULL, UNIQUE(from_id,to_id,relation));
            CREATE TABLE IF NOT EXISTS research_edge_evidence(
              edge_id TEXT NOT NULL REFERENCES research_edges(id) ON DELETE CASCADE,
              evidence_id TEXT NOT NULL REFERENCES research_evidence(id), PRIMARY KEY(edge_id,evidence_id));
            CREATE TABLE IF NOT EXISTS source_problems(
              id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), prompt TEXT NOT NULL,
              placement TEXT NOT NULL CHECK(placement IN ('inline','chapter_end','problem_set')),
              placement_ref TEXT, subject TEXT NOT NULL, prerequisites TEXT NOT NULL,
              novelty TEXT NOT NULL, combination TEXT NOT NULL, workload TEXT NOT NULL,
              provenance TEXT NOT NULL, experience TEXT NOT NULL, difficulty TEXT,
              created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS problem_assistance(
              problem_id TEXT NOT NULL REFERENCES source_problems(id) ON DELETE CASCADE,
              level TEXT NOT NULL CHECK(level IN ('orientation','small_hint','strong_hint','partial_solution','full_solution')),
              content TEXT NOT NULL, PRIMARY KEY(problem_id,level));
            """)
            # Preserve legacy problem records while removing any historical plaintext full solutions.
            for row in db.execute("SELECT problem_id,content FROM problem_material WHERE kind='solution'").fetchall():
                if not row["content"].startswith(("dpapi:", "fernet:")):
                    db.execute("UPDATE problem_material SET content=? WHERE problem_id=? AND kind='solution'",
                               (self.solution_cipher.encrypt(row["content"]), row["problem_id"]))

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)

    def _event(self, db, event_type, entity_type, entity_id, payload):
        db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)",
                   (uid(), event_type, entity_type, entity_id, self._json(payload), now()))

    def register_source(self, title: str, metadata=None, sections=None) -> dict:
        """Register source and optional outline only; does not ingest source content."""
        if not title.strip():
            raise ValueError("title is required")
        source_id = uid()
        ts = now()
        with self._connection() as db:
            db.execute("INSERT INTO sources VALUES(?,?,?,?)",
                       (source_id, title.strip(), self._json(metadata), ts))
            for i, spec in enumerate(sections or []):
                section_id = uid()
                db.execute("INSERT INTO sections VALUES(?,?,?,?,?)", (section_id, source_id,
                    spec["title"], int(spec.get("ordinal", i)), self._json(spec.get("metadata"))))
                for j, unit in enumerate(spec.get("units", [])):
                    db.execute("INSERT INTO units VALUES(?,?,?,?,?)", (uid(), section_id,
                        unit["title"], int(unit.get("ordinal", j)), self._json(unit.get("metadata"))))
            self._event(db, "source.registered", "source", source_id, {"title": title.strip()})
        return self.get_source(source_id)

    def get_source(self, source_id: str) -> dict | None:
        with self._connection() as db:
            src = db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            if not src:
                return None
            out = dict(src); out["metadata"] = json.loads(out["metadata"]); out["sections"] = []
            for s in db.execute("SELECT * FROM sections WHERE source_id=? ORDER BY ordinal", (source_id,)):
                section = dict(s); section["metadata"] = json.loads(section["metadata"]); section["units"] = []
                for u in db.execute("SELECT * FROM units WHERE section_id=? ORDER BY ordinal", (s["id"],)):
                    unit = dict(u); unit["metadata"] = json.loads(unit["metadata"]); section["units"].append(unit)
                out["sections"].append(section)
            return out

    def sources(self) -> list[dict]:
        with self._connection() as db:
            return [{"id": r["id"], "title": r["title"], "metadata": json.loads(r["metadata"]),
                     "created_at": r["created_at"]}
                    for r in db.execute("SELECT * FROM sources ORDER BY title COLLATE NOCASE,id")]

    @staticmethod
    def _clean_evidence(spec: dict) -> dict:
        locator = str(spec.get("locator", "")).strip()
        quote = str(spec.get("quote", "")).strip()
        if not locator or not quote:
            raise ValueError("evidence requires a locator and quoted source text")
        return {"locator": locator, "quote": quote, "source_ref": spec.get("source_ref"),
                "metadata": spec.get("metadata") or {}}

    def _store_evidence(self, db, source_id: str, spec: dict) -> str:
        if not db.execute("SELECT 1 FROM sources WHERE id=?", (source_id,)).fetchone():
            raise KeyError("source not found")
        ev = self._clean_evidence(spec)
        evidence_id = uid()
        db.execute("INSERT INTO research_evidence VALUES(?,?,?,?,?,?)",
                   (evidence_id, source_id, ev["locator"], ev["quote"], ev["source_ref"], self._json(ev["metadata"])))
        return evidence_id

    def _evidence_rows(self, db, owner_id: str, table: str, owner_key: str) -> list[dict]:
        rows = db.execute(f"""SELECT e.* FROM research_evidence e JOIN {table} x ON x.evidence_id=e.id
            WHERE x.{owner_key}=? ORDER BY e.id""", (owner_id,)).fetchall()
        return [dict(r) | {"metadata": json.loads(r["metadata"])} for r in rows]

    def create_research_node(self, source_id: str, node_type: str, label: str, claim: str,
                             metadata=None, evidence=None) -> dict:
        if not all(str(x).strip() for x in (node_type, label, claim)):
            raise ValueError("node_type, label, and claim are required")
        evidence = evidence or []
        if not evidence: raise ValueError("at least one evidence anchor is required")
        node_id = uid()
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM sources WHERE id=?", (source_id,)).fetchone(): raise KeyError("source not found")
            db.execute("INSERT INTO research_nodes VALUES(?,?,?,?,?,?)",
                       (node_id, source_id, node_type.strip(), label.strip(), claim.strip(), self._json(metadata)))
            for spec in evidence:
                ev_id = self._store_evidence(db, source_id, spec)
                db.execute("INSERT INTO research_node_evidence VALUES(?,?)", (node_id, ev_id))
            self._event(db, "research.node.created", "research_node", node_id, {"source_id": source_id})
        return self.get_research_node(node_id)

    def create_research_edge(self, from_id: str, to_id: str, relation: str, claim: str,
                             metadata=None, evidence=None) -> dict:
        if relation not in GRAPH_RELATIONS: raise ValueError("relation must be cites, requires, extends, or assumes")
        if not claim.strip(): raise ValueError("claim is required")
        evidence = evidence or []
        if not evidence: raise ValueError("at least one evidence anchor is required")
        edge_id = uid()
        with self._connection() as db:
            endpoints = db.execute("SELECT id FROM research_nodes WHERE id IN (?,?)", (from_id, to_id)).fetchall()
            if len(endpoints) != len(set((from_id, to_id))): raise KeyError("graph node not found")
            db.execute("INSERT INTO research_edges VALUES(?,?,?,?,?,?)",
                       (edge_id, from_id, to_id, relation, claim.strip(), self._json(metadata)))
            for spec in evidence:
                ev_id = self._store_evidence(db, str(spec.get("source_id", "")), spec)
                db.execute("INSERT INTO research_edge_evidence VALUES(?,?)", (edge_id, ev_id))
            self._event(db, "research.edge.created", "research_edge", edge_id, {"relation": relation})
        return self.get_research_edge(edge_id)

    def update_research_node(self, node_id: str, node_type: str, label: str, claim: str,
                             metadata=None, evidence=None) -> dict:
        if not all(str(x).strip() for x in (node_type, label, claim)): raise ValueError("node_type, label, and claim are required")
        if not evidence: raise ValueError("at least one evidence anchor is required")
        with self._connection() as db:
            row = db.execute("SELECT source_id FROM research_nodes WHERE id=?", (node_id,)).fetchone()
            if not row: raise KeyError("graph node not found")
            db.execute("UPDATE research_nodes SET node_type=?,label=?,claim=?,metadata=? WHERE id=?",
                       (node_type.strip(), label.strip(), claim.strip(), self._json(metadata), node_id))
            db.execute("DELETE FROM research_node_evidence WHERE node_id=?", (node_id,))
            for spec in evidence:
                ev_id = self._store_evidence(db, row["source_id"], spec)
                db.execute("INSERT INTO research_node_evidence VALUES(?,?)", (node_id, ev_id))
            self._event(db, "research.node.updated", "research_node", node_id, {})
        return self.get_research_node(node_id)

    def update_research_edge(self, edge_id: str, from_id: str, to_id: str, relation: str, claim: str,
                             metadata=None, evidence=None) -> dict:
        if relation not in GRAPH_RELATIONS: raise ValueError("relation must be cites, requires, extends, or assumes")
        if not claim.strip() or not evidence: raise ValueError("claim and at least one evidence anchor are required")
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM research_edges WHERE id=?", (edge_id,)).fetchone(): raise KeyError("graph edge not found")
            if db.execute("SELECT COUNT(*) FROM research_nodes WHERE id IN (?,?)", (from_id, to_id)).fetchone()[0] != len(set((from_id, to_id))): raise KeyError("graph node not found")
            db.execute("UPDATE research_edges SET from_id=?,to_id=?,relation=?,claim=?,metadata=? WHERE id=?",
                       (from_id, to_id, relation, claim.strip(), self._json(metadata), edge_id))
            db.execute("DELETE FROM research_edge_evidence WHERE edge_id=?", (edge_id,))
            for spec in evidence:
                ev_id = self._store_evidence(db, str(spec.get("source_id", "")), spec)
                db.execute("INSERT INTO research_edge_evidence VALUES(?,?)", (edge_id, ev_id))
            self._event(db, "research.edge.updated", "research_edge", edge_id, {"relation": relation})
        return self.get_research_edge(edge_id)

    def delete_research_node(self, node_id: str) -> bool:
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM research_nodes WHERE id=?", (node_id,)).fetchone(): return False
            edge_ids = [r[0] for r in db.execute("SELECT id FROM research_edges WHERE from_id=? OR to_id=?", (node_id, node_id))]
            for edge_id in edge_ids: db.execute("DELETE FROM research_edges WHERE id=?", (edge_id,))
            db.execute("DELETE FROM research_node_evidence WHERE node_id=?", (node_id,))
            db.execute("DELETE FROM research_nodes WHERE id=?", (node_id,))
            self._event(db, "research.node.deleted", "research_node", node_id, {"deleted_edges": edge_ids})
            return True

    def delete_research_edge(self, edge_id: str) -> bool:
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM research_edges WHERE id=?", (edge_id,)).fetchone(): return False
            db.execute("DELETE FROM research_edge_evidence WHERE edge_id=?", (edge_id,))
            db.execute("DELETE FROM research_edges WHERE id=?", (edge_id,))
            self._event(db, "research.edge.deleted", "research_edge", edge_id, {})
            return True

    def get_research_node(self, node_id: str) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM research_nodes WHERE id=?", (node_id,)).fetchone()
            if not row: return None
            result = dict(row); result["metadata"] = json.loads(result["metadata"])
            result["evidence"] = self._evidence_rows(db, node_id, "research_node_evidence", "node_id")
            return result

    def get_research_edge(self, edge_id: str) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM research_edges WHERE id=?", (edge_id,)).fetchone()
            if not row: return None
            result = dict(row); result["metadata"] = json.loads(result["metadata"])
            result["evidence"] = self._evidence_rows(db, edge_id, "research_edge_evidence", "edge_id")
            return result

    def research_graph(self, source_id: str | None = None) -> dict:
        with self._connection() as db:
            if source_id and not db.execute("SELECT 1 FROM sources WHERE id=?", (source_id,)).fetchone(): raise KeyError("source not found")
            if source_id:
                rows = db.execute("SELECT DISTINCT e.id,e.from_id,e.to_id FROM research_edges e JOIN research_edge_evidence x ON x.edge_id=e.id JOIN research_evidence v ON v.id=x.evidence_id WHERE v.source_id=? ORDER BY e.id", (source_id,)).fetchall()
                edges = [self.get_research_edge(r["id"]) for r in rows]
                node_ids = {r[0] for r in db.execute("SELECT id FROM research_nodes WHERE source_id=?", (source_id,))}
                # Include both endpoints of evidence-backed edges so a source-filtered
                # graph never returns dangling links when evidence spans sources.
                node_ids.update(endpoint for r in rows for endpoint in (r["from_id"], r["to_id"]))
            else:
                edges = [self.get_research_edge(r[0]) for r in db.execute("SELECT id FROM research_edges")]
                node_ids = {r[0] for r in db.execute("SELECT id FROM research_nodes")}
            nodes = [self.get_research_node(i) for i in sorted(node_ids)]
            return {"nodes": nodes, "edges": edges}

    def create_problem(self, source_id: str, prompt: str, placement: str, placement_ref: str | None,
                       subject: str, prerequisites, novelty: str, combination: str, workload: str,
                       provenance: dict, experience: str, difficulty: dict | None, assistance: dict) -> dict:
        if placement not in ("inline", "chapter_end", "problem_set"): raise ValueError("invalid placement")
        if not all(str(x).strip() for x in (prompt, subject, novelty, combination, workload, experience)):
            raise ValueError("prompt, subject, novelty, combination, workload, and experience are required")
        provenance = self._clean_evidence(provenance)
        if difficulty is not None and (not str(difficulty.get("assessment", "")).strip() or not str(difficulty.get("reason", "")).strip()):
            raise ValueError("difficulty requires an assessment and factual reason")
        if difficulty is not None and set(difficulty) != {"assessment", "reason"}:
            raise ValueError("difficulty may contain only assessment and reason")
        missing = set(HINT_LEVELS) - set(assistance or {})
        if missing: raise ValueError("assistance must include all five levels")
        problem_id, ts = uid(), now()
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM sources WHERE id=?", (source_id,)).fetchone(): raise KeyError("source not found")
            for prereq in prerequisites or []:
                if isinstance(prereq, dict) and prereq.get("problem_id"):
                    if not db.execute("SELECT 1 FROM source_problems WHERE id=? AND source_id=?", (prereq["problem_id"], source_id)).fetchone():
                        raise ValueError("prerequisite problem must exist in the same source")
            db.execute("INSERT INTO source_problems VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                problem_id, source_id, prompt.strip(), placement, placement_ref, subject.strip(),
                self._json(prerequisites), novelty.strip(), combination.strip(), workload.strip(),
                self._json(provenance), experience.strip(), self._json(difficulty) if difficulty else None, ts))
            for level in HINT_LEVELS:
                content = str(assistance[level]).strip()
                if not content: raise ValueError(f"assistance level {level} cannot be empty")
                if level == "full_solution": content = self.solution_cipher.encrypt(content)
                db.execute("INSERT INTO problem_assistance VALUES(?,?,?)", (problem_id, level, content))
            self._event(db, "problem.created", "problem", problem_id, {"source_id": source_id, "placement": placement})
        return self.get_problem(problem_id)

    @staticmethod
    def _problem_public(row) -> dict:
        return {"id": row["id"], "source_id": row["source_id"], "prompt": row["prompt"],
                "placement": row["placement"], "placement_ref": row["placement_ref"], "subject": row["subject"],
                "prerequisites": json.loads(row["prerequisites"]), "novelty": row["novelty"],
                "combination": row["combination"], "workload": row["workload"],
                "provenance": json.loads(row["provenance"]), "experience": row["experience"],
                "difficulty": json.loads(row["difficulty"]) if row["difficulty"] else None,
                "created_at": row["created_at"]}

    def get_problem(self, problem_id: str) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM source_problems WHERE id=?", (problem_id,)).fetchone()
            return self._problem_public(row) if row else None

    def list_problems(self, source_id: str | None = None, query: str | None = None) -> list[dict]:
        with self._connection() as db:
            if source_id and not db.execute("SELECT 1 FROM sources WHERE id=?", (source_id,)).fetchone(): raise KeyError("source not found")
            sql, args, where = "SELECT * FROM source_problems", [], []
            if source_id: where.append("source_id=?"); args.append(source_id)
            if query and query.strip(): where.append("(prompt LIKE ? OR subject LIKE ? OR placement_ref LIKE ?)"); args.extend([f"%{query.strip()}%"]*3)
            if where: sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY created_at,id"
            return [self._problem_public(r) for r in db.execute(sql, args)]

    def reveal_problem_level(self, problem_id: str, level: str) -> dict:
        if level not in HINT_LEVELS: raise ValueError("invalid assistance level")
        with self._connection() as db:
            row = db.execute("SELECT content FROM problem_assistance WHERE problem_id=? AND level=?", (problem_id, level)).fetchone()
            if not row:
                if not db.execute("SELECT 1 FROM source_problems WHERE id=?", (problem_id,)).fetchone(): raise KeyError("problem not found")
                raise ValueError("assistance level unavailable")
            content = self.solution_cipher.decrypt(row[0]) if level == "full_solution" else row[0]
            return {"problem_id": problem_id, "level": level, "content": content}

    def save_revision(self, unit_id: str, content: str) -> dict:
        """Append immutable edition; each saved revision receives a stable UUID."""
        ts, rev_id = now(), uid()
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM units WHERE id=?", (unit_id,)).fetchone():
                raise KeyError(unit_id)
            version = db.execute("SELECT COALESCE(MAX(revision),0)+1 FROM revisions WHERE unit_id=?", (unit_id,)).fetchone()[0]
            db.execute("INSERT INTO revisions VALUES(?,?,?,?,?)", (rev_id, unit_id, version, content, ts))
            self._event(db, "revision.saved", "revision", rev_id, {"unit_id": unit_id, "revision": version})
        return {"id": rev_id, "unit_id": unit_id, "revision": version, "content": content, "created_at": ts}

    def read_edition(self, unit_id: str) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM revisions WHERE unit_id=? ORDER BY revision DESC LIMIT 1", (unit_id,)).fetchone()
            return dict(row) if row else None

    def add_check(self, revision_id: str, check_type: str, passed: bool, detail="") -> dict:
        check_id, ts = uid(), now()
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM revisions WHERE id=?", (revision_id,)).fetchone():
                raise KeyError(revision_id)
            db.execute("INSERT INTO checks VALUES(?,?,?,?,?,?)", (check_id, revision_id,
                check_type, int(passed), detail, ts))
            self._event(db, "check.recorded", "revision", revision_id,
                        {"check_id": check_id, "check_type": check_type, "passed": bool(passed)})
        return {"id": check_id, "revision_id": revision_id, "check_type": check_type,
                "passed": bool(passed), "detail": detail, "created_at": ts}

    def get_checks(self, revision_id: str) -> list[dict]:
        with self._connection() as db:
            return [dict(r) | {"passed": bool(r["passed"])} for r in
                    db.execute("SELECT * FROM checks WHERE revision_id=? ORDER BY created_at,id", (revision_id,))]

    def understanding(self, revision_id: str) -> bool | None:
        """Return latest manual understanding state for one saved revision."""
        with self._connection() as db:
            row = db.execute("SELECT passed FROM checks WHERE revision_id=? AND check_type='understood' ORDER BY created_at DESC,id DESC LIMIT 1", (revision_id,)).fetchone()
            return bool(row[0]) if row else None

    def signoff_section(self, section_id: str, actor: str, idempotency_key: str) -> dict:
        """Queue synthesis using only units currently marked understood in this section."""
        if not actor.strip() or not idempotency_key.strip():
            raise ValueError("actor and idempotency_key are required")
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM sections WHERE id=?", (section_id,)).fetchone():
                raise KeyError(section_id)
            existing = db.execute("SELECT * FROM jobs WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if existing:
                return dict(existing)
            included = db.execute("""SELECT u.id AS unit_id,r.id AS revision_id FROM units u
                JOIN revisions r ON r.unit_id=u.id AND r.revision=(SELECT MAX(r2.revision) FROM revisions r2 WHERE r2.unit_id=u.id)
                WHERE u.section_id=? AND (SELECT c.passed FROM checks c WHERE c.revision_id=r.id
                AND c.check_type='understood' ORDER BY c.created_at DESC,c.id DESC LIMIT 1)=1 ORDER BY u.ordinal""", (section_id,)).fetchall()
            ids = [{"unit_id": r["unit_id"], "revision_id": r["revision_id"]} for r in included]
            sign_id, ts = uid(), now()
            db.execute("INSERT INTO section_signoffs VALUES(?,?,?,?,?)", (sign_id, section_id, actor, self._json(ids), ts))
            self._event(db, "section.signoff.recorded", "section", section_id,
                        {"signoff_id": sign_id, "actor": actor, "included_units": ids})
            return self._enqueue(db, "signoff", section_id, idempotency_key,
                                 {"signoff_id": sign_id, "included_units": ids})

    def enqueue(self, job_type: str, entity_id: str, idempotency_key: str, payload=None) -> dict:
        if job_type not in ("prepare", "revise", "signoff"):
            raise ValueError("job_type must be prepare, revise or signoff")
        with self._connection() as db:
            old = db.execute("SELECT * FROM jobs WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if old: return dict(old)
            return self._enqueue(db, job_type, entity_id, idempotency_key, payload or {})

    def _enqueue(self, db, job_type, entity_id, key, payload):
        ts, job_id = now(), uid()
        db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (job_id, key, job_type, entity_id, "queued", self._json(payload), None, None, ts, ts))
        self._event(db, "job.queued", "job", job_id, {"job_type": job_type, "entity_id": entity_id})
        return dict(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def claim_job(self) -> dict | None:
        """Atomically claim the oldest queued job for a configured external worker."""
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if row is None:
                return None
            ts = now()
            changed = db.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=? AND status='queued'",
                                 (ts, row["id"])).rowcount
            if not changed:
                return None
            self._event(db, "job.claimed", "job", row["id"], {})
            return dict(db.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone())

    def complete_job(self, job_id: str, result=None) -> dict:
        """Mark a running job successful after a worker actually produced a result."""
        return self._finish_job(job_id, "succeeded", result=result)

    def fail_job(self, job_id: str, error: str) -> dict:
        if not error or not error.strip():
            raise ValueError("error is required")
        return self._finish_job(job_id, "failed", error=error)

    def _finish_job(self, job_id: str, status: str, result=None, error=None) -> dict:
        with self._connection() as db:
            ts = now()
            changed = db.execute("UPDATE jobs SET status=?,result=?,error=?,updated_at=? WHERE id=? AND status='running'",
                (status, self._json(result) if result is not None else None, error, ts, job_id)).rowcount
            if not changed:
                if not db.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone():
                    raise KeyError(job_id)
                raise ValueError("job must be running to complete or fail")
            self._event(db, f"job.{status}", "job", job_id,
                        {"result": result} if status == "succeeded" else {"error": error})
            return dict(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def recover_stale_jobs(self, max_running_seconds: float) -> int:
        """Requeue expired running leases so a later worker can safely retry them."""
        if max_running_seconds <= 0:
            raise ValueError("max_running_seconds must be positive")
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_running_seconds)).isoformat(timespec="microseconds")
        with self._connection() as db:
            stale = db.execute("SELECT id FROM jobs WHERE status='running' AND updated_at<? ORDER BY created_at,id",
                               (cutoff,)).fetchall()
            ts = now()
            for row in stale:
                db.execute("UPDATE jobs SET status='queued',error=?,updated_at=? WHERE id=? AND status='running'",
                           ("Recovered after stale worker lease expiration", ts, row["id"]))
                self._event(db, "job.requeued", "job", row["id"], {"reason": "stale lease"})
            return len(stale)

    def get_job(self, job_id: str) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None

    def jobs(self, status=None) -> list[dict]:
        with self._connection() as db:
            sql = "SELECT * FROM jobs" + (" WHERE status=?" if status else "") + " ORDER BY created_at,id"
            return [dict(r) for r in db.execute(sql, (status,) if status else ())]
