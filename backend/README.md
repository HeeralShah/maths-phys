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
