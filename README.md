# Maths & Physics Study Vault

This repository is an existing personal Obsidian vault and a working source workspace for a proposed private, local-first study application. The vault remains the canonical home for human-readable topic notes; the application would add structured study state, generated editions, graphs, and research results around it.

## Current status

The local application foundation is in development. The backend has SQLite persistence and a FastAPI adapter for source metadata, immutable edition revisions, dated checks, section signoff snapshots, and durable job requests with status/idempotency/recovery primitives. The frontend scaffold is being built. The agent worker is unconfigured, so preparation/revision/signoff jobs are recorded but no agent generation or synthesis runs. Research graphs, literature views, problem library, and hint UI are not implemented yet.

React/TypeScript and Python/FastAPI are the current stack choices. SQLite persistence and the SDK harness shape are accepted; the specific SDK awaits the authorized comparison. No SDK benchmark has been run. The total trial spending cap is £20 across all providers, cases, retries, and paid tools.

## Project documents

- [Product requirements](docs/PRODUCT.md): behavior, user-visible requirements, and acceptance criteria.
- [Decision log](docs/DECISIONS.md): accepted direction, proposals, and unresolved choices.
- [Architecture](docs/ARCHITECTURE.md): data boundaries and proposed component shape.
- [Implementation tracker](docs/IMPLEMENTATION.md): milestones and readiness checks.
- [SDK trial protocol](docs/SDK-TRIAL.md): a reproducible, budget-gated evaluation plan.
- [Domain glossary](GLOSSARY.md): project vocabulary.

## Existing vault

The root folders `00 Home`, `01 System`, `02 Atlas`, `90 Inbox`, and `99 Archive`, along with `.obsidian`, are existing user material. Preserve them. Git is intended for private versioning of source notes, application code, schemas, and documentation. Keep source PDFs, local SQLite state, credentials, virtual environments, caches, and temporary artifacts out of Git.

## Development

Commands below use the repository's existing Windows virtual environment and package scripts. Run them from the repository root unless a directory change is shown.

### Backend unit tests

The backend currently has seven standard-library unit tests covering durable revisions/checks, signoff selection, idempotent job requests, job transitions, stale-job recovery, and the unconfigured worker boundary.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -p "test_*.py"
```

### Local API

Set the local database path and start the FastAPI service:

```powershell
$env:MATHSPHYS_DB = "maths_phys.sqlite3"
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

The API stores a local SQLite database. Back it up with the service stopped. Do not commit the database.

### Frontend

```powershell
Set-Location frontend
npm install
npm run dev
```

Build the frontend with:

```powershell
Set-Location frontend
npm run build
```

The dev server binds to `127.0.0.1`. The app is still under development; the full study workflows and agent-backed jobs are not available yet.
