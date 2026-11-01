"""Import a prepared JSON study edition through the local FastAPI contract.

The source PDF is registered by reference. Preparation text is imported only
when this explicit command is run. Re-running the same package detects matching
saved unit content and does not append duplicate revisions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = Path(r"C:\Users\heera\Dropbox\Academic Resources\B6La.pdf")


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


def prepared_units(package: dict) -> list[dict]:
    key = package["content_key"]
    units = []
    refresher = package["prerequisite_refresher"]
    units.append({
        "section_title": "Prerequisite refresher",
        "unit_title": refresher["title"],
        "content": refresher["content"],
        "metadata": {"content_key": key, "unit_kind": "prerequisite_refresher",
                     "scope": refresher.get("scope", "")},
        "source_refs": [{"source_file": package["source"]["metadata"]["source_file"],
                         "pdf_page": package["source"]["metadata"]["pdf_page"],
                         "printed_page": package["source"]["metadata"]["printed_page"],
                         "locator": "Prerequisites for the page's first-variation derivation"}],
    })
    for section in package["sections"]:
        for unit in section["units"]:
            units.append({"section_title": section["title"], "unit_title": unit["title"],
                          "content": unit["content"], "metadata": unit["metadata"],
                          "annotations": unit.get("annotations", []),
                          "source_refs": [{"source_file": package["source"]["metadata"]["source_file"],
                                           "pdf_page": package["source"]["metadata"]["pdf_page"],
                                           "printed_page": package["source"]["metadata"]["printed_page"],
                                           "locator": unit["metadata"]["source_locator"]}]})
    return units


def already_imported(base_url: str, source: dict, wanted: list[dict]) -> bool:
    saved_source = request(base_url, "GET", f"/sources/{source['id']}")
    existing = {(section["title"], unit["title"]): unit
                for section in saved_source.get("sections", []) for unit in section.get("units", [])}
    if len(existing) != len(wanted):
        return False
    for spec in wanted:
        unit = existing.get((spec["section_title"], spec["unit_title"]))
        if not unit:
            return False
        edition = request(base_url, "GET", f"/units/{unit['id']}/edition")
        if not edition or edition.get("content") != spec["content"]:
            return False
        saved_annotations = request(base_url, "GET", f"/revisions/{edition['id']}/annotations")
        canonical = lambda items: sorted((a.get("mark"), a.get("detail"),
                                          a.get("source_locator"), a.get("original_date"))
                                         for a in items)
        if canonical(saved_annotations) != canonical(spec.get("annotations", [])):
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=ROOT / "study-content" / "b6la-sturm-liouville-p29.json")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    package = json.loads(args.package.read_text(encoding="utf-8-sig"))
    source_spec = package["source"]
    metadata = dict(source_spec["metadata"])
    metadata["content_key"] = package["content_key"]

    sources = request(args.api, "GET", "/sources")
    source = next((item for item in sources if item.get("metadata", {}).get("content_key") == package["content_key"]), None)
    created = source is None
    if source is None:
        source = request(args.api, "POST", "/sources/register-file", {
            "path": str(args.pdf.resolve()), "title": source_spec["title"], "metadata": metadata})

    units = prepared_units(package)
    if already_imported(args.api, source, units):
        result = {"source_id": source["id"], "created_source": created,
                  "edition_imported": False, "units": len(units)}
    else:
        imported = request(args.api, "POST", f"/sources/{source['id']}/editions/import", {
            "complete": bool(package.get("complete")),
            "edition": {"title": source_spec["title"], "units": units}})
        result = {"source_id": source["id"], "created_source": created,
                  "edition_imported": True, "import_result": imported}
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
