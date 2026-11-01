"""Load Keshav's locally held three-pass paper-reading map into the research graph.

The map is evidence-first and idempotent. It stores no PDF copy and makes no model
or web-research calls. Run from the repository root after starting the local API.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP = ROOT / "study-content" / "keshav-reading-map.json"
DEFAULT_PDF = Path(r"C:\Users\heera\Dropbox\Academic Resources\HowtoReadPaper.pdf")


def api(method: str, url: str, payload: dict | None = None) -> dict | list:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, method=method,
                      headers={"Content-Type": "application/json"} if body is not None else {})
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"{method} {url} returned {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach local study API at {url}: {exc.reason}") from exc


def upsert_source(base: str, spec: dict, pdf_path: Path, dry_run: bool) -> str:
    sources = api("GET", f"{base}/sources")
    found = next((s for s in sources if s.get("metadata", {}).get("content_key") == spec["content_key"]), None)
    if found:
        return found["id"]
    if dry_run:
        return "DRY-RUN-SOURCE"
    created = api("POST", f"{base}/sources/register-file", {
        "title": spec["source"]["title"],
        "path": str(pdf_path),
        "metadata": spec["source"]["metadata"] | {"content_key": spec["content_key"]},
    })
    return created["id"]


def load_map(base: str, spec: dict, pdf_path: Path, dry_run: bool = False) -> tuple[int, int, str]:
    if not dry_run and not pdf_path.is_file():
        raise FileNotFoundError(f"Source PDF is not available: {pdf_path}")
    source_id = upsert_source(base, spec, pdf_path, dry_run)
    if dry_run:
        return len(spec["nodes"]), len(spec["edges"]), source_id

    graph = api("GET", f"{base}/research/graph?source_id={source_id}")
    existing_nodes = {n.get("metadata", {}).get("content_key"): n for n in graph["nodes"]
                      if n.get("metadata", {}).get("content_key")}
    existing_edges = {e.get("metadata", {}).get("content_key"): e for e in graph["edges"]
                      if e.get("metadata", {}).get("content_key")}
    node_ids: dict[str, str] = {}
    node_count = 0
    for node in spec["nodes"]:
        key = f"{spec['content_key']}:{node['key']}"
        body = {
            "source_id": source_id,
            "node_type": node["node_type"],
            "label": node["label"],
            "claim": node["claim"],
            "metadata": node.get("metadata", {}) | {"content_key": key, "status": node.get("status", "source-backed")},
            "evidence": [{"locator": ev["locator"], "quote": ev["quote"],
                          "source_ref": ev.get("source_ref"), "metadata": ev.get("metadata", {})}
                         for ev in node["evidence"]],
        }
        found = existing_nodes.get(key)
        if found:
            saved = api("PUT", f"{base}/research/nodes/{found['id']}", body)
        else:
            saved = api("POST", f"{base}/research/nodes", body)
            node_count += 1
        node_ids[node["key"]] = saved["id"]

    edge_count = 0
    for edge in spec["edges"]:
        key = f"{spec['content_key']}:{edge['key']}"
        body = {
            "from_id": node_ids[edge["from"]], "to_id": node_ids[edge["to"]],
            "relation": edge["relation"], "claim": edge["claim"],
            "metadata": edge.get("metadata", {}) | {"content_key": key},
            "evidence": [{"source_id": source_id, "locator": ev["locator"], "quote": ev["quote"],
                          "source_ref": ev.get("source_ref"), "metadata": ev.get("metadata", {})}
                         for ev in edge["evidence"]],
        }
        found = existing_edges.get(key)
        if found:
            api("PUT", f"{base}/research/edges/{found['id']}", body)
        else:
            api("POST", f"{base}/research/edges", body)
            edge_count += 1
    return node_count, edge_count, source_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=os.environ.get("MATHSPHYS_API", "http://127.0.0.1:8000"))
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--dry-run", action="store_true", help="Validate map counts and service availability without writes")
    args = parser.parse_args()
    spec = json.loads(args.map.read_text(encoding="utf-8"))
    if spec.get("schema_version") != 1 or not spec.get("nodes") or not spec.get("edges"):
        raise SystemExit("Map must have schema_version 1 and non-empty nodes and edges")
    result = load_map(args.api.rstrip("/"), spec, args.pdf, args.dry_run)
    print(f"source_id={result[2]} new_nodes={result[0]} new_edges={result[1]} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
