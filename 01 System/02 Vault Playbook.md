---
type: guide
tags:
  - index
  - status/growing
---

# Vault Playbook

This vault is organized as one knowledge tree.

The active top-level folders are:

- `00 Home`
- `01 System`
- `02 Atlas`
- `90 Inbox`
- `99 Archive`

## Folder Roles

- `00 Home` is the landing area.
- `01 System` stores conventions and templates.
- `02 Atlas` is the actual knowledge base.
- `90 Inbox` is for rough capture and temporary intake.
- `99 Archive` stores retired structures and experiments.

For fuller detail, also see:

- [[01 System/05 Atlas Structure|Atlas Structure]]
- [[01 System/06 Numbering and Ordering|Numbering and Ordering]]
- [[01 System/07 Inbox and Archive|Inbox and Archive]]

## Atlas

`02 Atlas` is the only active knowledge tree.

- Its root is [[02 Atlas/01 Atlas Index|Atlas Index]].
- Every meaningful sub-branch should have its own index page.
- Index pages belong inside the branch they describe.
- There is no separate top-level index system.

## Note Types

- `index`: navigation hub for a branch.
- `topic`: prose-first topic page.
- `proof`: derivation or proof page.
- `example`: worked example page.
- `synthesis`: your own collation or write-up.
- `course`: temporary intake note when useful.

## The Core Rule

Place notes by topic, not by source type, course identity, or discipline boundary.

That means:

- mathematics and physics may sit beside each other naturally
- a subtopic index is part of the knowledge base, not metadata about it
- copied quotations stay inside the relevant page or branch

## How To Write Index Pages

Every index page should use this order:

- `Overview`
- `Subtopics`
- `Core pages`
- `Proofs and examples`
- `Sources`
- `Open questions`

## How To Write Topic Pages

Recommended sections:

- `Summary`
- `Statement` or `Definition`
- `Discussion`
- `Examples`
- `Proof` or `Derivation`
- `Connections`
- `Sources`

## Source Placement

Put a source at the highest index that fully matches its scope.

- broad source: place it higher in the branch
- narrow source: place it lower down
- repeat a source lower only if the local branch really benefits from it

If a branch needs a local folder for source files, name it `99 Sources` so it stays at the end without needing renumbering whenever the branch grows.

## Metadata

Keep metadata light.

- Index pages: `type`, `area`, `parent_index`
- Topic-style pages: `type`, `parent_index`, `status`
