---
status: accepted
---

# Keep canonical topic notes in Markdown and structured study state in SQLite

Keep the Obsidian vault's Markdown notes as the human-readable Atlas canon, and store operational study state, results, and graph data in SQLite. This preserves an existing user-owned vault and readable, versionable topic notes while giving the application structured local persistence for checks and relationships. The stores have distinct ownership; SQLite may index note content but does not become the competing canonical copy. Backups must include both stores and referenced assets.
