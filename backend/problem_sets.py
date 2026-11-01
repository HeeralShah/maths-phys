"""FastAPI router for ordered, user-curated sets of source problems."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _uid() -> str:
    return str(uuid.uuid4())


def _ensure_schema(store) -> None:
    """Install this module's additive schema, safe to call on every app startup."""
    with store._connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS problem_sets(
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS problem_set_members(
            set_id TEXT NOT NULL REFERENCES problem_sets(id) ON DELETE CASCADE,
            problem_id TEXT NOT NULL REFERENCES source_problems(id) ON DELETE CASCADE,
            ordinal INTEGER NOT NULL,
            PRIMARY KEY(set_id, problem_id),
            UNIQUE(set_id, ordinal)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_problem_set_members_order ON problem_set_members(set_id,ordinal)")


def _public_problem(row) -> dict[str, Any]:
    """Return problem catalogue fields only; assistance material is never selected."""
    return {
        "id": row["id"],
        "source_id": row["source_id"],
        "prompt": row["prompt"],
        "placement": row["placement"],
        "placement_ref": row["placement_ref"],
        "subject": row["subject"],
        "prerequisites": json.loads(row["prerequisites"]),
        "novelty": row["novelty"],
        "combination": row["combination"],
        "workload": row["workload"],
        "provenance": json.loads(row["provenance"]),
        "experience": row["experience"],
        "difficulty": json.loads(row["difficulty"]) if row["difficulty"] else None,
        "created_at": row["created_at"],
    }


def _read_set(db, set_id: str) -> dict | None:
    row = db.execute("SELECT * FROM problem_sets WHERE id=?", (set_id,)).fetchone()
    if not row:
        return None
    members = db.execute("""SELECT p.* FROM problem_set_members m
        JOIN source_problems p ON p.id=m.problem_id
        WHERE m.set_id=? ORDER BY m.ordinal""", (set_id,)).fetchall()
    problems = [_public_problem(member) for member in members]
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "problem_ids": [problem["id"] for problem in problems],
        "problems": problems,
    }


def _validate_problem_ids(db, problem_ids: list[str], *, allow_empty: bool) -> list[str]:
    if len(problem_ids) != len(set(problem_ids)):
        raise HTTPException(status_code=422, detail="problem_ids must not contain duplicates")
    if not allow_empty and not problem_ids:
        raise HTTPException(status_code=422, detail="a problem set must contain at least one source problem")
    if not problem_ids:
        return []
    placeholders = ",".join("?" for _ in problem_ids)
    found = {row[0] for row in db.execute(
        f"SELECT id FROM source_problems WHERE id IN ({placeholders})", problem_ids)}
    missing = [problem_id for problem_id in problem_ids if problem_id not in found]
    if missing:
        raise HTTPException(status_code=404, detail={"message": "source problems not found", "problem_ids": missing})
    return problem_ids


def _validate_text(value: str, field: str, max_length: int, *, allow_empty: bool) -> str:
    normalized = value.strip()
    if not allow_empty and not normalized:
        raise HTTPException(status_code=422, detail=f"{field} is required")
    if len(normalized) > max_length:
        raise HTTPException(status_code=422, detail=f"{field} must be at most {max_length} characters")
    return normalized


class CreateProblemSet(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    problem_ids: list[str]


class UpdateProblemSet(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    problem_ids: list[str] | None = None


def build_router(store) -> APIRouter:
    """Create and initialize the problem-set router for an existing Store instance."""
    _ensure_schema(store)
    router = APIRouter(prefix="/problem-sets", tags=["problem sets"])

    @router.get("")
    def list_problem_sets():
        with store._connection() as db:
            set_ids = [row[0] for row in db.execute(
                "SELECT id FROM problem_sets ORDER BY updated_at DESC,created_at DESC,id")]
            return [_read_set(db, set_id) for set_id in set_ids]

    @router.post("", status_code=201)
    def create_problem_set(body: CreateProblemSet):
        title = _validate_text(body.title, "title", 200, allow_empty=False)
        description = _validate_text(body.description, "description", 5000, allow_empty=True)
        set_id, timestamp = _uid(), _now()
        with store._connection() as db:
            problem_ids = _validate_problem_ids(db, body.problem_ids, allow_empty=False)
            db.execute("INSERT INTO problem_sets VALUES(?,?,?,?,?)",
                       (set_id, title, description, timestamp, timestamp))
            db.executemany("INSERT INTO problem_set_members VALUES(?,?,?)",
                           [(set_id, problem_id, ordinal) for ordinal, problem_id in enumerate(problem_ids)])
            return _read_set(db, set_id)

    @router.get("/{set_id}")
    def get_problem_set(set_id: str):
        with store._connection() as db:
            result = _read_set(db, set_id)
            if result is None:
                raise HTTPException(status_code=404, detail="problem set not found")
            return result

    @router.put("/{set_id}")
    def update_problem_set(set_id: str, body: UpdateProblemSet):
        with store._connection() as db:
            current = db.execute("SELECT * FROM problem_sets WHERE id=?", (set_id,)).fetchone()
            if not current:
                raise HTTPException(status_code=404, detail="problem set not found")
            title = current["title"] if body.title is None else _validate_text(
                body.title, "title", 200, allow_empty=False)
            description = current["description"] if body.description is None else _validate_text(
                body.description, "description", 5000, allow_empty=True)
            timestamp = _now()
            db.execute("UPDATE problem_sets SET title=?,description=?,updated_at=? WHERE id=?",
                       (title, description, timestamp, set_id))
            if body.problem_ids is not None:
                problem_ids = _validate_problem_ids(db, body.problem_ids, allow_empty=True)
                db.execute("DELETE FROM problem_set_members WHERE set_id=?", (set_id,))
                db.executemany("INSERT INTO problem_set_members VALUES(?,?,?)",
                               [(set_id, problem_id, ordinal) for ordinal, problem_id in enumerate(problem_ids)])
            return _read_set(db, set_id)

    return router
