# Maths & Physics Study Vault

This repository is an existing personal Obsidian vault and a working source workspace for a proposed private, local-first study application. The vault remains the canonical home for human-readable topic notes; the application would add structured study state, generated editions, graphs, and research results around it.

## Current status

Product direction and implementation requirements are documented, and the application foundation is in development. React/TypeScript and Python/FastAPI remain proposed stack choices. SQLite persistence and an SDK harness are accepted; the specific SDK is pending comparison. No SDK benchmark has been run; the user has authorized the trial, and its numeric budget remains unresolved.

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

There is no application development command yet. Add setup and run instructions here once the implementation milestone establishes the actual toolchain; do not document proposed commands as working commands.
