"""Small durable SQLite service for the local maths-phys workflow.

This module deliberately contains no model client. Reads and checks are local and
side-effect free; synthesis is represented by durable jobs for a separately
configured worker.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def uid() -> str:
    return str(uuid.uuid4())


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
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
            """)

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
