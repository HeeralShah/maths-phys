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
import hashlib
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .migrations import run_migrations


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
        self._recover_atlas_operations()

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
            CREATE TABLE IF NOT EXISTS revision_provenance(
              revision_id TEXT PRIMARY KEY REFERENCES revisions(id), change_kind TEXT NOT NULL,
              previous_revision_id TEXT REFERENCES revisions(id), source_refs TEXT NOT NULL,
              metadata TEXT NOT NULL);
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
            CREATE TABLE IF NOT EXISTS problem_attempts(
              id TEXT PRIMARY KEY, problem_id TEXT NOT NULL REFERENCES source_problems(id),
              response TEXT NOT NULL, outcome TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS imported_annotations(
              id TEXT PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES revisions(id),
              mark TEXT NOT NULL CHECK(mark IN ('green','yellow','blue','purple')),
              detail TEXT NOT NULL, source_locator TEXT, historical INTEGER NOT NULL DEFAULT 1,
              original_date TEXT, imported_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS atlas_operations(
              id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
              payload TEXT NOT NULL, result TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS atlas_plans(
              id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
              idempotency_key TEXT NOT NULL UNIQUE, signoff_id TEXT NOT NULL REFERENCES section_signoffs(id),
              status TEXT NOT NULL CHECK(status IN ('prepared','applied')), plan TEXT NOT NULL,
              result TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS atlas_plan_applications(
              plan_id TEXT PRIMARY KEY REFERENCES atlas_plans(id),
              status TEXT NOT NULL CHECK(status IN ('applied','applied_unversioned')),
              commit_sha TEXT, error TEXT, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS learner_profile(
              id TEXT PRIMARY KEY CHECK(id='local-user'), data TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS edition_publications(
              publication_key TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
              package_hash TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL);
            """)
            run_migrations(db)
            # Preserve legacy problem records while removing any historical plaintext full solutions.
            for row in db.execute("SELECT problem_id,content FROM problem_material WHERE kind='solution'").fetchall():
                if not row["content"].startswith(("dpapi:", "fernet:")):
                    db.execute("UPDATE problem_material SET content=? WHERE problem_id=? AND kind='solution'",
                               (self.solution_cipher.encrypt(row["content"]), row["problem_id"]))

    def _recover_atlas_operations(self):
        """Roll back any multi-note apply interrupted before its completion record."""
        with self._connection() as db:
            rows = db.execute("SELECT id,payload FROM atlas_operations WHERE status='applying'").fetchall()
        for row in rows:
            journal = json.loads(row["payload"])
            for original in journal.get("originals", []):
                target = Path(original["path"])
                try:
                    if original["existed"]:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        restore = target.with_name(target.name + "." + row["id"] + ".restore")
                        restore.write_bytes(base64.b64decode(original["content"]))
                        os.replace(restore, target)
                    elif target.exists(): target.unlink()
                    temp = target.with_name(target.name + "." + row["id"] + ".tmp")
                    if temp.exists(): temp.unlink()
                except OSError:
                    # Leave operation applying for a later restart if recovery itself is blocked.
                    break
            else:
                with self._connection() as db:
                    db.execute("UPDATE atlas_operations SET status='recovered',payload='{}',error=?,updated_at=? WHERE id=? AND status='applying'",
                               ("Rolled back incomplete file application during startup", now(), row["id"]))

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _semantic_text(content: str) -> str:
        """Normalize layout-only whitespace while preserving wording and notation."""
        return " ".join(content.split())

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

    def register_pdf(self, title: str, path: str, metadata=None, sections=None) -> dict:
        """Register an existing PDF by stable local path; registration never parses it."""
        file = Path(path).expanduser().resolve(strict=True)
        if not file.is_file() or file.suffix.lower() != ".pdf":
            raise ValueError("path must identify an existing PDF file")
        with file.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError("file does not have a PDF signature")
        import fitz
        doc = fitz.open(file)
        try:
            pages = doc.page_count
        finally:
            doc.close()
        digest = self._sha256_file(file)
        data = dict(metadata or {})
        data["local_file"] = {"path": str(file), "sha256": digest, "page_count": pages}
        return self.register_source(title or file.stem, data, sections)

    def source_page(self, source_id: str, page_number: int) -> dict:
        """Extract/render a page only through a PDF path already registered to this source."""
        source = self.get_source(source_id)
        if not source:
            raise KeyError("source not found")
        ref = source["metadata"].get("local_file")
        if not isinstance(ref, dict) or not ref.get("path"):
            raise ValueError("source has no registered PDF")
        path = Path(ref["path"]).resolve(strict=True)
        if not path.is_file() or path.suffix.lower() != ".pdf":
            raise ValueError("registered PDF is unavailable")
        digest = self._sha256_file(path)
        if ref.get("sha256") and digest != ref["sha256"]:
            raise ValueError("registered PDF changed since it was added")
        import fitz
        doc = fitz.open(path)
        try:
            if page_number < 1 or page_number > doc.page_count:
                raise ValueError(f"page_number must be between 1 and {doc.page_count}")
            page = doc.load_page(page_number - 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            return {"source_id": source_id, "page_number": page_number, "page_count": doc.page_count,
                    "text": page.get_text("text"), "image_base64": base64.b64encode(pix.tobytes("png")).decode("ascii"),
                    "image_mime": "image/png"}
        finally:
            doc.close()

    def import_prepared_edition(self, source_id: str, package: dict, publication_key: str | None = None) -> dict:
        """Validate a complete prepared package, then publish every unit revision atomically."""
        if not isinstance(package, dict) or package.get("complete") is not True:
            raise ValueError("edition package must explicitly declare complete=true")
        package_hash = hashlib.sha256(self._json(package).encode("utf-8")).hexdigest()
        publication_key = str(publication_key).strip() if publication_key is not None else None
        if publication_key:
            with self._connection() as db:
                prior = db.execute("SELECT * FROM edition_publications WHERE publication_key=?", (publication_key,)).fetchone()
                if prior:
                    if prior["source_id"] != source_id or prior["package_hash"] != package_hash:
                        raise ValueError("publication_key is already bound to a different complete package")
                    return json.loads(prior["result"])
        edition = package.get("edition") if isinstance(package, dict) else None
        units = edition.get("units") if isinstance(edition, dict) else None
        if not isinstance(units, list) or not units:
            raise ValueError("edition.units must contain complete units")
        if not all(isinstance(u, dict) and str(u.get("content", "")).strip() and
                   str(u.get("section_title", "")).strip() and str(u.get("unit_title", "")).strip() for u in units):
            raise ValueError("every unit needs section_title, unit_title and non-empty content")
        unit_keys = [(u["section_title"].strip().casefold(), u["unit_title"].strip().casefold()) for u in units]
        if len(unit_keys) != len(set(unit_keys)):
            raise ValueError("an edition package cannot contain the same section/unit more than once")
        problems = package.get("problems", [])
        if not isinstance(problems, list): raise ValueError("problems must be a list")
        required_levels = set(HINT_LEVELS)
        for problem in problems:
            if not isinstance(problem, dict) or not all(str(problem.get(k, "")).strip() for k in
                ("prompt", "placement", "subject", "novelty", "combination", "workload", "experience")):
                raise ValueError("each problem needs prompt, placement, subject, novelty, combination, workload and experience")
            if problem["placement"] not in ("inline", "chapter_end", "problem_set"):
                raise ValueError("invalid problem placement")
            if not isinstance(problem.get("assistance"), dict) or not required_levels.issubset(problem["assistance"]):
                raise ValueError("problem must contain all five assistance levels")
            if any(not str(problem["assistance"][level]).strip() for level in HINT_LEVELS):
                raise ValueError("problem assistance levels cannot be empty")
            if not isinstance(problem.get("provenance"), dict) or not problem["provenance"].get("locator") or not problem["provenance"].get("quote"):
                raise ValueError("problem provenance requires locator and quote")
        graph = package.get("graph") or {}
        graph_nodes = graph.get("nodes", []) if isinstance(graph, dict) else None
        graph_edges = graph.get("edges", []) if isinstance(graph, dict) else None
        if not isinstance(graph_nodes, list) or not isinstance(graph_edges, list):
            raise ValueError("graph nodes and edges must be lists")
        graph_keys = set()
        for node in graph_nodes:
            if not isinstance(node, dict) or not all(str(node.get(k, "")).strip() for k in ("local_key", "node_type", "label", "claim")):
                raise ValueError("graph node requires local_key, node_type, label and claim")
            if node["local_key"] in graph_keys: raise ValueError("graph local_key values must be unique")
            graph_keys.add(node["local_key"])
            if not isinstance(node.get("evidence"), list) or not node["evidence"]:
                raise ValueError("every imported graph node requires source evidence")
            for evidence in node["evidence"]: self._clean_evidence(evidence)
        for edge in graph_edges:
            if not isinstance(edge, dict) or not all(str(edge.get(k, "")).strip() for k in ("from_key", "to_key", "relation", "claim")):
                raise ValueError("graph edge requires from_key, to_key, relation and claim")
            if edge["from_key"] not in graph_keys or edge["to_key"] not in graph_keys:
                raise ValueError("graph edge endpoints must resolve to this package's nodes")
            if edge["relation"] not in GRAPH_RELATIONS: raise ValueError("invalid research graph relation")
            if not isinstance(edge.get("evidence"), list) or not edge["evidence"]:
                raise ValueError("every imported graph edge requires source evidence")
            for evidence in edge["evidence"]: self._clean_evidence(evidence)
        source = self.get_source(source_id)
        if not source: raise KeyError("source not found")
        # Prepare and validate all rows before the publication transaction.
        output = []
        with self._connection() as db:
            if publication_key:
                prior = db.execute("SELECT * FROM edition_publications WHERE publication_key=?", (publication_key,)).fetchone()
                if prior:
                    if prior["source_id"] != source_id or prior["package_hash"] != package_hash:
                        raise ValueError("publication_key is already bound to a different complete package")
                    return json.loads(prior["result"])
            sections = {s["title"]: s["id"] for s in source["sections"]}
            for spec in units:
                section_id = sections.get(spec["section_title"])
                if section_id is None:
                    section_id = uid()
                    ordinal = db.execute("SELECT COALESCE(MAX(ordinal),-1)+1 FROM sections WHERE source_id=?", (source_id,)).fetchone()[0]
                    db.execute("INSERT INTO sections VALUES(?,?,?,?,?)", (section_id, source_id, spec["section_title"], ordinal, self._json({})))
                    sections[spec["section_title"]] = section_id
                row = db.execute("SELECT id,metadata FROM units WHERE section_id=? AND title=?", (section_id, spec["unit_title"])).fetchone()
                unit_id = row["id"] if row else uid()
                if not row:
                    ordinal = db.execute("SELECT COALESCE(MAX(ordinal),-1)+1 FROM units WHERE section_id=?", (section_id,)).fetchone()[0]
                    db.execute("INSERT INTO units VALUES(?,?,?,?,?)", (unit_id, section_id, spec["unit_title"], ordinal, self._json(spec.get("metadata"))))
                elif spec.get("metadata"):
                    merged = json.loads(row["metadata"]) | spec["metadata"]
                    db.execute("UPDATE units SET metadata=? WHERE id=?", (self._json(merged), unit_id))
                output.append((unit_id, spec))
            # Same transaction: units and all revisions become visible together.
            revisions = []
            for unit_id, spec in output:
                ts, rid = now(), uid()
                number = db.execute("SELECT COALESCE(MAX(revision),0)+1 FROM revisions WHERE unit_id=?", (unit_id,)).fetchone()[0]
                previous = db.execute("SELECT id,content FROM revisions WHERE unit_id=? ORDER BY revision DESC LIMIT 1", (unit_id,)).fetchone()
                db.execute("INSERT INTO revisions VALUES(?,?,?,?,?)", (rid, unit_id, number, spec["content"], ts))
                formatting_only = bool(previous and self._semantic_text(previous["content"]) == self._semantic_text(spec["content"]))
                db.execute("INSERT INTO revision_provenance VALUES(?,?,?,?,?)", (rid,
                    "formatting" if formatting_only else "material", previous["id"] if previous else None,
                    self._json(spec.get("source_refs", [])), self._json(spec.get("metadata", {}))))
                if formatting_only:
                    latest_checks = db.execute("""SELECT c.* FROM checks c WHERE c.revision_id=? AND c.id=(
                        SELECT c2.id FROM checks c2 WHERE c2.revision_id=c.revision_id AND c2.check_type=c.check_type
                        ORDER BY c2.created_at DESC,c2.id DESC LIMIT 1)""", (previous["id"],)).fetchall()
                    for check in latest_checks:
                        db.execute("INSERT INTO checks VALUES(?,?,?,?,?,?)", (uid(), rid, check["check_type"], check["passed"],
                            "Carried forward from formatting-only revision: " + check["detail"], check["created_at"]))
                self._event(db, "revision.imported", "revision", rid, {"unit_id": unit_id, "source_id": source_id,
                    "source_refs": spec.get("source_refs", []), "edition_title": edition.get("title", "")})
                for annotation in spec.get("annotations", []):
                    mark = str(annotation.get("mark", ""))
                    if mark not in ("green", "yellow", "blue", "purple"):
                        raise ValueError("annotation mark must be green, yellow, blue, or purple")
                    db.execute("INSERT INTO imported_annotations VALUES(?,?,?,?,?,?,?,?)", (uid(), rid, mark,
                        str(annotation.get("detail", "")), annotation.get("source_locator"), int(bool(annotation.get("historical", True))),
                        annotation.get("original_date") or annotation.get("created_at"), ts))
                revisions.append({"id": rid, "unit_id": unit_id, "revision": number, "content": spec["content"], "created_at": ts,
                                  "change_kind": "formatting" if formatting_only else "material", "previous_revision_id": previous["id"] if previous else None,
                                  "source_refs": spec.get("source_refs", [])})
            for problem in problems:
                pid, ts = uid(), now()
                provenance = problem["provenance"]
                db.execute("INSERT INTO source_problems VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    pid, source_id, problem["prompt"].strip(), problem["placement"], problem.get("placement_ref"),
                    problem["subject"].strip(), self._json(problem.get("prerequisites", [])), problem["novelty"].strip(),
                    problem["combination"].strip(), problem["workload"].strip(), self._json(provenance),
                    problem["experience"].strip(), self._json(problem["difficulty"]) if problem.get("difficulty") else None, ts))
                for level in HINT_LEVELS:
                    material = str(problem["assistance"][level]).strip()
                    if level == "full_solution": material = self.solution_cipher.encrypt(material)
                    db.execute("INSERT INTO problem_assistance VALUES(?,?,?)", (pid, level, material))
                self._event(db, "problem.imported", "problem", pid, {"source_id": source_id, "placement": problem["placement"]})
            node_ids = {}
            for node in graph_nodes:
                node_id = uid()
                node_ids[node["local_key"]] = node_id
                db.execute("INSERT INTO research_nodes VALUES(?,?,?,?,?,?)", (node_id, source_id,
                    node["node_type"].strip(), node["label"].strip(), node["claim"].strip(), self._json(node.get("metadata"))))
                for evidence in node["evidence"]:
                    evidence_id = self._store_evidence(db, str(evidence.get("source_id") or source_id), evidence)
                    db.execute("INSERT INTO research_node_evidence VALUES(?,?)", (node_id, evidence_id))
                self._event(db, "research.node.imported", "research_node", node_id, {"source_id": source_id, "local_key": node["local_key"]})
            edge_ids = []
            for edge in graph_edges:
                edge_id = uid()
                db.execute("INSERT INTO research_edges VALUES(?,?,?,?,?,?)", (edge_id, node_ids[edge["from_key"]],
                    node_ids[edge["to_key"]], edge["relation"], edge["claim"].strip(), self._json(edge.get("metadata"))))
                for evidence in edge["evidence"]:
                    evidence_id = self._store_evidence(db, str(evidence.get("source_id") or source_id), evidence)
                    db.execute("INSERT INTO research_edge_evidence VALUES(?,?)", (edge_id, evidence_id))
                edge_ids.append(edge_id)
                self._event(db, "research.edge.imported", "research_edge", edge_id, {"relation": edge["relation"]})
            result = {"source_id": source_id, "title": edition.get("title", ""), "complete": True,
                      "units": revisions, "problems": [p["prompt"] for p in problems],
                      "graph": {"nodes": node_ids, "edges": edge_ids}, "metadata": edition.get("metadata", {})}
            if publication_key:
                db.execute("INSERT INTO edition_publications VALUES(?,?,?,?,?)", (publication_key, source_id,
                    package_hash, self._json(result), now()))
            self._event(db, "edition.imported", "source", source_id, {"title": result["title"], "unit_ids": [r["unit_id"] for r in revisions]})
        return result

    def get_edition_publication(self, publication_key: str) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM edition_publications WHERE publication_key=?", (publication_key,)).fetchone()
            if not row: return None
            return {"publication_key": row["publication_key"], "source_id": row["source_id"],
                    "package_hash": row["package_hash"], "result": json.loads(row["result"]), "created_at": row["created_at"]}

    def record_problem_attempt(self, problem_id: str, response: str, outcome: str, details="") -> dict:
        if not response.strip() or not outcome.strip(): raise ValueError("response and outcome are required")
        attempt = {"id": uid(), "problem_id": problem_id, "response": response, "outcome": outcome,
                   "details": details, "created_at": now()}
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM source_problems WHERE id=?", (problem_id,)).fetchone(): raise KeyError("problem not found")
            db.execute("INSERT INTO problem_attempts VALUES(?,?,?,?,?,?)", tuple(attempt.values()))
        return attempt

    def problem_attempts(self, problem_id: str) -> list[dict]:
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM source_problems WHERE id=?", (problem_id,)).fetchone(): raise KeyError("problem not found")
            return [dict(r) for r in db.execute("SELECT * FROM problem_attempts WHERE problem_id=? ORDER BY created_at,id", (problem_id,))]

    @staticmethod
    def _sha256_file(path: Path) -> str | None:
        if not path.exists(): return None
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""): h.update(chunk)
        return h.hexdigest()

    def apply_synthesis_plan(self, vault_root: str | Path, plan: dict) -> dict:
        """Apply a prepared, checked-material-only Atlas plan with optimistic file checks and rollback journal."""
        key = str(plan.get("idempotency_key", "")).strip()
        signoff_id = str(plan.get("signoff_id", "")).strip()
        files = plan.get("files")
        if not key or not signoff_id or not isinstance(files, list) or not files:
            raise ValueError("plan requires idempotency_key, signoff_id and files")
        root = Path(vault_root).resolve(strict=True)
        with self._connection() as db:
            old = db.execute("SELECT * FROM atlas_operations WHERE idempotency_key=?", (key,)).fetchone()
            if old:
                row = dict(old); row["result"] = json.loads(row["result"]) if row["result"] else None
                return row
            signoff = db.execute("SELECT * FROM section_signoffs WHERE id=?", (signoff_id,)).fetchone()
            if not signoff: raise KeyError("signoff not found")
            signed = json.loads(signoff["included_units"])
            rev_ids = plan.get("source_revision_ids")
            signed_ids = {x["revision_id"] for x in signed}
            if not isinstance(rev_ids, list) or not rev_ids or not set(rev_ids).issubset(signed_ids):
                raise ValueError("plan provenance must use revisions from this signoff")
            for entry in signed:
                if entry["revision_id"] not in rev_ids: continue
                latest = db.execute("SELECT id FROM revisions WHERE unit_id=? ORDER BY revision DESC LIMIT 1", (entry["unit_id"],)).fetchone()
                if not latest:
                    raise ValueError("signed-off material has changed; reconfirm the section before applying this plan")
                signed_content = db.execute("SELECT content FROM revisions WHERE id=?", (entry["revision_id"],)).fetchone()["content"]
                current_content = db.execute("SELECT content FROM revisions WHERE id=?", (latest["id"],)).fetchone()["content"]
                if self._semantic_text(signed_content) != self._semantic_text(current_content):
                    raise ValueError("signed-off material has changed; reconfirm the section before applying this plan")
                current = db.execute("SELECT passed FROM checks WHERE revision_id=? AND check_type='understood' ORDER BY created_at DESC,id DESC LIMIT 1", (latest["id"],)).fetchone()
                if not current or not current["passed"]:
                    raise ValueError("plan includes material that is no longer checked understood")
        expected = plan.get("expected_hashes", {})
        changes, originals = [], []
        for item in files:
            rel = Path(str(item.get("path", "")))
            if rel.is_absolute() or not item.get("path") or rel.suffix.lower() != ".md": raise ValueError("Atlas plan paths must be relative Markdown paths")
            if not rel.parts or rel.parts[0] != "02 Atlas": raise ValueError("Atlas plans may write only within vault/02 Atlas")
            target = (root / rel).resolve()
            try: target.relative_to(root)
            except ValueError: raise ValueError("Atlas plan path must stay within the vault")
            resolved_rel = target.relative_to(root)
            if not resolved_rel.parts or resolved_rel.parts[0] != "02 Atlas": raise ValueError("Atlas plans may resolve only within vault/02 Atlas")
            if str(target) in {change["path"] for change in changes}: raise ValueError("Atlas plan contains duplicate target paths")
            current_hash = self._sha256_file(target)
            if rel.as_posix() not in expected: raise ValueError(f"plan must include an expected hash for {rel.as_posix()}")
            wanted = expected.get(rel.as_posix())
            if current_hash != wanted: raise ValueError(f"Atlas note changed since plan preparation: {rel.as_posix()}")
            if not isinstance(item.get("content"), str) or not item["content"].strip(): raise ValueError("Atlas note content is required")
            originals.append({"path": str(target), "existed": target.exists(),
                              "content": base64.b64encode(target.read_bytes()).decode("ascii") if target.exists() else None})
            changes.append({"path": str(target), "content": item["content"], "relative_path": rel.as_posix(), "expected_hash": wanted})
        op_id, ts = uid(), now()
        journal = {"originals": originals, "changes": changes}
        with self._connection() as db:
            db.execute("INSERT INTO atlas_operations VALUES(?,?,?,?,?,?,?,?)", (op_id, key, "applying",
                self._json(journal), None, None, ts, ts))
        try:
            # Stage every new file on the target filesystem before replacing any target.
            staged = []
            for change in changes:
                target = Path(change["path"]); target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_name(target.name + "." + op_id + ".tmp")
                temp.write_text(change["content"], encoding="utf-8", newline="")
                staged.append((temp, target))
            for (temp, target), change in zip(staged, changes):
                if self._sha256_file(target) != change["expected_hash"]:
                    raise ValueError(f"Atlas note changed during plan application: {change['relative_path']}")
                os.replace(temp, target)
            result = {"id": op_id, "status": "applied", "signoff_id": signoff_id,
                      "paths": [x["relative_path"] for x in changes]}
            with self._connection() as db:
                db.execute("UPDATE atlas_operations SET status='applied',payload='{}',result=?,updated_at=? WHERE id=?",
                           (self._json(result), now(), op_id))
            return result
        except Exception as exc:
            rollback_ok = True
            for original in originals:
                target = Path(original["path"])
                try:
                    if original["existed"]:
                        restore = target.with_name(target.name + "." + op_id + ".restore")
                        restore.write_bytes(base64.b64decode(original["content"]))
                        os.replace(restore, target)
                    elif target.exists(): target.unlink()
                except OSError: rollback_ok = False
            with self._connection() as db:
                if rollback_ok:
                    db.execute("UPDATE atlas_operations SET status='failed',payload='{}',error=?,updated_at=? WHERE id=?", (str(exc), now(), op_id))
                else:
                    db.execute("UPDATE atlas_operations SET error=?,updated_at=? WHERE id=?", (f"Rollback incomplete: {exc}", now(), op_id))
            raise

    def import_synthesis_plan(self, job_id: str, vault_root: str | Path, plan: dict) -> dict:
        """Persist and validate a signoff worker plan for later explicit user application."""
        root = Path(vault_root).resolve(strict=True)
        with self._connection() as db:
            job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not job: raise KeyError("job not found")
            if job["job_type"] != "signoff" or job["status"] not in ("running", "succeeded"):
                raise ValueError("synthesis plans can be imported only for a running or completed signoff job")
            signed_payload = json.loads(job["payload"])
            signoff_id = str(plan.get("signoff_id", "")).strip()
            if not signoff_id or signoff_id != signed_payload.get("signoff_id"):
                raise ValueError("plan signoff_id does not match this signoff job")
            requested_intent = str(signed_payload.get("intent", "")).strip()
            supplied_intent = str(plan.get("intent", "")).strip()
            if requested_intent and supplied_intent != requested_intent:
                raise ValueError("plan must preserve the signoff's user-entered intent exactly")
            plan["intent"] = requested_intent
            source_revision_ids = plan.get("source_revision_ids")
            allowed_ids = {entry["revision_id"] for entry in signed_payload.get("included_units", [])}
            if not isinstance(source_revision_ids, list) or not source_revision_ids or not set(source_revision_ids).issubset(allowed_ids):
                raise ValueError("plan provenance must be a non-empty subset of this checked signoff snapshot")
            for entry in signed_payload.get("included_units", []):
                if entry["revision_id"] not in source_revision_ids: continue
                current = db.execute("SELECT id,unit_id FROM revisions WHERE unit_id=? ORDER BY revision DESC LIMIT 1", (entry["unit_id"],)).fetchone()
                signed_content = db.execute("SELECT content FROM revisions WHERE id=?", (entry["revision_id"],)).fetchone()["content"]
                current_content = db.execute("SELECT content FROM revisions WHERE id=?", (current["id"],)).fetchone()["content"] if current else None
                if not current or self._semantic_text(signed_content) != self._semantic_text(current_content):
                    raise ValueError("signed-off material changed; a new signoff is required before saving this plan")
                understood = db.execute("SELECT passed FROM checks WHERE revision_id=? AND check_type='understood' ORDER BY created_at DESC,id DESC LIMIT 1", (current["id"],)).fetchone()
                if not understood or not understood["passed"]:
                    raise ValueError("plan includes material that is no longer checked understood")
            key = str(plan.get("idempotency_key") or f"signoff:{signoff_id}").strip()
            plan["idempotency_key"] = key
            files, expected = plan.get("files"), plan.get("expected_hashes")
            if not isinstance(files, list) or not files or not isinstance(expected, dict):
                raise ValueError("plan requires files and expected_hashes")
            seen = set()
            for item in files:
                rel = Path(str(item.get("path", "")))
                if rel.is_absolute() or not rel.parts or rel.suffix.casefold() != ".md":
                    raise ValueError("Atlas plan paths must be relative Markdown paths")
                target = (root / rel).resolve()
                resolved_rel = target.relative_to(root)
                if resolved_rel.parts[0] != "02 Atlas": raise ValueError("Atlas plans may write only within vault/02 Atlas")
                if str(target) in seen: raise ValueError("Atlas plan contains duplicate target paths")
                seen.add(str(target))
                if rel.as_posix() not in expected or self._sha256_file(target) != expected[rel.as_posix()]:
                    raise ValueError(f"expected hash is missing or stale for {rel.as_posix()}")
                if not isinstance(item.get("content"), str) or not item["content"].strip():
                    raise ValueError("Atlas plan note content cannot be empty")
            prior = db.execute("SELECT * FROM atlas_plans WHERE idempotency_key=?", (key,)).fetchone()
            if prior:
                existing_plan = json.loads(prior["plan"])
                if prior["signoff_id"] != signoff_id or existing_plan != plan:
                    raise ValueError("idempotency key is already bound to a different synthesis plan")
                return dict(prior) | {"plan": existing_plan, "result": json.loads(prior["result"]) if prior["result"] else None}
            plan_id, ts = uid(), now()
            db.execute("INSERT INTO atlas_plans VALUES(?,?,?,?,?,?,?,?,?)", (plan_id, job_id, key, signoff_id,
                "prepared", self._json(plan), None, ts, ts))
            self._event(db, "atlas.plan.imported", "atlas_plan", plan_id,
                        {"signoff_id": signoff_id, "source_revision_ids": source_revision_ids})
            return {"id": plan_id, "job_id": job_id, "idempotency_key": key, "signoff_id": signoff_id,
                    "status": "prepared", "plan": plan, "result": None, "created_at": ts, "updated_at": ts}

    def _commit_atlas_plan(self, vault_root: str | Path, plan: dict) -> dict:
        """Create a local commit for only the synthesized note paths; never push or touch other paths."""
        root = Path(vault_root).resolve(strict=True)
        try:
            repo = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                                  capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return {"versioning_status": "applied_unversioned", "git_error": "Git is unavailable; the Atlas files remain applied."}
        if repo.returncode:
            return {"versioning_status": "applied_unversioned", "git_error": "No containing Git repository; the Atlas files remain applied."}
        repo_root = Path(repo.stdout.strip()).resolve()
        changed = []
        expected = plan.get("expected_hashes", {})
        for item in plan.get("files", []):
            rel = Path(item["path"])
            target = (root / rel).resolve(strict=True)
            target.relative_to(root)
            if target.read_text(encoding="utf-8") != item["content"]:
                return {"versioning_status": "applied_unversioned", "git_error": f"{rel.as_posix()} changed after synthesis; review it before committing."}
            git_path = target.relative_to(repo_root).as_posix()
            old_hash = expected.get(rel.as_posix())
            new_hash = self._sha256_file(target)
            if old_hash != new_hash: changed.append(git_path)
        if not changed:
            return {"versioning_status": "applied", "git_commit": None, "git_error": None}
        # A second index keeps the user's existing staged work intact. The main
        # index is refreshed only for paths committed by this operation.
        try:
            staged = subprocess.run(["git", "-C", str(repo_root), "diff", "--cached", "--quiet", "HEAD", "--", *changed],
                                    capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return {"versioning_status": "applied_unversioned", "git_error": "Could not inspect the Git index; Atlas files remain applied."}
        if staged.returncode != 0:
            return {"versioning_status": "applied_unversioned", "git_error": "Atlas targets already have staged edits; review and commit them manually."}
        try:
            worktree = subprocess.run(["git", "-C", str(repo_root), "diff", "--quiet", "HEAD", "--", *changed],
                                      capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return {"versioning_status": "applied_unversioned", "git_error": "Could not inspect the Git worktree; Atlas files remain applied."}
        if worktree.returncode == 0:
            head = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
            return {"versioning_status": "applied", "git_commit": head.stdout.strip() if head.returncode == 0 else None, "git_error": None}
        if worktree.returncode != 1:
            return {"versioning_status": "applied_unversioned", "git_error": "Could not compare Atlas targets with HEAD; files remain applied."}
        try:
            handle, index_path = tempfile.mkstemp(prefix="maths-phys-atlas-index-")
        except OSError:
            return {"versioning_status": "applied_unversioned", "git_error": "Could not create a temporary Git index; Atlas files remain applied."}
        os.close(handle)
        env = os.environ.copy(); env["GIT_INDEX_FILE"] = index_path; env["GIT_TERMINAL_PROMPT"] = "0"
        try:
            commands = [
                ["git", "-C", str(repo_root), "read-tree", "HEAD"],
                ["git", "-C", str(repo_root), "add", "--", *changed],
            ]
            for command in commands:
                run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
                if run.returncode:
                    return {"versioning_status": "applied_unversioned", "git_error": "Git could not prepare the Atlas-only commit; retry after checking repository state."}
            intent = str(plan.get("intent", "")).strip()
            if intent:
                message = f"Atlas synthesis: {intent.replace(chr(10), ' ').strip()}"
            else:
                titles = ", ".join(Path(p).stem for p in changed[:3])
                message = f"Atlas synthesis: update {titles} from checked signoff {str(plan.get('signoff_id',''))[:8]}"
            run = subprocess.run(["git", "-C", str(repo_root), "commit", "--only", "--message", message,
                                  "--", *changed], env=env, capture_output=True, text=True, timeout=30)
            if run.returncode:
                return {"versioning_status": "applied_unversioned", "git_error": "Atlas files are applied, but Git commit failed; configure repository identity and retry."}
            # Do not leave this commit's paths staged in the user's original index.
            try:
                refresh = subprocess.run(["git", "-C", str(repo_root), "reset", "--quiet", "HEAD", "--", *changed],
                                         capture_output=True, text=True, timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                refresh = None
            sha = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
            return {"versioning_status": "applied", "git_commit": sha.stdout.strip() if sha.returncode == 0 else None,
                    "git_error": None if refresh and refresh.returncode == 0 else "Commit succeeded; refresh the repository index for the Atlas paths."}
        except (OSError, subprocess.TimeoutExpired):
            return {"versioning_status": "applied_unversioned", "git_error": "Git operation timed out; Atlas files remain applied and can be retried."}
        finally:
            try: Path(index_path).unlink(missing_ok=True)
            except OSError: pass

    def get_synthesis_plan(self, plan_id: str) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM atlas_plans WHERE id=?", (plan_id,)).fetchone()
            if not row: return None
            result = dict(row) | {"plan": json.loads(row["plan"]), "result": json.loads(row["result"]) if row["result"] else None}
            application = db.execute("SELECT * FROM atlas_plan_applications WHERE plan_id=?", (plan_id,)).fetchone()
            if application:
                result.update(status=application["status"], git_commit=application["commit_sha"], git_error=application["error"])
            return result

    def apply_imported_synthesis_plan(self, plan_id: str, vault_root: str | Path) -> dict:
        with self._connection() as db:
            row = db.execute("SELECT * FROM atlas_plans WHERE id=?", (plan_id,)).fetchone()
            if not row: raise KeyError("synthesis plan not found")
            if row["status"] == "applied":
                result = json.loads(row["result"])
                application = db.execute("SELECT status FROM atlas_plan_applications WHERE plan_id=?", (plan_id,)).fetchone()
                if application and application["status"] == "applied": return result
                plan = json.loads(row["plan"])
            else:
                plan = json.loads(row["plan"])
                result = None
        if result is None:
            result = self.apply_synthesis_plan(vault_root, plan)
        with self._connection() as db:
            db.execute("UPDATE atlas_plans SET status='applied',result=?,updated_at=? WHERE id=? AND status='prepared'",
                       (self._json(result), now(), plan_id))
        versioning = self._commit_atlas_plan(vault_root, plan)
        result.update(versioning)
        with self._connection() as db:
            db.execute("INSERT INTO atlas_plan_applications VALUES(?,?,?,?,?) ON CONFLICT(plan_id) DO UPDATE SET status=excluded.status,commit_sha=excluded.commit_sha,error=excluded.error,updated_at=excluded.updated_at",
                       (plan_id, versioning["versioning_status"], versioning.get("git_commit"), versioning.get("git_error"), now()))
            db.execute("UPDATE atlas_plans SET result=?,updated_at=? WHERE id=?", (self._json(result), now(), plan_id))
        return result

    def sources(self) -> list[dict]:
        with self._connection() as db:
            return [{"id": r["id"], "title": r["title"], "metadata": json.loads(r["metadata"]),
                     "created_at": r["created_at"]}
                    for r in db.execute("SELECT * FROM sources ORDER BY title COLLATE NOCASE,id")]

    @staticmethod
    def _empty_profile() -> dict:
        return {"goals": "", "assumed_knowledge": [], "misconceptions": [],
                "preferred_explanations": "", "preferences": {}, "notes": ""}

    def get_learning_profile(self) -> dict:
        with self._connection() as db:
            row = db.execute("SELECT data,updated_at FROM learner_profile WHERE id='local-user'").fetchone()
            return self._empty_profile() | (json.loads(row["data"]) if row else {}) | {"updated_at": row["updated_at"] if row else None}

    def update_learning_profile(self, data: dict) -> dict:
        if not isinstance(data, dict): raise ValueError("profile must be an object")
        allowed = set(self._empty_profile())
        if set(data) - allowed: raise ValueError("profile contains unsupported fields")
        value = self._empty_profile() | data
        for key in ("goals", "preferred_explanations", "notes"):
            if not isinstance(value[key], str): raise ValueError(f"{key} must be a string")
        for key in ("assumed_knowledge", "misconceptions"):
            if not isinstance(value[key], list) or any(not isinstance(x, str) for x in value[key]):
                raise ValueError(f"{key} must be a list of strings")
        if not isinstance(value["preferences"], dict): raise ValueError("preferences must be an object")
        ts = now()
        with self._connection() as db:
            db.execute("INSERT INTO learner_profile VALUES('local-user',?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at",
                       (self._json(value), ts))
        return value | {"updated_at": ts}

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

    def save_revision(self, unit_id: str, content: str, source_refs=None, metadata=None) -> dict:
        """Append immutable edition; each saved revision receives a stable UUID."""
        ts, rev_id = now(), uid()
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM units WHERE id=?", (unit_id,)).fetchone():
                raise KeyError(unit_id)
            previous = db.execute("SELECT id,content FROM revisions WHERE unit_id=? ORDER BY revision DESC LIMIT 1", (unit_id,)).fetchone()
            version = db.execute("SELECT COALESCE(MAX(revision),0)+1 FROM revisions WHERE unit_id=?", (unit_id,)).fetchone()[0]
            db.execute("INSERT INTO revisions VALUES(?,?,?,?,?)", (rev_id, unit_id, version, content, ts))
            formatting_only = previous and self._semantic_text(previous["content"]) == self._semantic_text(content)
            db.execute("INSERT INTO revision_provenance VALUES(?,?,?,?,?)", (rev_id,
                "formatting" if formatting_only else "material", previous["id"] if previous else None,
                self._json(source_refs or []), self._json(metadata or {})))
            if formatting_only:
                # Carry forward the latest state per check type; dated history remains on prior revision.
                latest_checks = db.execute("""SELECT c.* FROM checks c WHERE c.revision_id=? AND c.id=(
                    SELECT c2.id FROM checks c2 WHERE c2.revision_id=c.revision_id AND c2.check_type=c.check_type
                    ORDER BY c2.created_at DESC,c2.id DESC LIMIT 1)""", (previous["id"],)).fetchall()
                for check in latest_checks:
                    db.execute("INSERT INTO checks VALUES(?,?,?,?,?,?)", (uid(), rev_id, check["check_type"],
                        check["passed"], "Carried forward from formatting-only revision: " + check["detail"], check["created_at"]))
            self._event(db, "revision.saved", "revision", rev_id, {"unit_id": unit_id, "revision": version})
        return {"id": rev_id, "unit_id": unit_id, "revision": version, "content": content, "created_at": ts,
                "change_kind": "formatting" if formatting_only else "material", "previous_revision_id": previous["id"] if previous else None,
                "source_refs": source_refs or [], "metadata": metadata or {}}

    def read_edition(self, unit_id: str) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM revisions WHERE unit_id=? ORDER BY revision DESC LIMIT 1", (unit_id,)).fetchone()
            if not row: return None
            result = dict(row)
            provenance = db.execute("SELECT change_kind,previous_revision_id,source_refs,metadata FROM revision_provenance WHERE revision_id=?", (row["id"],)).fetchone()
            if provenance:
                result.update(change_kind=provenance["change_kind"], previous_revision_id=provenance["previous_revision_id"],
                              source_refs=json.loads(provenance["source_refs"]), metadata=json.loads(provenance["metadata"]))
            return result

    def read_revision(self, revision_id: str) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM revisions WHERE id=?", (revision_id,)).fetchone()
            if not row: return None
            result = dict(row)
            provenance = db.execute("SELECT change_kind,previous_revision_id,source_refs,metadata FROM revision_provenance WHERE revision_id=?", (revision_id,)).fetchone()
            if provenance:
                result.update(change_kind=provenance["change_kind"], previous_revision_id=provenance["previous_revision_id"],
                              source_refs=json.loads(provenance["source_refs"]), metadata=json.loads(provenance["metadata"]))
            else:
                result.update(change_kind="material", previous_revision_id=None, source_refs=[], metadata={})
            return result

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

    def imported_annotations(self, revision_id: str) -> list[dict]:
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM revisions WHERE id=?", (revision_id,)).fetchone(): raise KeyError("revision not found")
            return [dict(r) | {"historical": bool(r["historical"])} for r in db.execute(
                "SELECT * FROM imported_annotations WHERE revision_id=? ORDER BY imported_at,id", (revision_id,))]

    def understanding(self, revision_id: str) -> bool | None:
        """Return latest manual understanding state for one saved revision."""
        with self._connection() as db:
            row = db.execute("SELECT passed FROM checks WHERE revision_id=? AND check_type='understood' ORDER BY created_at DESC,id DESC LIMIT 1", (revision_id,)).fetchone()
            return bool(row[0]) if row else None

    def signoff_section(self, section_id: str, actor: str, idempotency_key: str, intent: str = "") -> dict:
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
                        {"signoff_id": sign_id, "actor": actor, "intent": intent, "included_units": ids})
            return self._enqueue(db, "signoff", section_id, idempotency_key,
                                 {"signoff_id": sign_id, "included_units": ids, "intent": intent})

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

    def requeue_job(self, job_id: str, reason: str) -> dict:
        """Return a claimed job to the queue when a transient configured limit blocks execution."""
        if not reason.strip(): raise ValueError("reason is required")
        with self._connection() as db:
            ts = now()
            changed = db.execute("UPDATE jobs SET status='queued',error=?,updated_at=? WHERE id=? AND status='running'",
                                 (reason, ts, job_id)).rowcount
            if not changed:
                if not db.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone(): raise KeyError(job_id)
                raise ValueError("job must be running to requeue")
            self._event(db, "job.requeued", "job", job_id, {"reason": reason})
            return dict(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

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
