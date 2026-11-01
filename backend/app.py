"""Optional FastAPI adapter. Set MATHSPHYS_DB to choose the SQLite file."""
import os
from fastapi import FastAPI, HTTPException, Query
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

@app.post("/sources", status_code=201)
def register_source(body: SourceIn):
    try: return store.register_source(body.title, body.metadata, body.sections)
    except (ValueError, KeyError) as e: raise HTTPException(400, str(e))

@app.get("/sources")
def list_sources(): return store.sources()

@app.get("/sources/{source_id}")
def get_source(source_id: str):
    result = store.get_source(source_id)
    if result is None: raise HTTPException(404, "source not found")
    return result

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
