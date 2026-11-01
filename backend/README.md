# Local backend

SQLite-backed local service for source outlines, immutable unit editions, manual
checks, partial signoffs and durable synthesis job requests. Source registration
stores metadata and an optional section/unit outline only; it does not upload or
process source material. Reads and manual checks do not enqueue jobs or call a
model. No model SDK is configured; `worker_protocol.py` marks that boundary and
fails clearly while retaining queued jobs.

The schema includes sources, sections, units, immutable revisions, checks,
append-only events, scoped signoffs, jobs, graph nodes/edges, problems, and
problem hint/solution metadata. Manual `understood` checks are append-only state
changes: a later false check retracts understanding for that revision. Section
signoff snapshots only units whose latest edition is currently marked understood,
so a partial section (for example, 6 of 8 units) queues a job for those six units.
Jobs have stable UUIDs and caller-provided unique idempotency keys; supported
types are `prepare`, `revise`, and `signoff`.

Research records use the evidence-linked `research_nodes`, `research_edges`,
and evidence tables. Node claims require at least one source locator and quote;
edges require evidence too and accept `cites`, `requires`, `extends`, or
`assumes`. Local graph reads and mutations never enqueue work. The HTTP API
provides `GET /sources`, `GET /research/graph`, node and edge GET/POST/PUT/DELETE
routes under `/research`, and `GET /problems` for source-only exercise search.
Problem creation accepts `inline`, `chapter_end`, and `problem_set` placements,
the qualitative dimensions and provenance, plus all five prerecorded assistance
levels. Ordinary problem listing/detail and search never include assistance.
`POST /problems/{id}/reveal` returns only the explicitly requested level and
does not create a job. Full solutions are protected at rest: Windows uses the
current user's DPAPI; other platforms use Fernet with a mode-0600 key alongside
the configured database (`<database>.solution.key`). That fallback key must be
included in any manual backup and protected like the database. Windows DPAPI
blobs can be recovered only under the same Windows user profile; include the
database in backups and retain access to that profile. Existing plaintext rows
in the legacy `problem_material` solution table are encrypted during startup.
No API exposes that legacy table.

Problem difficulty is a qualitative assessment and factual reason. The problem
schema contains no duration or time-estimate field. Prerequisites are stored as
provided; when a prerequisite names another problem ID, it must identify a
problem in the same source.

Worker-facing store methods claim the oldest queued job atomically, allow only a
running job to become succeeded or failed, and can requeue running jobs whose
lease timestamp is stale. These are persistence primitives; the included worker
stub still refuses to execute or complete jobs until an actual worker is
configured.

Use Python 3.10+. The storage and tests use only the standard library:

```powershell
python -m unittest discover -s backend -p "test_*.py"
```

For the optional HTTP API, install `backend/requirements.txt` and run from the
repository root:

```powershell
$env:MATHSPHYS_DB = "maths_phys.sqlite3"
uvicorn backend.app:app --reload
```

The SQLite database is local and durable. Back it up with the service stopped.
