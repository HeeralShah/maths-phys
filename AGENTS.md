# Agent instructions

This repository is a private study vault and the source workspace for a proposed local study application. Treat existing Obsidian notes and source files as user data.

## Before changing the project

- Read [the product requirements](docs/PRODUCT.md) and [the decision log](docs/DECISIONS.md) for product work.
- Read [the architecture](docs/ARCHITECTURE.md) before changing persistence, integrations, or data boundaries.
- Read [the implementation tracker](docs/IMPLEMENTATION.md) before claiming scope or completion.
- Read [the SDK trial protocol](docs/SDK-TRIAL.md) before running any agent SDK evaluation. The SDK comparison is authorized but has not been run; record its numeric budget first.
- Keep [GLOSSARY.md](GLOSSARY.md) authoritative for domain terms; implementation choices belong in docs, not the glossary.

## Data and behavior guardrails

- Preserve the existing Obsidian vault and its notes. Build on it; do not replace or reformat the vault wholesale.
- Treat source PDFs as user-owned inputs. Do not commit PDFs, databases, credentials, caches, or generated temporary images.
- AI calls that cost money or change durable study state require a direct, explicit user action. Browsing, graph expansion, and hint reveal are local operations and never start agent generation.
- Complete generation before publishing the rendered study edition; internal progress checkpoints may be persisted, but partial output is not a complete published edition.
- Keep source notation in reading editions and normalized notation in canonical Atlas notes; retain provenance between them.
- Record implementation evidence in the tracker. Mark a milestone complete only when every acceptance criterion listed for it has evidence.
