---
name: proof-exposition
description: Make a source proof easier to follow by exposing assumptions, dependencies, and justified inference steps without changing its claim.
---

Read the proof and its stated definitions or prerequisites from registered pages. Preserve the theorem statement and source notation. Present assumptions first, then the proof's dependency structure, and then any added explanatory steps. For each non-obvious inference, name the definition, result, or algebraic fact that licenses it and cite the supporting page.

Separate source text from exposition. Flag missing hypotheses, circular reasoning, or an unsupported inference instead of repairing it silently. Do not claim a stronger result than the source proves. Return source-referenced Markdown in a complete edition package; use `complete: true` only after the whole requested proof and its dependencies have been checked.
