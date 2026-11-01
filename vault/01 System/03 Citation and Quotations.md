---
type: guide
tags:
  - index
  - status/growing
---

# Citation and Quotations

Sources should support the topic tree without becoming a parallel navigation system.

## Source Placement Rule

Attach each source to the highest index whose scope it genuinely covers.

- Broad source: place it high in the branch.
- Narrow source: place it lower down.
- Repeat a source lower in the tree only if the local branch genuinely benefits from seeing it again.

## Source Entry Format

Use compact source entries inside the `Sources` section of an index page.

```md
- Tong, David. *Quantum Field Theory*. University of Cambridge lecture notes, 2006-2007.
  Relevant here: canonical quantization, path integrals, renormalization.
  Local file: [[02 Atlas/09 Quantum Field Theory/02 Canonical Quantization/99 Sources/01 qft_david_tong.pdf|qft_david_tong.pdf]]
  Key locations: Ch. 2, Ch. 6, pp. 95-120.
```

## Topic-Page Citations

Topic, proof, example, and synthesis pages should end with a short `Sources` section listing only the references actually used on that page.

If the full source entry already appears on an ancestor index, the page can cite that source directly without recreating a separate source page.

## Verbatim Material

Short copied passages should live inline in the relevant page as quote callouts.

```md
> [!quote] Tong, *Quantum Field Theory*, p. 21
> Exact copied passage here.
```

Always include:

- source name
- locator
- local file link when helpful

## Personal Notes and Collations

Your own university notes, your own synthesis, and pages inspired by excellent published expositions all belong in the same topic tree.

The difference should show up in the prose and the citations, not in the vault structure.

For the placement of branch-local source folders, see [[01 System/06 Numbering and Ordering|Numbering and Ordering]].
