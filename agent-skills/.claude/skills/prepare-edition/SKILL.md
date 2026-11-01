---
name: prepare-edition
description: Prepare or revise a complete source-faithful study edition from registered PDF pages, preserving source order, notation, page provenance, and optional source-only problems.
---

Prepare the complete requested reading package before returning it. Use registered source-page tools as the only authority for the original material; the source itself owns wording, notation, order, and diagrams. Keep source notation in reading text and retain page locators in every unit's `source_refs`.

Return one JSON object with `complete: true`, `edition: {title, units}`, and optional `problems`. Each unit has `section_title`, `unit_title`, `content`, `source_refs`, and optional `metadata` and `annotations`. Preserve all requested page coverage and order. Include an annotation only when the source contains a visible historical mark; record its mark and locator, set `historical: true`, and leave unknown dates null.

Before returning, confirm that all requested pages have been read and represented, every unit has non-empty Markdown content and source references, and optional problems have complete five-level assistance. If source access or coverage is incomplete, report failure instead of returning a publishable package.
