# Annotation grammar for source-faithful study editions

Status: evidence-backed design input, not yet an implemented UI contract

This document translates the user's historical PDF marking practice into a browser-native annotation grammar. It is based on visual inspection of rendered pages, not on PDF text extraction alone. The aim is not to reproduce handwriting. It is to reproduce the *work performed by the handwriting*: expose the missing move exactly where it matters, connect it to its source expression, and preserve the reading flow.

## Corpus and method

The raw folder scan found 42 PDFs containing annotations, across 753 annotated physical pages and 7,292 PDF annotation objects. Those totals include duplicate copies, so they are descriptive rather than a statistical sample. Most marks are vector ink: 6,469 ink objects, compared with 326 highlights, 328 rectangles, 121 lines, 33 free-text objects, 9 circles and 6 underlines. A text-only extractor therefore misses most of the evidence.

The dominant ink colours in the raw inventory were red (4,824 objects), green (659), blue (293) and purple (100), with separate pale highlight variants. The inspection sampled more than 40 rendered pages from 13 distinct documents, including analysis, topology, mathematical methods, classical mechanics, electromagnetism, fluid mechanics, statistical physics and quantum mechanics.

These are historical study records. They do not establish current understanding and must not create current study checks.

## What the annotations actually do

The stable pattern is more useful than any single colour:

1. The source remains visible and in order.
2. A short mark identifies the exact word, expression or transition that prompted work.
3. The extra work is placed beside or between the relevant source lines, not collected in an explanation block at the end.
4. Algebra is expanded until the hidden operation is visible.
5. A note often says *why* an operation is valid: the theorem, assumption, convention, definition or limiting argument being used.
6. Arrows, brackets and small diagrams preserve the relationship between the note and the source.
7. Ticks record the learner's judgment. They are not claims an agent is allowed to make on the learner's behalf.

### Observed evidence

Page numbers below are 1-based physical PDF pages.

| Source and page | Observed mark | Work performed | Browser analogue |
|---|---|---|---|
| `methods.pdf`, p.41 | Red derivation fills the lower margin; circled factors and a brace track separation of variables | Reconstructs several omitted algebraic steps and shows which term depends on which variable | Aligned equation bridge with term-to-term highlighting and a short dependency label |
| `methods.pdf`, p.45 | Red integration-by-parts workings surround the equations; green questions challenge signs and a factorial | Verifies a long calculation while isolating possible mistakes | Interlinear operation labels plus a green issue flag; original and proposed correction shown separately |
| `methods.pdf`, p.64 | Red substitutions sit immediately beside the heat-equation solution; blue ticks mark accepted lines; a blue note records an attempted verification | Combines derivation, sanity check and learner confidence without interrupting the source | Compact derivation bridge; manual check control; optional verification note |
| `methods.pdf`, p.71 | Red Fourier-coefficient explanation and physical-energy comments sit beside the relevant formulas; green asks what “small oscillations” means mathematically | Supplies a hidden calculation, physical intuition and an unresolved modelling assumption | Local equation bridge, margin intuition note and assumption flag |
| `B6La.pdf`, p.10 | Red derivative expansion and small notation comments attach directly to individual terms; blue ticks mark accepted transitions | Makes the chain rule and Hessian argument explicit | Token-anchored micro-derivation with operation labels |
| `B6La.pdf`, p.11 | Red commentary reconstructs the sign/domain argument; blue note says an example was checked instead of a rigorous proof | Separates formal reasoning from a sanity check | Inline proof bridge plus clearly labelled sanity check |
| `B6La.pdf`, p.30 | Red first-variation and quotient-rule work is interleaved with the source; green refers to another set of notes and questions the boundary condition | Reveals omitted variational steps and a prerequisite/source discrepancy | Multi-step aligned derivation, prerequisite link and evidence-backed issue note |
| `MA259_12345_1920.pdf`, p.7 | Red geometric diagram and a short proof expand the sketch proof | Converts “you may find it helpful to draw a picture” into the actual picture and missing inequalities | Small local diagram with a concise derivation under the claim |
| `MA259_12345_1920.pdf`, p.22 | Purple highlight marks “proofs are left to the reader”; green asks whether two norm-based definitions are equivalent; red supplies a definition | Identifies an exercise and a prerequisite gap | Purple inline exercise affordance plus a linked definition note |
| `MA259_12345_1920.pdf`, p.53 | Red comments reconstruct rank and inverse-function-theorem reasoning; coloured highlights identify the exact source clauses being used | Shows which earlier theorem discharges each proof step | Clause-to-reason connectors and theorem chips at the transition |
| `Notes-Analysis-III-JLR - Oct.pdf`, p.26 | Red quantifier reasoning explains why the sweeping indicator functions have no pointwise limit | Turns a verbal claim into a pointwise counterargument | Short proof bridge positioned after the claim |
| `Notes-Analysis-III-JLR - Oct.pdf`, p.32 | Red comments name the FTC and expand a limiting equality; green highlights the continuity condition | Names an unstated result and explains why its hypotheses hold | Result tag with a one-line applicability check |
| `Notes-Analysis-III-JLR - Oct.pdf`, p.64 | Red note identifies a prior example-sheet result; green notes the direction in which a limit must be justified | Adds provenance and exposes an unproved interchange | Source link plus green justification-required flag |
| `px263_main.pdf`, p.35 | A hand-drawn surface-current diagram and red/green comments explain the discontinuity | Adds spatial intuition and an alternative reference | Clean vector diagram, margin intuition and source link |
| `px263_main.pdf`, p.38 | Red loop diagram and prose explain the limiting rectangle; blue note confirms the orientation convention | Makes a geometric limiting argument visible | Diagram with animated/stepped width-to-zero explanation and a convention note |
| `px263_main.pdf`, p.44 | Red notes derive boundary conditions around each displayed result | Reconstructs omitted vector-calculus reasoning | Short expandable derivation attached to each boundary condition, not one block after the page |
| `MA222_260_notes_2020-21.pdf`, p.27 | Dense red proof comments are inserted beside the exact topology statements they justify | Reconstructs the proof at clause level | Margin proof rail with numbered connectors into the source |
| `MA222_260_notes_2020-21.pdf`, p.28 | Purple asks to prove that the subspace topology is a topology; red and green notes add details and comments on presentation order | Extracts a reader exercise and identifies expository friction | Purple exercise card in place; optional presentation note kept secondary |
| `ClassicalDynamicsI.pdf`, pp.4-5 | Red chain-rule and rotating-coordinate calculations fill omitted steps; arrows join each expansion to its source equation; blue ticks and “verified” mark accepted steps | Performs line-by-line mathematical debugging | Equation bridge with arrows between matched subexpressions; manual check beside the source unit |
| `ClassicalDynamicsI.pdf`, p.7 | Purple highlight encloses an inline Coriolis question; green questions the meaning of a force statement; red derives the coordinate formula | Separates exercise extraction, conceptual ambiguity and calculation | Purple source problem, green concept flag and local derivation |
| `sp.pdf`, p.35 | Red differential calculation and an everyday partitioning analogy explain extensive quantities | Adds both formal manipulation and intuition | Equation bridge followed by a one-sentence intuition note |
| `sp.pdf`, p.40 | Red momentum-insertion working supplies the missing quantum step; green marks the classical-limit sentence | Exposes an identity and a key approximation | Local identity expansion plus assumption badge |
| `sp.pdf`, p.69 | Red measure/Jacobian derivation sits above a blue-highlighted source explanation and blue ticks | Makes a sum-to-integral conversion explicit | Aligned measure transformation with source clause retained beneath it |
| `fluids1.pdf`, p.8 | Red material-volume argument is written above the page; arrows point to the Jacobian statement | Supplies the geometric meaning of a formal derivative | Small before/after volume diagram with a compact derivation |
| `fluids1.pdf`, p.12 | Red comment explains the triple-product cancellation and questions a streamline conclusion | Separates a straightforward identity from a subtle global inference | One-line identity label plus a green scope/assumption warning |
| `PX265_Handout2.pdf`, pp.14-16 | Purple working completes “try it”; orange/red text interprets the density of states and bound/free electrons | Completes a prompted derivation and adds physical meaning | Purple exercise expansion and adjacent physical-interpretation note |
| `chap8.pdf`, pp.4-5 | Orange highlights collect assumptions; blue highlight/tick marks accepted consequences; small red/blue comments clarify a perturbative expansion | Tracks assumptions separately from understood results | Assumption strip at the first use; manual understood state on the relevant claim |
| `year3/vector_calculus.pdf`, p.43 | Large red diagram, unit-normal calculation and arrows sit beside Green's/divergence theorem statements | Converts a terse theorem translation into geometry | Clean inline SVG diagram with equation labels and connector arrows |
| `quantum_mechanics.pdf`, p.28 | Red derivation expands a commutator; green box and comment mark a conceptual connection; blue tick marks a result | Adds missing operator algebra and flags an interesting connection | Equation bridge, concept note and manual check |

## Semantic colours

The user's stated current convention is the authority:

| Family | Current meaning | Agent behaviour |
|---|---|---|
| Green | Something unclear, a mistake, or a reference/result outside the current document | Flag the obstacle at its exact anchor. If the agent can resolve it, show the resolution as an adjacent explanatory or correction annotation; do not erase the fact that the source caused a problem. |
| Yellow/orange/pink highlight with red text | Added explanation, intermediate work, a mini-proof or interpretation | This is the principal agent-authored annotation family. Use restrained highlighting for the source span and typographic red/rust for the attached work. |
| Blue | The learner understands the material fully and does not need further explanation | Only the learner may create this state through the check control. The agent must never auto-blue a passage. A dated blue state is study data, not generated content. |
| Purple | An exercise for the reader that has not been done at that point | Extract it as a source problem, preserve it inline, and link it to the problem workflow. Do not reveal assistance automatically. |

The historical corpus contains exceptions. For example, older green notes sometimes mean “interesting” or “verify”, blue sometimes contains a sanity-check comment rather than only a tick, and purple workings can complete a source “try it”. Therefore:

- never infer current state from colour alone;
- store semantic intent separately from visual family;
- retain imported marks as `historical_user` with their original colour;
- use content, geometry, date and surrounding marks when importing legacy annotations;
- leave ambiguous legacy intent explicitly unclassified rather than inventing certainty.

## Annotation intents

Agent-authored annotations should use a small semantic vocabulary. Colour is presentation; these intents are data.

| Intent | Question answered | Typical visible form |
|---|---|---|
| `step_bridge` | How did the source get from this line to the next? | Aligned intermediate equations, operation labels and matched-term emphasis |
| `reason` | Why is this operation permitted? | A short result/definition tag with the relevant hypotheses |
| `assumption` | What is being assumed here, explicitly or implicitly? | Margin note or assumption chip at first use |
| `notation` | What does this symbol/index/convention mean here? | Inline micro-gloss or short margin note |
| `intuition` | What geometric or physical picture makes this natural? | Brief prose, limiting case, analogy or small diagram |
| `sanity_check` | Does the result have the right sign, units, limit or special case? | Compact check line, explicitly labelled as a check rather than a proof |
| `prerequisite` | Which outside result is being used? | One-sentence local statement plus link to the canonical Atlas note or evidence source |
| `cross_reference` | Where is this developed elsewhere? | Source/Atlas link with a short statement of relevance |
| `correction` | Is the source wrong, incomplete or misleading? | Original retained, issue flagged, corrected form and justification shown separately |
| `exercise` | Is the reader being asked to do mathematical work? | Purple inline problem with provenance and attempt state |
| `understanding` | Has the learner personally accepted this unit? | Manual dated check only; never generated by the agent |

## Visual primitives

### 1. Source fragment

The smallest source-faithful block: paragraph, displayed equation, list item, theorem clause, proof step, figure or caption. Fragments retain source order and source notation. Reflow for browser legibility is allowed; rewriting or silently correcting the source is not.

### 2. Equation bridge

The main primitive for mathematical reading. It sits *between* the source lines it connects.

- Preserve the source's start and end expressions.
- Add only the missing intermediate lines.
- Label each transition with the operation actually used: “differentiate”, “substitute (2.18)”, “integrate by parts”, “use symmetry”, “divide by \(G\)”, “take \(\epsilon\to0\)”.
- Highlight matched subexpressions consistently across consecutive lines.
- Use arrows or braces for correspondence, not decorative motion.
- Allow one local expansion to open without shifting the reader to a separate explanation page.

For one to three short moves, show the bridge directly. For a longer calculation, keep a one-line transition summary visible and fold the full derivation at that anchor.

### 3. Margin note and connector

A short note aligned with its source fragment. A fine connector or shared hover/focus state reveals the anchor. Use it for a reason, assumption, notation point, intuition or cross-reference that does not need to interrupt the main line.

Do not emulate cramped handwritten margins. On narrow screens, margin notes become indented inline notes immediately after their anchor.

### 4. Subexpression overlay

Use colour, underbraces, boxes and arrows to show what changed inside a formula. The overlay may point into the source equation but must never obscure it. Prose belongs in a margin/interlinear note, not on top of mathematical glyphs.

### 5. Local diagram

A compact SVG or canvas figure anchored beside the relevant argument: coordinate axes, limiting loop, volume deformation, geometric set inclusion or force direction. Labels share the notation of the source edition. The diagram is an explanation, not a replacement for the source figure.

### 6. Issue and correction pair

The source fragment remains verbatim. A green issue flag states the problem precisely. A separate correction panel gives the proposed replacement and derivation/evidence. Corrections carry confidence and review state; low-confidence concerns are questions, not asserted errors.

### 7. Inline exercise

The original exercise text remains in place with a purple edge/highlight. Attempt status and the five-level assistance ladder are available locally, but unopened assistance is absent from the ordinary reader context.

### 8. Manual understanding control

A checkbox sits in the reading rail beside the smallest coherent claim/equation/proof group selected for checking. Ticking it creates a dated learner record and a blue state. The check is visually adjacent but is not part of the generated annotation layer.

## Placement rules

| Placement | Use when | Avoid when |
|---|---|---|
| Interlinear | The annotation is required to follow the immediate transition between equations or proof clauses | It is background knowledge that can be read independently |
| Margin | A short reason, notation note, assumption, intuition or source link attaches to one fragment | The note needs more than roughly two compact sentences or several equations |
| Formula overlay | The relationship is spatial: cancellation, substitution, matched factors, sign, index or direction | The annotation is prose or could hide source glyphs |
| Inline after anchor | The screen is narrow, or a short proof/clarification must remain in the reading sequence | It would duplicate a visible margin note |
| Fold at anchor | A derivation, prerequisite proof, example or alternative explanation is useful but long | The hidden material is essential to understand the next source line; then its minimal bridge must remain visible |
| Chapter side rail | Navigation, annotation filters, unresolved issues and study checks | Mathematical explanation itself; do not exile all comments into a detached sidebar |

The reader must not accumulate all annotations after a page or section. The attachment point is part of the meaning.

## Agent decision rules

For a complete chapter, the preparation agent should:

1. Segment the chapter into ordered source fragments while preserving all source text, equations, figures, captions and notation.
2. Read the learner profile and relevant Atlas notes before deciding what is “obvious”.
3. Identify transition costs: omitted algebra, unnamed results, implicit assumptions, notation changes, scope changes, unexplained physical interpretations, suspicious claims and source exercises.
4. Re-derive every proposed mathematical bridge. Do not generate a plausible-looking intermediate line without checking that it reaches the source result.
5. Prefer the smallest annotation that removes the transition cost. A named operation can be enough; a routine identity should not receive a page of exposition.
6. Put a line-to-line manipulation at the transition, not in a prose block after the subsection.
7. State the reason and applicability conditions when a theorem or identity is used nontrivially.
8. Give intuition locally, ideally as a geometric picture, physical interpretation, limiting case, dimensional check or contrast with a nearby case.
9. Retain source errors verbatim and create an issue/correction pair. Never silently repair the reading edition.
10. Treat a dependency outside the chapter as a prerequisite annotation with a concise local statement and a provenance link. Do not silently prepare the entire external source.
11. Extract every genuine source exercise, including “show that”, “verify”, “try it” and proofs left to the reader. Use purple, and do not generate new exercises in v1.
12. Never mark a passage blue or understood. Only a learner action can do that.
13. Distinguish proof from sanity check, citation from inference, and high-confidence correction from open question.
14. Complete and validate the whole selected chapter before publishing any new edition revision.
15. Keep annotation density readable. Cluster several comments on the same transition into one structured annotation instead of covering the page with repeated callouts.

## Initial chapter-edition schema

This example is deliberately implementation-neutral. Coordinates are normalized to the rendered source page so anchors survive zoom and reflow.

```json
{
  "edition_id": "edition-…",
  "source_id": "source-…",
  "source_revision": {
    "sha256": "…",
    "page_count": 51
  },
  "scope": {
    "kind": "chapter",
    "title": "7 Variational principles",
    "physical_pages": [28, 34],
    "printed_pages": [27, 33]
  },
  "complete": true,
  "fragments": [
    {
      "id": "f-7.3-start",
      "order": 184,
      "kind": "display_equation",
      "source_text": "\\mathcal{L}y=\\lambda wy",
      "source_anchor": {
        "physical_page": 30,
        "rect": [0.30, 0.48, 0.68, 0.54]
      }
    }
  ],
  "annotations": [
    {
      "id": "a-variation-to-eigenproblem",
      "origin": "agent_generated",
      "intent": "step_bridge",
      "visual_family": "explanation",
      "anchors": ["f-variation", "f-7.3-start"],
      "placement": "interlinear",
      "visible_summary": "Apply the Euler-Lagrange operator to each quadratic functional.",
      "math_steps": [
        {
          "latex": "\\delta F=2\\int_\\alpha^\\beta \\delta y[-(\\rho y')'+\\sigma y]\\,dx",
          "operation": "integrate the \\delta y' term by parts"
        },
        {
          "latex": "\\frac{\\delta F}{\\delta y}=2\\mathcal{L}y,\\qquad \\frac{\\delta G}{\\delta y}=2wy",
          "operation": "read off the functional derivatives"
        }
      ],
      "provenance": [
        {
          "kind": "source_fragment",
          "fragment_id": "f-variation"
        }
      ],
      "confidence": 0.98,
      "requires_review": false
    },
    {
      "id": "a-boundary-condition",
      "origin": "agent_generated",
      "intent": "correction",
      "visual_family": "issue",
      "anchors": ["f-boundary-claim"],
      "placement": "margin",
      "visible_summary": "The vanishing boundary term needs the stated homogeneous/fixed-end variation condition.",
      "body": "The printed claim is retained. The issue is whether the boundary condition stated here is sufficient for the endpoint term to vanish.",
      "proposed_correction": "State the endpoint variation condition explicitly before dropping the term.",
      "confidence": 0.93,
      "requires_review": true
    }
  ],
  "learner_state": {
    "checks": [],
    "legacy_marks_imported_as_current": false
  }
}
```

Important separations in the schema:

- `intent` is not a colour;
- `origin` distinguishes source, historical user, agent and current user content;
- source anchors and provenance survive independently of layout;
- chapter completeness is an edition-level invariant;
- learner checks live outside generated annotations;
- an issue can retain the source and propose a correction without rewriting either.

## Acceptance examples for a reader prototype

A prototype is successful only if all of these can be read without leaving the source flow:

1. A two-line formula jump expands into three checked intermediate manipulations between the lines.
2. Hovering or focusing a changed term shows where it came from in the previous line.
3. A theorem used without being named shows a short applicability note and an Atlas/source link.
4. A physical assumption is visible at first use and does not become a detached chapter summary.
5. A suspected sign error preserves the printed expression and displays the correction separately.
6. An inline “show that” remains in place as a purple source problem.
7. A learner check, and only a learner check, turns the unit blue and records its date.
8. On mobile, margin annotations fall inline at the same anchors without losing order.
9. A long optional derivation can collapse, but the operation connecting the source lines remains visible.
10. Preparing a 5-10 page chapter publishes one complete revision; it does not expose page-by-page partial output as a finished edition.

## Limits and learning loop

This grammar captures robust patterns, not the meaning of every historical mark. The corpus spans different tools and conventions; some colour meanings changed. The agent should therefore emit structured annotations that can be corrected, hidden, expanded or reclassified. Accepted/rejected annotations can later tune density and depth, but they must not be treated as evidence that the learner currently understands the underlying mathematics.

