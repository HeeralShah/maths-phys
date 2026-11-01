---
type: guide
tags:
  - index
  - source
  - status/growing
---

# Source Workflow

This note is the practical workflow for adding material without losing attribution.

## Minimal Workflow

1. Create a `source` note.
2. Add or confirm the bibliographic details.
3. Link the source note from any concept, proof, example, or synthesis note that uses it.

## When You Want To Quote

1. Create an `excerpt` note.
2. Put the full quotation in a callout.
3. Add the exact locator.
4. Give the quote a block ID.
5. Embed that block into the notes that need it.

Example:

```md
> [!quote] David Tong, *Quantum Field Theory*, p. 23
> Insert the exact quotation here.
^tong-qft-p23
```

Then reuse it with:

```md
![[David Tong - Quantum Field Theory - p23 - Example excerpt#^tong-qft-p23]]
```

## When You Only Need A Page Reference

If the source matters but you do not need the full quotation:

- cite the source note in `source_notes`
- mention the page or section in the body
- paraphrase in your own words

## When You Build Your Own Write-Up

Use a `synthesis` note when:

- one source is incomplete
- multiple expositions complement each other
- you want one coherent write-up after reading several references

At the end of the note, include a short source ledger such as:

```md
## Sources

- Main derivation idea from [[Source A]], Chapter 3.
- Notation chosen to match [[Source B]], Section 2.
- Final example adapted from [[Source C]], p. 118.
```

## Hard Copy Sources

When you only own a physical book:

- still create the source note
- set `holding: hard-copy`
- record a shelf or location if useful
- make excerpt notes by manual transcription when needed

## Suggested Properties For Source Notes

- `source_kind`
- `authors`
- `year`
- `title`
- `edition`
- `publisher`
- `url`
- `local_file`
- `holding`
- `topics`
- `status`

## Suggested Properties For Excerpt Notes

- `source_note`
- `locator`
- `quote_kind`
- `topics`
