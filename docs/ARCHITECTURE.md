# Proposed architecture and data boundaries

Status: architecture baseline captured; application foundation is in development. Requirements in [PRODUCT.md](PRODUCT.md) and accepted decisions in [DECISIONS.md](DECISIONS.md) take precedence over proposals below.

## Proposed components

1. **Browser UI** — React/TypeScript study workspace for library, reading editions, checks, problem assistance, research graph, and Atlas review.
2. **Local application service** — Python/FastAPI for explicit commands, persistence, file access, and agent orchestration. Bind locally; agent actions must be attributable to a user command.
3. **Study store** — SQLite database for metadata, checks, study status, edition/revision records, research results, graph nodes/edges, and operation status.
4. **Vault** — existing Obsidian Markdown tree remains the human-readable canonical topic-note store. App-created or updated notes must respect manual intent and retain source links.
5. **Source files** — original PDFs and other source documents remain user-owned files outside Git. The app stores metadata and a stable reference; copy/import behavior is an open question.
6. **Agent harness** — an SDK harness with narrowly scoped vault, tools, web, math, and skills capabilities. The SDK choice is pending the authorized trial.

## Data ownership and invariants

- **Markdown/Obsidian owns canonical topic prose.** SQLite may index it but must not become a competing canonical copy.
- **SQLite owns operational study state and structured research records.** Include explicit source provenance for derived records.
- **Source files own original content and notation.** Reading editions maintain source order; normalized Atlas notation never overwrites original source representation.
- **Generated editions are immutable published artifacts by revision.** Internal progress checkpoints may be persisted; publish only when generation is complete. A regeneration creates a new revision and does not silently rewrite the user's current reading state.
- **Study checks have history.** Current marks and historical imported marks must be separable and dated.
- **Signoff synthesis consumes only checked material.** Record the signoff and source/check set so the Atlas contribution can be explained.
- **Unchecking is non-destructive to Atlas.** A later material edit to signed-off material is pending reconfirmation, not automatic retraction.
- **Agent operations have explicit intent and visible status.** Browsing, graph expansion, and hint reveal remain local operations.

## Proposed command lifecycle

```text
source metadata -> explicit Prepare -> agent completes edition content -> persist complete artifact -> render
clarification chat submission -> background revision job -> explicit Refresh -> preserve checks + reading position
checked study unit -> explicit Signoff -> background synthesis -> proposed/recorded Atlas changes + provenance
research request -> explicit Start research -> evidence-backed records -> local graph browse/expand
problem reveal -> show selected prerecorded level (no agent operation)
```

The implementation should represent operations as stateful records (requested/running/completed/failed/cancelled) with inputs, outputs, and provenance. Do not expose generated output as a completed edition until all required generation is complete and validated.

## Backup boundary

A recoverable backup must include the SQLite database, referenced assets, vault Markdown, and any keys needed to recover protected data. Git alone is not a backup of PDFs or local state. Destination, encryption, retention, and key recovery remain open decisions; document and demonstrate restore before v1 completion.

## Security and cost boundaries

- Keep credentials and keys outside Git and outside generated note content.
- Agent/web access is mediated by explicit user actions and declared tools. Record which sources and tools supported a result.
- Require a configured paid-trial budget before invoking any paid SDK/model/web service. Cost estimates may be shown as actual/observed amounts after execution, never as study-time predictions.
- Solution material must not enter default prompts, search results, or general retrieval before its explicit reveal. Encryption and reveal implementation await the open threat-model decision.
