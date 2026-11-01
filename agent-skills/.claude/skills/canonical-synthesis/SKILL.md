---
name: canonical-synthesis
description: Prepare an incremental Atlas Markdown plan from the checked revisions explicitly included in a section signoff.
---

Use only the checked revision IDs and contents supplied by the signoff job. Treat their source references as provenance. Search the canonical vault for existing topic notes and inspect each proposed target under `02 Atlas` before constructing the plan. Use one normalized notation per note, retain links to every contributing source revision, and preserve existing manually expressed intent.

Return a plan object with `signoff_id`, the exact `source_revision_ids`, `expected_hashes` for every target (null for a new note), and `files` containing relative `02 Atlas/...md` paths plus complete Markdown content. Include an idempotency key supplied by the caller. Do not claim a target is safe when its expected hash is unknown. Never write files or include unchecked material. If a signed revision no longer matches the current material, return a reconfirmation requirement instead of a plan.
