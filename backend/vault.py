"""Contained, read-only access to canonical Markdown notes in the Obsidian vault."""
from pathlib import Path


def _vault_file(root: str | Path, relative_path: str) -> Path:
    base = Path(root).resolve(strict=True)
    target = (base / relative_path).resolve(strict=True)
    target.relative_to(base)
    if target.suffix.casefold() != ".md" or ".obsidian" in target.parts or not target.is_file():
        raise FileNotFoundError("canonical Markdown note not found")
    return target


def read_note(root: str | Path, relative_path: str) -> dict:
    base = Path(root).resolve(strict=True)
    target = _vault_file(base, relative_path)
    return {"path": target.relative_to(base).as_posix(), "content": target.read_text(encoding="utf-8")}


def search_notes(root: str | Path, query: str, limit: int = 100) -> list[dict]:
    base = Path(root).resolve(strict=True)
    needle = query.strip().casefold()
    if not needle:
        raise ValueError("query is required")
    hits = []
    for path in base.rglob("*.md"):
        try:
            content = read_note(base, path.relative_to(base).as_posix())["content"]
        except (OSError, ValueError):
            continue
        index = content.casefold().find(needle)
        if index < 0:
            continue
        start, end = max(0, index - 120), min(len(content), index + len(needle) + 180)
        title = next((line.lstrip("# ").strip() for line in content.splitlines() if line.startswith("#")), path.stem)
        hits.append({"path": path.relative_to(base).as_posix(), "title": title,
                     "snippet": content[start:end].replace("\n", " ")})
        if len(hits) >= limit:
            break
    return hits
