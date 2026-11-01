# Local backend

SQLite-backed local service for source outlines, immutable unit editions, manual
checks, partial signoffs and durable synthesis job requests. Source registration
stores metadata and an optional section/unit outline only; it does not upload or
process source material. Reads and manual checks do not enqueue jobs or call a
model. PDFs can be explicitly registered by local path with `POST /sources/register-file`;
the API stores the canonical path and a SHA-256 fingerprint. `GET /sources/{id}/pdf?page=N`
only serves a registered PDF and refuses it if its bytes have changed. This route
extracts text and renders that selected page; registration itself does not parse it.
No model SDK is configured; `worker_protocol.py` marks that boundary and
fails clearly while retaining queued jobs.

The schema includes sources, sections, units, immutable revisions, checks,
append-only events, scoped signoffs, jobs, graph nodes/edges, problems, and
problem hint/solution metadata, historical imported annotations and problem
attempts. Manual `understood` checks are append-only state
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
Complete prepared packages can be imported at `POST /sources/{id}/editions/import`.
All units and optional problems are validated before publication and committed in
one SQLite transaction; each unit receives an immutable revision with source
references retained in its event provenance. Historical annotations are stored
separately from current checks and read at `/revisions/{revision_id}/annotations`.
The canonical vault is searched and read through `GET /vault/search?q=` and
`GET /vault/notes/{relative_path}`; reads are constrained to Markdown beneath
`MATHSPHYS_VAULT` (default `vault/`).
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
Attempts are durable learner experience records available at
`POST /problems/{id}/attempts` and `GET /problems/{id}/attempts`; they do not
invoke a worker.

Atlas plans name their signoff, use only revisions in that signoff, and require
those revisions to remain the latest checked-understood revisions. Each
Markdown target includes the SHA-256 observed during plan preparation (use
`null` for a new note). Writes stage and replace files, journal originals for
rollback, and use an idempotency key. Startup restores interrupted applications
before serving requests. A changed signed-off revision requires a new signoff.

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

## Optional Claude worker

The worker is separate from the API process and is never launched automatically.
Install `backend/requirements-claude.txt` only when selecting Claude, then set
`MATHSPHYS_AGENT_ENABLED=1`, `MATHSPHYS_AGENT_PROVIDER=claude`, an explicit
`MATHSPHYS_AGENT_MODEL`, `MATHSPHYS_AGENT_MAX_TURNS`,
`MATHSPHYS_AGENT_JOB_BUDGET_USD`, `MATHSPHYS_AGENT_TOTAL_BUDGET_USD`, and
`ANTHROPIC_API_KEY`. The worker reserves the per-job budget against a SQLite
lifetime ledger before a call and leaves queued jobs queued when the configured
total headroom is exhausted. SDK-estimated cost is recorded after a completed
run; when a run ends without a cost report, the full reservation is retained.
The Claude SDK documents that its `max_budget_usd` is a client-side estimate and
can pass the configured value by one API call, so configure the per-job limit
with headroom.

Run one explicitly queued job or start polling manually:

```powershell
python -m backend.claude_worker --once
python -m backend.claude_worker --loop --poll-seconds 2
```

The worker exposes only registered PDF page read/render and contained vault
read/search tools to the SDK. It imports a prepared edition only after the full
JSON package declares `complete: true` and passes atomic package validation. A
signoff job validates and applies a synthesis plan from its checked snapshot
before completing. Review the saved plan through `GET /synthesis-plans/{id}`.
Applied plans create a local commit for only their Atlas note paths, using the
signoff intent or a descriptive message. The worker never pushes. If Git is
unavailable or committing fails, the note stays applied and the plan is marked
`applied_unversioned`; retry after fixing repository configuration through
`POST /synthesis-plans/{id}/commit`.

## Google ADK / Agent Runtime foundation

`google_agent_worker.py` is the opt-in provider boundary for **our custom ADK
application deployed on Gemini Enterprise Agent Platform Agent Runtime**. It is
not an adapter for the prebuilt Gemini API Antigravity managed agent. The newer
`google-antigravity` Python SDK is also not a production dependency; it remains
a separate quality-trial candidate.

The module performs no SDK import, credential lookup, database write, upload or
model call when imported. After the durable worker has claimed an explicitly
requested job and reserved its budget, the adapter:

1. verifies the registered source SHA-256;
2. preserves an entire selected chapter as an in-memory native PDF (copying
   selected pages without rasterising them);
3. sends the PDF and a versioned task envelope to an already deployed ADK
   `ReasoningEngine`;
4. captures usage events, extracts untrusted JSON and runs the provider-neutral
   artifact validator; and
5. returns the artifact and estimated cost to the durable worker. It never
   settles the ledger or publishes an edition itself.

Install the optional client only when configuring this route:

```powershell
python -m pip install -r backend/requirements-google.txt
```

Authentication uses Google Application Default Credentials rather than a key
stored in this repository. Required configuration is deliberately explicit:

```powershell
$env:MATHSPHYS_AGENT_ENABLED = "1"
$env:MATHSPHYS_AGENT_PROVIDER = "google-adk"
$env:GOOGLE_CLOUD_PROJECT = "your-project"
$env:GOOGLE_CLOUD_LOCATION = "europe-west2"
$env:MATHSPHYS_GOOGLE_RUNTIME = "projects/your-project/locations/europe-west2/reasoningEngines/offline-resource-id"
$env:MATHSPHYS_AGENT_MODEL = "your-deployed-gemini-model"
$env:MATHSPHYS_AGENT_MAX_LLM_CALLS = "6"
$env:MATHSPHYS_AGENT_MAX_TOTAL_TOKENS = "100000"
$env:MATHSPHYS_AGENT_JOB_BUDGET_USD = "1.00"
$env:MATHSPHYS_AGENT_TOTAL_BUDGET_USD = "20.00"
```

Ordinary preparation always uses the offline resource. Research is rejected
unless a different `MATHSPHYS_GOOGLE_RESEARCH_RUNTIME` is configured and the
job itself explicitly includes `allow_web_research: true`. Tool and network
policy belong in those deployed ADK revisions; the local adapter cannot make an
online runtime safe merely by labelling a request “offline.”

`RunConfig.max_llm_calls` is sent on every request. The requested total-token
and monetary envelopes are also included for enforcement by callbacks in the
deployed ADK application; Agent Runtime does not turn those application fields
into a hard cross-sub-agent budget automatically. The local pre-call budget
reservation remains the hard gate, and unknown usage retains that reservation.

The foundation currently uses `async_stream_query` with a default nine-minute
timeout, below Agent Runtime's ten-minute streaming limit. Google's longer
query-job API writes both the input query and output to GCS; it is intentionally
not an automatic fallback until a private bucket, deletion policy, cancellation
and job-recovery path are designed.

The adapter foundation is tested with injected transports and fake events; it
does not make a credentialed call:

```powershell
python -m unittest backend.test_google_agent_worker -v
```

Before paid work is enabled, the ADK package still needs to be deployed and its
native-PDF request, callbacks, region/retention settings and output contract
must pass the representative sample protocol. See
`docs/research/google-managed-agent-options.md` for the product comparison,
privacy constraints and current chapter cost model.
