"""Optional FastAPI adapter. Set MATHSPHYS_DB to choose the SQLite file."""
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .store import Store

store = Store(os.environ.get("MATHSPHYS_DB", "maths_phys.sqlite3"))
app = FastAPI(title="Maths-Phys local service", version="0.1.0")

class SourceIn(BaseModel):
    title: str
    metadata: dict = Field(default_factory=dict)
    sections: list[dict] = Field(default_factory=list)

class RevisionIn(BaseModel): content: str
class CheckIn(BaseModel): check_type: str; passed: bool; detail: str = ""
class SignoffIn(BaseModel): scope: str = ""; actor: str; idempotency_key: str
class JobIn(BaseModel): job_type: str; entity_id: str; idempotency_key: str; payload: dict = Field(default_factory=dict)

@app.post("/sources", status_code=201)
def register_source(body: SourceIn):
    try: return store.register_source(body.title, body.metadata, body.sections)
    except (ValueError, KeyError) as e: raise HTTPException(400, str(e))

@app.get("/sources/{source_id}")
def get_source(source_id: str):
    result = store.get_source(source_id)
    if result is None: raise HTTPException(404, "source not found")
    return result

@app.put("/units/{unit_id}/revisions")
def save_revision(unit_id: str, body: RevisionIn):
    try: return store.save_revision(unit_id, body.content)
    except KeyError: raise HTTPException(404, "unit not found")

@app.get("/units/{unit_id}/edition")
def read_edition(unit_id: str): return store.read_edition(unit_id)

@app.post("/revisions/{revision_id}/checks", status_code=201)
def add_check(revision_id: str, body: CheckIn):
    try: return store.add_check(revision_id, body.check_type, body.passed, body.detail)
    except KeyError: raise HTTPException(404, "revision not found")

@app.get("/revisions/{revision_id}/checks")
def get_checks(revision_id: str): return store.get_checks(revision_id)

@app.post("/sections/{section_id}/signoffs", status_code=202)
def signoff_section(section_id: str, body: SignoffIn):
    try: return store.signoff_section(section_id, body.actor, body.idempotency_key)
    except KeyError: raise HTTPException(404, "section not found")
    except ValueError as e: raise HTTPException(400, str(e))

@app.post("/jobs", status_code=202)
def enqueue_job(body: JobIn):
    try: return store.enqueue(body.job_type, body.entity_id, body.idempotency_key, body.payload)
    except ValueError as e: raise HTTPException(400, str(e))

@app.get("/jobs")
def jobs(status: str | None = None): return store.jobs(status)

@app.get("/jobs/{job_id}")
def job(job_id: str):
    result = store.get_job(job_id)
    if result is None: raise HTTPException(404, "job not found")
    return result
