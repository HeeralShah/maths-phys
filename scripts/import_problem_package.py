"""Register a source PDF and import its verbatim prompt package idempotently."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = Path(r"C:\Users\heera\Dropbox\Academic Resources\ClassicalDynamicsI.pdf")
REQUIRED_LEVELS = {"orientation", "small_hint", "strong_hint", "partial_solution", "full_solution"}


def request(base_url: str, method: str, path: str, body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = Request(base_url.rstrip("/") + path, data=data, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=30) as response:
            payload = response.read()
            return json.loads(payload.decode("utf-8")) if payload else None
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API {method} {path} returned {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach local API at {base_url}: {exc.reason}") from exc


def validate(package: dict) -> None:
    if not package.get("complete"):
        raise ValueError("problem package must be marked complete")
    if not package.get("problems"):
        raise ValueError("problem package has no source prompts")
    for problem in package["problems"]:
        if not str(problem.get("prompt", "")).strip():
            raise ValueError("every source prompt must be non-empty")
        if not str(problem.get("provenance", {}).get("quote", "")).strip():
            raise ValueError("every prompt needs its exact source quote")
        assistance = problem.get("assistance", {})
        if set(assistance) != REQUIRED_LEVELS or any(not str(assistance[k]).strip() for k in REQUIRED_LEVELS):
            raise ValueError("every problem must contain all five non-empty assistance levels")


def import_package(package: dict, pdf: Path, base_url: str) -> dict:
    validate(package)
    source_spec = package["source"]
    metadata = dict(source_spec["metadata"])
    sources = request(base_url, "GET", "/sources")
    source = next((item for item in sources
                   if item.get("metadata", {}).get("content_key") == package["content_key"]), None)
    created_source = source is None
    if source is None:
        source = request(base_url, "POST", "/sources/register-file", {
            "path": str(pdf.resolve()), "title": source_spec["title"], "metadata": metadata})
    existing = request(base_url, "GET", "/problems?" + urlencode({"source_id": source["id"]}))
    existing_prompts = {item["prompt"]: item for item in existing}
    created = []
    for spec in package["problems"]:
        if spec["prompt"] in existing_prompts:
            continue
        body = {"source_id": source["id"], **spec}
        created.append(request(base_url, "POST", "/problems", body))
    return {"source_id": source["id"], "created_source": created_source,
            "problem_ids": [item["id"] for item in created],
            "created_prompts": [item["prompt"] for item in created],
            "existing_count": len(existing_prompts),
            "package_count": len(package["problems"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path,
                        default=ROOT / "data" / "local" / "prepared" / "classical-dynamics-coriolis-problems.json")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    package = json.loads(args.package.read_text(encoding="utf-8-sig"))
    result = import_package(package, args.pdf, args.api)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
