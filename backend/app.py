"""Optional FastAPI adapter. Set MATHSPHYS_DB to choose the SQLite file."""
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from .store import Store
from .vault import read_note, search_notes
from .problem_sets import build_router as build_problem_sets_router

store = Store(os.environ.get("MATHSPHYS_DB", "maths_phys.sqlite3"))
app = FastAPI(title="Maths-Phys local service", version="0.1.0")
app.include_router(build_problem_sets_router(store))

class SourceIn(BaseModel):
    title: str
    metadata: dict = Field(default_factory=dict)
    sections: list[dict] = Field(default_factory=list)

class RevisionIn(BaseModel): content: str
class CheckIn(BaseModel): check_type: str; passed: bool; detail: str = ""
class SignoffIn(BaseModel): scope: str = ""; actor: str; idempotency_key: str; intent: str = Field(default="", max_length=300)
class JobIn(BaseModel): job_type: str; entity_id: str; idempotency_key: str; payload: dict = Field(default_factory=dict)
class EvidenceIn(BaseModel): locator: str; quote: str; source_ref: str | None = None; metadata: dict = Field(default_factory=dict)
class NodeIn(BaseModel): source_id: str; node_type: str; label: str; claim: str; metadata: dict = Field(default_factory=dict); evidence: list[EvidenceIn]
class NodeUpdateIn(BaseModel): node_type: str; label: str; claim: str; metadata: dict = Field(default_factory=dict); evidence: list[EvidenceIn]
class EdgeEvidenceIn(EvidenceIn): source_id: str
class EdgeIn(BaseModel): from_id: str; to_id: str; relation: str; claim: str; metadata: dict = Field(default_factory=dict); evidence: list[EdgeEvidenceIn]
class EdgeUpdateIn(EdgeIn): pass
class ProblemIn(BaseModel):
    source_id: str; prompt: str; placement: str; placement_ref: str | None = None; subject: str
    prerequisites: list = Field(default_factory=list); novelty: str; combination: str; workload: str
    provenance: EvidenceIn; experience: str; difficulty: dict | None = None; assistance: dict
class RevealIn(BaseModel): level: str
class RegisterPdfIn(BaseModel): path: str; title: str = ""; metadata: dict = Field(default_factory=dict); sections: list[dict] = Field(default_factory=list)
class PreparedEditionIn(BaseModel): complete: bool; edition: dict; problems: list[dict] = Field(default_factory=list); graph: dict = Field(default_factory=dict); publication_key: str | None = None
class AttemptIn(BaseModel): response: str; outcome: str; details: str = ""
class ProfileIn(BaseModel): goals: str = ""; assumed_knowledge: list[str] = Field(default_factory=list); misconceptions: list[str] = Field(default_factory=list); preferred_explanations: str = ""; preferences: dict = Field(default_factory=dict); notes: str = ""

VAULT_ROOT = Path(os.environ.get("MATHSPHYS_VAULT", Path(__file__).resolve().parents[1] / "vault")).resolve()

@app.post("/sources", status_code=201)
def register_source(body: SourceIn):
    try: return store.register_source(body.title, body.metadata, body.sections)
    except (ValueError, KeyError) as e: raise HTTPException(400, str(e))

@app.get("/sources")
def list_sources(): return store.sources()

@app.get("/profile")
def get_profile(): return store.get_learning_profile()

@app.put("/profile")
def update_profile(body: ProfileIn):
    try: return store.update_learning_profile(body.model_dump())
    except ValueError as e: raise HTTPException(400, str(e))

@app.get("/sources/{source_id}")
def get_source(source_id: str):
    result = store.get_source(source_id)
    if result is None: raise HTTPException(404, "source not found")
    return result

@app.post("/sources/register-file", status_code=201)
def register_pdf(body: RegisterPdfIn):
    try: return store.register_pdf(body.title, body.path, body.metadata, body.sections)
    except (ValueError, OSError) as e: raise HTTPException(400, str(e))

@app.get("/sources/{source_id}/pages/{page_number}")
def source_page(source_id: str, page_number: int):
    try: return store.source_page(source_id, page_number)
    except KeyError as e: raise HTTPException(404, str(e))
    except (ValueError, OSError) as e: raise HTTPException(400, str(e))

@app.get("/sources/{source_id}/pdf")
def source_pdf_page(source_id: str, page: int = Query(ge=1)):
    return source_page(source_id, page)

@app.post("/sources/{source_id}/editions/import", status_code=201)
def import_edition(source_id: str, body: PreparedEditionIn):
    try: return store.import_prepared_edition(source_id, body.model_dump(exclude={"publication_key"}), body.publication_key)
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(400, str(e))

@app.get("/vault/search")
def search_vault(q: str = Query(min_length=1, max_length=300)):
    try: return search_notes(VAULT_ROOT, q)
    except (OSError, ValueError) as e: raise HTTPException(400, str(e))

@app.get("/vault/notes/{relative_path:path}")
def read_vault_note(relative_path: str):
    try: return read_note(VAULT_ROOT, relative_path)
    except FileNotFoundError as e: raise HTTPException(404, str(e))
    except (OSError, ValueError) as e: raise HTTPException(400, str(e))

@app.get("/research/graph")
def research_graph(source_id: str | None = None):
    try: return store.research_graph(source_id)
    except KeyError as e: raise HTTPException(404, str(e))

@app.post("/research/nodes", status_code=201)
def create_research_node(body: NodeIn):
    try: return store.create_research_node(body.source_id, body.node_type, body.label, body.claim, body.metadata, [x.model_dump() for x in body.evidence])
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(400, str(e))

@app.get("/research/nodes/{node_id}")
def get_research_node(node_id: str):
    result = store.get_research_node(node_id)
    if result is None: raise HTTPException(404, "graph node not found")
    return result

@app.put("/research/nodes/{node_id}")
def update_research_node(node_id: str, body: NodeUpdateIn):
    try: return store.update_research_node(node_id, body.node_type, body.label, body.claim, body.metadata, [x.model_dump() for x in body.evidence])
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(400, str(e))

@app.delete("/research/nodes/{node_id}", status_code=204)
def delete_research_node(node_id: str):
    if not store.delete_research_node(node_id): raise HTTPException(404, "graph node not found")

@app.post("/research/edges", status_code=201)
def create_research_edge(body: EdgeIn):
    try: return store.create_research_edge(body.from_id, body.to_id, body.relation, body.claim, body.metadata, [x.model_dump() for x in body.evidence])
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(400, str(e))

@app.get("/research/edges/{edge_id}")
def get_research_edge(edge_id: str):
    result = store.get_research_edge(edge_id)
    if result is None: raise HTTPException(404, "graph edge not found")
    return result

@app.put("/research/edges/{edge_id}")
def update_research_edge(edge_id: str, body: EdgeUpdateIn):
    try: return store.update_research_edge(edge_id, body.from_id, body.to_id, body.relation, body.claim, body.metadata, [x.model_dump() for x in body.evidence])
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(400, str(e))

@app.delete("/research/edges/{edge_id}", status_code=204)
def delete_research_edge(edge_id: str):
    if not store.delete_research_edge(edge_id): raise HTTPException(404, "graph edge not found")

@app.get("/problems")
def list_problems(source_id: str | None = None, q: str | None = Query(default=None, max_length=300)):
    try: return store.list_problems(source_id, q)
    except KeyError as e: raise HTTPException(404, str(e))

@app.post("/problems", status_code=201)
def create_problem(body: ProblemIn):
    try: return store.create_problem(body.source_id, body.prompt, body.placement, body.placement_ref,
        body.subject, body.prerequisites, body.novelty, body.combination, body.workload,
        body.provenance.model_dump(), body.experience, body.difficulty, body.assistance)
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(400, str(e))

@app.get("/problems/{problem_id}")
def get_problem(problem_id: str):
    result = store.get_problem(problem_id)
    if result is None: raise HTTPException(404, "problem not found")
    return result

@app.post("/problems/{problem_id}/reveal")
def reveal_problem(problem_id: str, body: RevealIn):
    try: return store.reveal_problem_level(problem_id, body.level)
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(400, str(e))

@app.post("/problems/{problem_id}/attempts", status_code=201)
def record_attempt(problem_id: str, body: AttemptIn):
    try: return store.record_problem_attempt(problem_id, body.response, body.outcome, body.details)
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(400, str(e))

@app.get("/problems/{problem_id}/attempts")
def problem_attempts(problem_id: str):
    try: return store.problem_attempts(problem_id)
    except KeyError as e: raise HTTPException(404, str(e))

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

@app.get("/revisions/{revision_id}/annotations")
def imported_annotations(revision_id: str):
    try: return store.imported_annotations(revision_id)
    except KeyError as e: raise HTTPException(404, str(e))

@app.post("/sections/{section_id}/signoffs", status_code=202)
def signoff_section(section_id: str, body: SignoffIn):
    try: return store.signoff_section(section_id, body.actor, body.idempotency_key, body.intent)
    except KeyError: raise HTTPException(404, "section not found")
    except ValueError as e: raise HTTPException(400, str(e))

@app.post("/atlas/apply-plan")
def apply_atlas_plan(body: dict):
    try: return store.apply_synthesis_plan(VAULT_ROOT, body)
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(409, str(e))

@app.get("/synthesis-plans/{plan_id}")
def get_synthesis_plan(plan_id: str):
    result = store.get_synthesis_plan(plan_id)
    if result is None: raise HTTPException(404, "synthesis plan not found")
    return result

@app.post("/synthesis-plans/{plan_id}/apply")
def apply_imported_synthesis_plan(plan_id: str):
    try: return store.apply_imported_synthesis_plan(plan_id, VAULT_ROOT)
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(409, str(e))

@app.post("/synthesis-plans/{plan_id}/commit")
def retry_synthesis_commit(plan_id: str):
    try: return store.apply_imported_synthesis_plan(plan_id, VAULT_ROOT)
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(409, str(e))

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
