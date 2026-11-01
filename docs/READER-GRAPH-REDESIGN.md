# Chapter reader and literature-map redesign

Status: proposed product correction for review. This document audits the current implementation and defines the replacement model. It does not select an agent provider and it does not authorize a paid call.

## Decision summary

The current reader and graph should not be incrementally restyled. Their stored models encode the wrong things.

1. A prepared reading edition is one complete chapter-scale artifact, not a collection of explanatory Markdown cards prepared page by page.
2. Source content and agent commentary are separate, immutable layers. Commentary is anchored to exact source passages, equations, figures, or positions between source blocks.
3. The main reading surface is the faithful source in its original order. Short annotations appear in the reading flow; derivation bridges appear between the formula lines they explain; longer material is progressively disclosed.
4. Understanding is checked against small checkable items inside the chapter. It is not a single flag on a whole Markdown revision.
5. A research graph is a literature map centred on one paper. Its canvas nodes are works in the literature, not headings, reading steps, assumptions, or other pieces of the same document.
6. Sections, results, assumptions, and contributions of the focal paper remain important, but they are records and filters attached to literature relationships, not default graph nodes.
7. Preparing a reading edition and researching the literature are separate explicit jobs. Edition preparation may extract the focal paper's own bibliography, but it must not silently perform paid external literature research.

These are changes to the domain model, persistence contract, agent output contract, and frontend composition. CSS changes alone cannot produce the intended product.

## What is wrong in the current build

### Reader

The present reader treats `revisions.content` as an opaque Markdown string. Prepared content mixes faithful transcription, expanded derivation, interpretation, assumptions, correction, and exercises under headings in the same blob. `foldEditionSections()` in `frontend/src/main.tsx` then turns the headings into stacked `<details>` cards.

Consequences:

- The source is no longer the stable visual spine of the document.
- An explanation cannot be placed precisely between the two formula lines it connects.
- The UI cannot distinguish source words from generated words without parsing conventions such as `### Source text`.
- A correction cannot preserve the erroneous source statement and attach a distinct correction reliably.
- A formula manipulation has no structured operands, correspondences, or transformation rule from which to draw highlights and arrows.
- User text selection is saved as `{color, text}` and the renderer highlights the first matching text node. Repeated phrases, formulas split across nodes, edits, and revised editions make that anchor unstable.
- A current understanding check belongs to an entire unit revision. This is too coarse for a chapter and conflates the publication container with the learner's checkable item.
- The preparation UI asks for arbitrary physical pages and describes the result as selected pages. It does not model or publish a complete source chapter.

The existing B6La package illustrates the limitation. Its mathematical content can be sound while its structure still forces the explanation to appear after a full transcription rather than at the exact transition being explained.

### Research graph

The present graph accepts arbitrary `research_nodes` with a `node_type`, `claim`, and `source_id`. The saved Keshav map consequently places a paper, passes, checklists, decisions, survey steps, and bibliography entries on the same canvas. A fixed four-column SVG grid connects them with generic `requires`, `extends`, `assumes`, and `cites` edges.

Consequences:

- The graph visualizes the internal structure of one document rather than that document's place in literature.
- A paper and a reading instruction have the same visual status even though they are different kinds of entity.
- `source_id` conflates the entity being described with the source supplying evidence. An external cited work may not be a locally registered source at all.
- A source filter selects nodes and edges through evidence provenance; it does not select a coherent focal-paper map.
- Bibliographic citation and intellectual dependence are not separated strongly enough.
- There is no durable bibliographic identity for a work, no map revision, no role relative to the focal work, and no section-level context attached to a relationship.
- A uniform grid provides no visual semantics for predecessor, contemporary, or downstream work.

Keshav's reading process is useful application guidance and can be represented as a reading edition or method note. It should not be presented as the exemplar literature graph.

## Proposed vocabulary

These terms are proposed here and should be added to `GLOSSARY.md` only after they are accepted.

**Preparation scope**: the complete source range selected for one preparation operation. For the initial product this is normally a chapter, or the whole document when the document is already one chapter or paper.

**Chapter edition**: an immutable, completely published reading artifact for one preparation scope. A revision contains all ordered source blocks, anchored annotations, checkable items, and source-only problem links needed to render that scope.

**Source block**: an ordered, faithful unit of source content: heading, paragraph, display equation, figure, table, list, example, footnote, or exercise. It is a rendering and anchoring unit, not necessarily a study unit.

**Annotation**: a historical, generated, or learner-authored addition that does not replace source content. It has an intent, visual role, placement, provenance, and one or more anchors.

**Annotation anchor**: a durable pointer to a source block, quoted range, equation, figure region, or gap between source blocks. Raw character offsets alone are not durable enough.

**Derivation bridge**: a structured annotation placed between source formula lines that exposes omitted transformations. It can identify corresponding terms, introduced or cancelled factors, and the rule used at each step.

**Checkable item**: a small coherent claim, equation group, proof move, definition, or paragraph cluster for which the learner can record current understanding. The preparation agent proposes its boundaries.

**Work**: a bibliographically identifiable paper, book, thesis, set of notes, or other publication. A work may have a locally registered source, but does not require one.

**Literature map**: a revisioned, evidence-backed view of works related to one focal work.

**Literature relationship**: a claim about how one work relates to another, distinct from the bare fact that one bibliography cites the other.

**Paper analysis record**: a result, assumption, contribution, method, or section summary belonging to one paper. These records support reading and filtering but are not default canvas nodes.

## Reader product model

### Scope selection

Source registration remains inert. Before paid preparation, the application offers detected structural scopes from the PDF table of contents, bookmarks, headings, and page geometry. Detection may be local and heuristic; any model-assisted detection is itself an explicit action.

The user explicitly prepares one scope:

- a chapter when the source is a book or full lecture-note set;
- the entire document when it is a paper or already a single chapter;
- an explicitly adjusted contiguous range when source structure is ambiguous.

Pages remain provenance and navigation markers. They are not the conceptual unit of generation or publication. A chapter can be longer than ten pages; the data model must not encode a five-to-ten-page maximum.

The job may inspect adjacent pages, earlier definitions, the Atlas, and cited sources as context without silently publishing those pages as part of the edition. Its output boundary remains the selected scope.

### Chapter publication invariant

A chapter edition revision can be published only when all of the following validate in one transaction:

1. The selected source range and source-file hash match the preparation request.
2. Every block in the selected range is represented once in source order, or has an explicit typed omission such as a decorative running header.
3. Faithful source text, formulas, figures, tables, numbering, and notation are retained.
4. Every annotation anchor resolves within the same edition revision.
5. Every derivation bridge has valid endpoints, ordered steps, and rendered mathematics.
6. Every checkable item resolves to one or more source blocks.
7. Extracted source problems resolve to their original positions.
8. The package declares itself complete and has passed schema and rendering validation.

An interrupted job may save private checkpoints, but the reader continues to show the prior complete revision. It never mixes completed pages with unfinished pages.

### Source and annotation layers

The browser composes two logical layers without visually separating them into two distant panes:

```text
chapter edition
  ordered source blocks                 faithful, immutable for the revision
    anchors and gaps                    stable attachment points
      historical annotations           imported source markup; current state unassessed
      generated annotations            derivation, intuition, correction, prerequisite, reference
      learner annotations               later personal marks or notes
    checkable items                     current understanding state, separate from annotation colour
```

Generated annotations should be brief at first sight. Their placement is part of the output contract:

| Intent | Default placement | Visual treatment |
|---|---|---|
| Omitted algebra/calculus move | Between the two relevant formula blocks | Compact derivation bridge with aligned equations, term colours, transformation label, and local arrows |
| Meaning of a symbol or phrase | Immediately after the phrase or in the near margin | One-line typographic note; expand only when necessary |
| Physical or mathematical intuition | Immediately after the claim it illuminates | Short warm-colour inline aside, not a detached essay |
| Hidden result or prerequisite | At first use | Green reference cue with the result stated briefly and a link to its Atlas note or source |
| Source mistake | Beside the original, which remains visible | Green issue marker plus a distinct correction line; never silently rewrite the source |
| Alternative derivation or long proof | At the relevant point | Collapsed detail whose summary states exactly what it adds |
| Source example | In original position | Faithful example, collapsible when long but never removed |
| Source exercise | In original position | Purple exercise treatment linked to the problem record |
| Historical learner mark | At its original anchor | Subdued facsimile cue labelled historical; it never checks current understanding |
| Current understanding | Beside the proposed checkable item | Explicit checkbox and date; the colour blue is optional presentation, not the state itself |

### Formula derivations

The faithful source equation should remain a single untouched LaTeX expression. To make manipulation visible without injecting unsafe markup into source LaTeX, the derivation bridge uses a structured duplicate of the relevant expressions.

Each bridge contains:

- the source equation blocks it connects;
- an ordered list of intermediate expression rows;
- expression segments with stable IDs and LaTeX;
- correspondences between segments in adjacent rows;
- a role for each changed segment: preserved, introduced, substituted, moved, cancelled, differentiated, integrated, or simplified;
- the mathematical rule or result used;
- optional Atlas/source provenance for a nontrivial rule;
- a compact explanation and an optional expanded proof.

The renderer places segment-level KaTeX fragments in aligned rows and draws local SVG connectors using measured segment positions. On a narrow screen or with reduced motion, arrows collapse to numbered correspondences and colour remains supplemented by labels. The renderer must never rely on colour alone.

This gives the requested visual account of formula changes while preserving the source equation verbatim above or below it.

### Reader layout

The default desktop view should be a document, not a dashboard of cards:

```text
+-------------------+-----------------------------------------------+---------------------+
| Chapter outline   | faithful chapter text                         | near-margin notes   |
| and page markers  |                                               | and checkboxes      |
|                   | equation A                                    | [ ] understood      |
|                   |   ↳ interline derivation bridge               |                     |
|                   | equation B                                    | intuition           |
|                   | short inline explanation in the reading flow  | source p. 18        |
+-------------------+-----------------------------------------------+---------------------+
```

- The centre column is continuous chapter prose with source page-boundary markers.
- The left outline navigates headings within the already loaded chapter.
- The right rail contains short notes and checkboxes anchored to the visible source blocks.
- Derivation bridges and short intuition notes appear in the centre flow where removing them would break comprehension.
- A source-page button opens the original rendered PDF page beside the reconstructed edition for fidelity checks.
- Local display controls can show source only, concise annotations, or all annotations. They do not call an agent.
- Scroll position is stored against a source-block key, not a brittle pixel offset.
- Clarification chat captures the selected anchor(s). Submission explicitly queues a revision. When complete, Refresh swaps to a whole new chapter revision and maps the old position and checks by stable semantic keys. A material change to a checked item requires reconfirmation.

## Reader persistence model

Use additive versioned tables rather than stretching `units`, `revisions`, and `checks` further.

### Source structure

`source_scopes`

| Column | Purpose |
|---|---|
| `id` | Stable scope identity |
| `source_id` | Registered source |
| `parent_scope_id` | Optional book/part hierarchy |
| `scope_kind` | `document`, `paper`, `chapter`, or `custom_range` |
| `title`, `ordinal` | Source title/order |
| `start_locator`, `end_locator` | Page plus optional source coordinate |
| `detection_method`, `confirmed_at` | Provenance of boundary selection |

`chapter_editions`

| Column | Purpose |
|---|---|
| `id`, `scope_id`, `revision` | Immutable published revision identity |
| `source_sha256` | File version prepared |
| `status` | Only `complete` editions are readable; checkpoints live elsewhere |
| `package_hash`, `publication_key` | Idempotent publication |
| `generator`, `model`, `prompt_version`, `skill_versions` | Reproducibility without secrets |
| `created_at` | Publication time |

### Document and annotations

`edition_blocks`

| Column | Purpose |
|---|---|
| `id`, `edition_id`, `stable_key` | Revision-local ID plus cross-revision semantic key |
| `parent_block_id`, `ordinal` | Document tree and source order |
| `block_kind` | Heading, paragraph, equation, figure, table, list, example, exercise, footnote |
| `source_content` | Faithful Markdown/LaTeX or typed JSON payload |
| `source_locator` | Page, printed page, label, and optional PDF bounding box |
| `content_hash` | Fidelity and anchor validation |

`edition_annotations`

| Column | Purpose |
|---|---|
| `id`, `edition_id`, `stable_key` | Annotation identity and revision mapping |
| `origin` | `historical`, `generated`, or `learner` |
| `intent` | Derivation, intuition, prerequisite, definition, correction, reference, warning, notation, or exercise guidance |
| `visual_role` | Green issue/reference, yellow explanation, blue historical-understood cue, purple exercise, neutral |
| `placement` | Inline-after, interlinear, near-margin, overlay, collapsed-detail |
| `body` | Markdown/LaTeX for ordinary annotations |
| `payload` | Typed JSON for derivation bridges or other structured visuals |
| `importance`, `confidence` | Density control and review signal; not hidden as certainty |
| `provenance` | Agent evidence, Atlas links, and source references |

`annotation_anchors`

| Column | Purpose |
|---|---|
| `annotation_id`, `ordinal` | Supports one annotation spanning multiple targets |
| `anchor_kind` | Whole block, quoted range, formula, figure region, or gap between blocks |
| `block_id`, `after_block_id`, `before_block_id` | Structural target |
| `exact_quote`, `prefix`, `suffix` | Web-annotation-style text selector and recovery context |
| `formula_label`, `segment_hint` | Optional mathematical selector |
| `bbox` | Optional page-space target for historical ink or figure regions |

`checkable_items`

| Column | Purpose |
|---|---|
| `id`, `edition_id`, `stable_key`, `ordinal` | Proposed check identity and cross-revision mapping |
| `item_kind`, `label` | Claim, equation group, proof move, definition, paragraph cluster |
| `anchor_spec` | One or more block/range anchors |
| `material_hash` | Decides whether a revised item needs reconfirmation |

`study_checks_v2`

| Column | Purpose |
|---|---|
| `id`, `checkable_item_id`, `understood`, `checked_at` | Learner's dated state |
| `carried_from_check_id` | Formatting-only carry-forward provenance |
| `reconfirmation_reason` | Material change explanation when applicable |

The package also links `source_problems` to an edition block or anchor. Problem assistance remains outside normal edition retrieval.

### Anchor durability

No single locator is sufficient. Each text anchor should combine:

1. revision-local block ID for exact rendering;
2. cross-revision stable block key;
3. exact quote plus prefix/suffix for recovery and validation;
4. page/bounding-box provenance where available;
5. a content hash to detect silent drift.

Formula anchors point primarily to an equation block. Segment-level structure belongs to the annotation payload; it should not pretend a model-generated token offset is a permanent coordinate in the original PDF.

## Reader API and job changes

Recommended v2 routes:

```text
GET  /sources/{source_id}/scopes
POST /sources/{source_id}/scopes/detect              explicit if agent-assisted
POST /source-scopes                                  confirm or adjust a scope locally
POST /source-scopes/{scope_id}/prepare                explicit paid/agent action
GET  /source-scopes/{scope_id}/editions/latest
GET  /chapter-editions/{edition_id}                   manifest + ordered blocks
GET  /chapter-editions/{edition_id}/annotations
GET  /chapter-editions/{edition_id}/checkable-items
POST /checkable-items/{item_id}/checks
POST /chapter-editions/{edition_id}/clarifications    anchored explicit revision request
POST /chapter-editions/{edition_id}/refresh           local switch after job completion
```

`prepare` jobs target `source_scope.id`, not an individual existing `unit.id` or arbitrary page string. The request records the confirmed source range and allowed context range. The provider-neutral worker contract returns one schema-versioned complete chapter package. Provider code must not define the package shape.

Edition import should no longer accept research graph data in the same package. It may accept source-only problems and the focal paper's verbatim bibliography because those are extracted from the selected source. External literature research is a separate explicit action.

## Literature-map product model

### Canvas boundary

For a selected focal paper, the graph canvas contains only works:

- the focal paper;
- important predecessor papers whose ideas, results, methods, or assumptions the focal paper uses;
- books or exposition genuinely important for understanding it;
- closely related or competing contemporary work when useful;
- downstream papers for which there is evidence of extension, application, generalisation, replication, or influence.

The graph must not create canvas nodes for the focal paper's sections, equations, claims, assumptions, Keshav passes, or generated reading notes.

Internal paper records still matter. Selecting a section in a paper outline filters or highlights the external works connected to that section. Selecting a literature edge shows which sections, results, and assumptions support the relationship.

### Separate facts from interpretations

At least three layers must remain distinct:

1. **Bibliographic fact**: work A cites work B; work C cites work A; metadata identity and date.
2. **Paper analysis**: the focal paper states an assumption, uses a named result, claims a contribution, or discusses work B in a particular section.
3. **Intellectual relationship**: work A extends, applies, generalises, contrasts with, depends on, or is later built upon by work B. This may be an evidence-backed inference and must say so.

A citation is evidence of citation only. It is not automatically evidence of intellectual influence, prerequisite status, or ancestry.

### Visual layout

Use a deterministic focal-paper layout rather than an arbitrary grid:

```text
foundational books       important explanatory works
          \                         /
predecessors  ----->  FOCAL PAPER  ----->  downstream works
    methods/results      |   |               extensions/applications
                         |   +-- competing/contemporary work
                         +------ section/result filters live off-canvas
```

- Time runs left to right when dates are known.
- Horizontal role lanes distinguish foundations, direct predecessors, contemporaries, and downstream work.
- Edge style encodes relationship semantics; it never uses direction alone to carry meaning.
- Node size may encode map importance chosen by the research agent, but not raw citation count without a visible label.
- Topic clusters can use restrained background regions. Avoid a different colour for every node type.
- The default map is curated and bounded. Dense citation neighborhoods are available through explicit local filters, not rendered all at once.
- A synchronized list/timeline view is required for accessibility and for cases where a graph is not the clearest view.
- Selecting a node or edge opens bibliographic metadata, a concise relationship explanation, all evidence, confidence/inference status, and links to local source/edition where present.

### Literature persistence model

`works`

| Column | Purpose |
|---|---|
| `id`, `work_type`, `title` | Local work identity |
| `authors`, `year`, `venue` | Normalized bibliographic fields |
| `doi`, `arxiv_id`, `isbn`, `external_ids` | Deduplication identifiers |
| `url`, `abstract` | Metadata with provider provenance |
| `metadata_provenance` | Provider/source, retrieval date, and raw identifier |

`source_works`

Links an optional local `source_id` to a `work_id`. This removes the assumption that every graph node is a registered local source.

`paper_analyses`

An immutable analysis revision for a focal work and optional chapter edition. It records scope, completion, model/tool provenance, and creation time.

`paper_records`

Typed records for section summaries, contributions, results, methods, assumptions, limitations, and notation. Each record has a locator and evidence. Assumptions additionally record whether they are stated, inherited, or inferred.

`literature_maps`

| Column | Purpose |
|---|---|
| `id`, `focal_work_id`, `revision` | One coherent map and its immutable revision |
| `status`, `package_hash` | Complete publication and idempotency |
| `research_scope`, `cutoff_reason` | Why these works are included and exploration stopped |
| `provider_provenance`, `created_at` | Reproducibility and freshness |

`literature_map_works`

Associates a work with the map and assigns one or more roles: focal, foundation, predecessor, contemporary, downstream, or explanatory. Includes an importance reason and display lane.

`literature_relationships`

| Column | Purpose |
|---|---|
| `from_work_id`, `to_work_id` | Work-to-work link only |
| `relation_type` | Cites, uses-result-from, uses-method-from, extends, applies, generalises, contrasts, replicates, corrects, or downstream-citation |
| `claim`, `epistemic_status`, `confidence` | What is claimed and whether stated or inferred |
| `bibliographic_fact` | Keeps bare citation status explicit |

`literature_relationship_contexts`

Attaches a relationship to focal-paper sections, `paper_records`, or source anchors. This is how subsection-level literature context appears without turning subsections into graph nodes.

`research_evidence_v2`

Evidence identifies the work or source it came from, exact locator/quote where legally and technically available, URL/provider identifier, retrieval time, and whether the content was read directly or inferred from metadata. One relationship may require evidence from both works.

### Literature API and jobs

Recommended v2 routes:

```text
POST /works/resolve                                      local metadata/dedup where possible
POST /works/{focal_work_id}/research                     explicit paid/web/agent action
GET  /works/{focal_work_id}/literature-maps/latest
GET  /literature-maps/{map_id}
GET  /literature-maps/{map_id}/works
GET  /literature-maps/{map_id}/relationships
GET  /paper-analyses/{analysis_id}/records
GET  /literature-relationships/{relationship_id}/evidence
```

Opening, filtering, laying out, or expanding already saved map data is local. Discovering new external works or evaluating a new relationship is a clearly labelled research action and produces a new complete map revision; it is never triggered by panning or clicking a node.

## Agent output contracts

The managed agent implementation should target provider-neutral schemas.

### Chapter package

At minimum:

```json
{
  "schema_version": 2,
  "complete": true,
  "scope": {"scope_id": "...", "source_sha256": "...", "start": {}, "end": {}},
  "blocks": [
    {"stable_key": "s7-eq-3", "ordinal": 31, "kind": "equation", "source_content": "...", "source_locator": {}}
  ],
  "annotations": [
    {
      "stable_key": "ann-s7-eq3-to-eq4",
      "intent": "derivation",
      "visual_role": "yellow_explanation",
      "placement": "interlinear",
      "anchors": [{"kind": "gap", "after": "s7-eq-3", "before": "s7-eq-4"}],
      "payload": {"rows": [], "correspondences": [], "rules": []},
      "provenance": []
    }
  ],
  "checkable_items": [],
  "problem_links": [],
  "coverage": {"represented_blocks": [], "typed_omissions": []}
}
```

### Literature-map package

At minimum:

```json
{
  "schema_version": 2,
  "complete": true,
  "focal_work": {},
  "works": [],
  "paper_records": [],
  "relationships": [],
  "contexts": [],
  "evidence": [],
  "research_scope": {},
  "cutoff_reason": "..."
}
```

Schema validation should reject internal paper records used as work nodes, relationships without evidence, unresolved anchors, missing provenance, and packages that silently treat citation as a stronger intellectual relation.

## Migration from the current build

### Preserve, do not reinterpret

- Keep current `sections`, `units`, `revisions`, `checks`, `imported_annotations`, and research tables readable during migration.
- Mark their API and UI as v1/legacy once v2 is usable; do not destructively rewrite user study history.
- Add a real schema migration mechanism and schema-version table before adding v2 tables. The current startup-only `CREATE TABLE IF NOT EXISTS` approach is insufficient for data-shape changes.

### Reading editions

Current Markdown cannot be reliably split into source and generated layers by heading names in all cases. Do not auto-claim faithful anchors from it.

- Retain existing revisions as legacy editions.
- Re-prepare the B6La example from its original PDF into the v2 chapter schema as the first acceptance fixture.
- If a legacy unit has an exact verified `### Source text` section, an import assistant may propose blocks, but publication still requires coverage and fidelity validation.
- Map existing dated checks only when a human- or agent-reviewed stable semantic item is demonstrably equivalent. Otherwise preserve the historical check on the legacy revision and leave the v2 item unassessed.
- Map imported historical colour marks to anchored historical annotations only where their original page target can be recovered; otherwise retain them as page-level historical notes.

### Research data

- Preserve the current Keshav graph records as legacy research data, but remove them from the literature-map navigation.
- Convert its bibliography entries to `works` only after bibliographic identity resolution. A listed citation can create a `cites` fact; it must not create an `extends` or `requires` relationship by implication.
- Use an actual mathematics or physics paper as the first literature-map acceptance fixture.
- Do not merge current `research_nodes.source_id` into work identity. Introduce `works` and `source_works` explicitly.

## Code change map

The current monoliths make these changes harder to verify. The redesign should create seams rather than adding more conditional rendering to them.

### Backend

- Add ordered migrations under `backend/migrations/` and a schema-version runner invoked by `Store` startup.
- Add chapter-domain persistence in `backend/chapter_editions.py` (or an equivalent focused store) rather than growing `backend/store.py` indefinitely.
- Add literature-domain persistence in `backend/literature.py`.
- Add provider-neutral package models and validation in `backend/contracts/chapter_v2.py` and `backend/contracts/literature_v2.py`.
- Add v2 routes in focused routers, then include them from `backend/app.py`.
- Change `backend/worker_protocol.py` so preparation targets a confirmed scope and returns a schema-versioned chapter package.
- Keep provider-specific managed-agent code as an adapter around these contracts. It must not write directly to the database.
- Stop including `graph` in `PreparedEditionIn`. Source problem extraction may remain part of chapter preparation; external literature research receives its own command and idempotent publication path.

### Frontend

Split `frontend/src/main.tsx` into domain views before implementing the visual layer:

```text
frontend/src/reader/ChapterReader.tsx
frontend/src/reader/SourceBlock.tsx
frontend/src/reader/AnnotationLayer.tsx
frontend/src/reader/DerivationBridge.tsx
frontend/src/reader/CheckableItem.tsx
frontend/src/reader/SourcePagePanel.tsx
frontend/src/research/LiteratureMap.tsx
frontend/src/research/LiteratureTimeline.tsx
frontend/src/research/WorkDetails.tsx
frontend/src/research/RelationshipEvidence.tsx
frontend/src/api/types.ts
```

- Remove `foldEditionSections()` from the v2 reader.
- Replace text-search highlighting with anchor resolution against structured blocks.
- Replace `selectedUnit` as the reader's primary state with `selectedScope`, `editionRevision`, and `activeBlockKey`.
- Replace the fixed-grid graph SVG with a deterministic work layout and synchronized list/timeline. The exact visualization library can be chosen after a small throwaway prototype; the persistence model must not depend on it.
- Keep clarification, refresh, checks, and graph browsing local/explicit boundaries from the accepted requirements.

### Prepared fixtures

- Replace `study-content/b6la-sturm-liouville-p29.json` only after a v2 chapter fixture covers a complete confirmed scope; retain the current file as legacy evidence until then.
- Do not use `study-content/keshav-reading-map.json` as the v2 graph fixture.
- Add JSON Schema fixtures for a complete chapter package, a literature map, invalid anchors, internal-node rejection, and citation-versus-influence separation.

## Acceptance cases

### Chapter reader

1. Prepare a complete five-to-ten-page chapter containing prose, a multi-line derivation, a figure or table, a source mistake, an example, and an exercise.
2. Verify every source block against rendered PDF pages and confirm original order and notation.
3. Show at least one visual derivation bridge exactly between its two source equations, including a nontrivial external result link.
4. Show a short intuition annotation in flow and a longer optional derivation collapsed at the point of use.
5. Preserve an erroneous source line and display its correction distinctly.
6. Tick one checkable claim and one equation group independently; reload and retain both dates.
7. Submit an anchored clarification, continue reading the prior revision, refresh when complete, and retain position and unaffected checks.
8. Confirm that opening or changing annotation-density controls invokes no agent.
9. Confirm a failed generation cannot appear as a partial chapter.

### Literature map

1. Select a real mathematics or physics focal paper with identifiable predecessor and downstream works.
2. Confirm every canvas node is a work; no section, assumption, result, or method-step appears as a node.
3. Select a focal subsection and see the relevant external works highlighted without creating subsection nodes.
4. Distinguish a bare citation edge from an evidence-backed `uses result from` or `extends` relationship.
5. Inspect evidence and epistemic status for every relationship.
6. Browse, filter, pan, open evidence, and switch to the timeline without any agent call.
7. Start new discovery only through the explicit research command and publish a new complete map revision.
8. Render a useful bounded default map rather than all discovered citations at once.

## Implementation sequence

1. Validate this vocabulary and the chapter reader prototype against several real annotated pages.
2. Introduce schema migrations and provider-neutral v2 contracts.
3. Implement v2 chapter persistence and API with invalid-package tests.
4. Build the source-block renderer, anchor resolver, checkable items, and one derivation bridge primitive.
5. Re-prepare one complete real chapter and run visual fidelity checks.
6. Implement work identity, paper analysis, literature map persistence, and separate research publication.
7. Prototype and implement the focal-paper map plus timeline/list.
8. Migrate legacy views to a labelled read-only path, then remove them only after history and source fidelity are verified.

This sequence creates the correct storage boundary before binding the managed agent to it. Otherwise a new provider would merely generate higher-quality prose into the same wrong reader and graph structures.
