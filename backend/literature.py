"""Work-centric, evidence-backed literature map persistence."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

from .contracts.literature_v2 import LiteratureMapPackage, WorkSpec
from .store import Store, now, uid


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normal(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _identity_key(work: WorkSpec) -> str:
    if work.doi:
        doi = work.doi.casefold().strip()
        doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi)
        return "doi:" + doi
    if work.arxiv_id:
        return "arxiv:" + work.arxiv_id.casefold().strip().removeprefix("arxiv:")
    if work.isbn:
        return "isbn:" + re.sub(r"[^0-9xX]", "", work.isbn).casefold()
    fallback = {"title": _normal(work.title), "year": work.year,
                "first_author": _normal(work.authors[0]) if work.authors else ""}
    return "fallback:" + hashlib.sha256(_json(fallback).encode("utf-8")).hexdigest()


class LiteratureRepository:
    def __init__(self, store: Store):
        self.store = store

    def publish(self, package: LiteratureMapPackage) -> dict:
        payload = package.model_dump(mode="json")
        package_hash = hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()
        with self.store._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT * FROM literature_maps WHERE publication_key=?",
                               (package.publication_key,)).fetchone()
            if prior:
                if prior["package_hash"] != package_hash:
                    raise ValueError("publication_key is already bound to a different complete literature map")
                return self.get_map(prior["id"])

            if package.edition_id:
                edition = db.execute("""SELECT e.id,s.source_id FROM chapter_editions e
                    JOIN source_scopes s ON s.id=e.scope_id WHERE e.id=? AND e.status='complete'""",
                                     (package.edition_id,)).fetchone()
                if not edition:
                    raise ValueError("edition_id must identify a complete chapter edition")
            else:
                edition = None

            work_ids: dict[str, str] = {}
            for work in package.works:
                identity = _identity_key(work)
                existing = db.execute("SELECT id FROM works WHERE identity_key=?", (identity,)).fetchone()
                if existing:
                    work_ids[work.local_key] = existing["id"]
                    continue
                work_id = uid()
                db.execute("INSERT INTO works VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    work_id, identity, work.work_type, work.title, _json(work.authors), work.year,
                    work.venue, work.doi, work.arxiv_id, work.isbn, _json(work.external_ids),
                    work.url, work.abstract, _json(work.metadata_provenance), now()))
                work_ids[work.local_key] = work_id

            if len(set(work_ids.values())) != len(work_ids):
                raise ValueError("works must resolve to distinct bibliographic identities")

            focal_id = work_ids[package.focal_work_key]
            if edition:
                db.execute("INSERT OR IGNORE INTO source_works(source_id,work_id) VALUES(?,?)",
                           (edition["source_id"], focal_id))

            analysis_revision = db.execute(
                "SELECT COALESCE(MAX(revision),0)+1 FROM paper_analyses WHERE focal_work_id=?", (focal_id,)).fetchone()[0]
            analysis_id, timestamp = uid(), now()
            db.execute("INSERT INTO paper_analyses VALUES(?,?,?,?,?,?,?,?,?)", (
                analysis_id, focal_id, package.edition_id, analysis_revision, "complete", package_hash,
                package.generator, package.model, timestamp))

            map_revision = db.execute(
                "SELECT COALESCE(MAX(revision),0)+1 FROM literature_maps WHERE focal_work_id=?", (focal_id,)).fetchone()[0]
            map_id = uid()
            db.execute("INSERT INTO literature_maps VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
                map_id, focal_id, analysis_id, map_revision, "complete", package_hash,
                package.publication_key, _json(package.research_scope), package.cutoff_reason,
                _json(package.provider_provenance), timestamp))

            for member in package.map_works:
                db.execute("INSERT INTO literature_map_works VALUES(?,?,?,?,?)", (
                    map_id, work_ids[member.work_key], _json(member.roles), member.importance_reason,
                    member.lane))

            evidence_ids: dict[str, str] = {}
            for evidence in package.evidence:
                evidence_id = uid()
                if evidence.source_id and not db.execute(
                        "SELECT 1 FROM sources WHERE id=?", (evidence.source_id,)).fetchone():
                    raise ValueError("evidence source_id does not resolve")
                db.execute("INSERT INTO research_evidence_v2 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
                    evidence_id, map_id, evidence.local_key,
                    work_ids.get(evidence.work_key or ""), evidence.source_id, evidence.evidence_kind,
                    evidence.locator, evidence.quote, evidence.url, evidence.provider_identifier,
                    evidence.retrieved_at, _json(evidence.metadata)))
                evidence_ids[evidence.local_key] = evidence_id

            record_ids: dict[str, str] = {}
            for record in package.paper_records:
                record_id = uid()
                db.execute("INSERT INTO paper_records VALUES(?,?,?,?,?,?,?,?,?)", (
                    record_id, analysis_id, record.stable_key, record.record_type, record.label,
                    record.claim, record.section_label, _json(record.locator), _json(record.metadata)))
                record_ids[record.stable_key] = record_id
                for evidence_key in record.evidence_keys:
                    db.execute("INSERT INTO paper_record_evidence VALUES(?,?)",
                               (record_id, evidence_ids[evidence_key]))

            for relation in package.relationships:
                relationship_id = uid()
                db.execute("INSERT INTO literature_relationships VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
                    relationship_id, map_id, relation.stable_key, work_ids[relation.from_work_key],
                    work_ids[relation.to_work_key], relation.relationship_class, relation.relation_type,
                    relation.claim, relation.epistemic_status, relation.citation_status,
                    relation.confidence, _json(relation.metadata)))
                for evidence_key in relation.evidence_keys:
                    db.execute("INSERT INTO literature_relationship_evidence VALUES(?,?)",
                               (relationship_id, evidence_ids[evidence_key]))
                for ordinal, context in enumerate(relation.contexts):
                    db.execute("INSERT INTO literature_relationship_contexts VALUES(?,?,?,?,?)", (
                        relationship_id, ordinal, context.section_label,
                        record_ids.get(context.paper_record_key or ""), _json(context.source_anchor)))

            self.store._event(db, "literature_map.published", "literature_map", map_id,
                              {"focal_work_id": focal_id, "revision": map_revision, "complete": True})
        return self.get_map(map_id)

    def latest(self, focal_work_id: str) -> dict | None:
        with self.store._connection() as db:
            if not db.execute("SELECT 1 FROM works WHERE id=?", (focal_work_id,)).fetchone():
                raise KeyError("work not found")
            row = db.execute("SELECT id FROM literature_maps WHERE focal_work_id=? AND status='complete' "
                             "ORDER BY revision DESC LIMIT 1", (focal_work_id,)).fetchone()
        return self.get_map(row["id"]) if row else None

    def list_works(self) -> list[dict]:
        with self.store._connection() as db:
            return [self._work(row) for row in db.execute("SELECT * FROM works ORDER BY year,title,id")]

    @staticmethod
    def _work(row) -> dict:
        result = dict(row)
        result["authors"] = json.loads(result["authors"])
        result["external_ids"] = json.loads(result["external_ids"])
        result["metadata_provenance"] = json.loads(result["metadata_provenance"])
        return result

    def get_map(self, map_id: str) -> dict | None:
        with self.store._connection() as db:
            row = db.execute("SELECT * FROM literature_maps WHERE id=?", (map_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["research_scope"] = json.loads(result["research_scope"])
            result["provider_provenance"] = json.loads(result["provider_provenance"])
            result["focal_work"] = self._work(db.execute(
                "SELECT * FROM works WHERE id=?", (row["focal_work_id"],)).fetchone())

            members = []
            for member in db.execute("""SELECT w.*,m.roles,m.importance_reason,m.lane
                    FROM literature_map_works m JOIN works w ON w.id=m.work_id
                    WHERE m.map_id=? ORDER BY CASE m.lane
                      WHEN 'foundation' THEN 1 WHEN 'predecessor' THEN 2 WHEN 'focal' THEN 3
                      WHEN 'contemporary' THEN 4 WHEN 'downstream' THEN 5 ELSE 6 END,w.year,w.title""", (map_id,)):
                item = self._work(member)
                item["roles"] = json.loads(item["roles"])
                members.append(item)
            result["works"] = members

            evidence = {}
            for raw in db.execute("SELECT * FROM research_evidence_v2 WHERE map_id=? ORDER BY stable_key", (map_id,)):
                item = dict(raw)
                item["metadata"] = json.loads(item["metadata"])
                evidence[item["id"]] = item
            result["evidence"] = list(evidence.values())

            analysis_id = row["analysis_id"]
            records = []
            record_keys = {}
            for raw in db.execute("SELECT * FROM paper_records WHERE analysis_id=? ORDER BY stable_key", (analysis_id,)):
                item = dict(raw)
                item["locator"] = json.loads(item["locator"])
                item["metadata"] = json.loads(item["metadata"])
                item["evidence_ids"] = [link[0] for link in db.execute(
                    "SELECT evidence_id FROM paper_record_evidence WHERE record_id=? ORDER BY evidence_id", (item["id"],))]
                records.append(item)
                record_keys[item["id"]] = item["stable_key"]
            result["paper_records"] = records

            relationships = []
            for raw in db.execute("SELECT * FROM literature_relationships WHERE map_id=? ORDER BY stable_key", (map_id,)):
                item = dict(raw)
                item["metadata"] = json.loads(item["metadata"])
                contexts = []
                for context_row in db.execute(
                        "SELECT * FROM literature_relationship_contexts WHERE relationship_id=? ORDER BY ordinal",
                        (item["id"],)):
                    context = dict(context_row)
                    context["paper_record_key"] = record_keys.get(context.pop("paper_record_id"))
                    context["source_anchor"] = json.loads(context["source_anchor"])
                    contexts.append(context)
                item["contexts"] = contexts
                item["evidence_ids"] = [link[0] for link in db.execute(
                    "SELECT evidence_id FROM literature_relationship_evidence WHERE relationship_id=? ORDER BY evidence_id",
                    (item["id"],))]
                relationships.append(item)
            result["relationships"] = relationships
            return result

