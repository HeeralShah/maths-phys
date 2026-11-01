---
name: expand-derivation
description: Expand a source derivation into readable intermediate steps while preserving its assumptions, notation, and page-level provenance.
---

Work only from the supplied registered source pages and selected unit. Keep the author's symbols and conventions. Add an intermediate step only when it follows from the preceding line and stated assumptions; name the identity, substitution, or algebraic operation that justifies it. Keep the source's original derivation visible and distinguish any explanatory bridge from source wording.

Attach `source_refs` to the pages supporting the derivation and each consequential assumption. Do not silently repair a source error: identify the exact line and mark a proposed correction as an explanation with its own evidence. Return complete unit Markdown in the prepared-edition package shape, including `complete: true`; leave unsupported steps out and report an unresolved gap explicitly.
