"""Persistence for complete, source-faithful chapter editions."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .contracts.chapter_v2 import AnchorSpec, ChapterPackage
from .store import Store, now, uid


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ChapterRepository:
    def __init__(self, store: Store):
        self.store = store

    def create_scope(self, source_id: str, scope_kind: str, title: str, ordinal: int,
                     start_locator: dict, end_locator: dict, detection_method: str,
                     parent_scope_id: str | None = None) -> dict:
        if scope_kind not in ("document", "paper", "chapter", "custom_range"):
            raise ValueError("invalid scope_kind")
        if not title.strip() or not detection_method.strip() or ordinal < 0:
            raise ValueError("scope title, non-negative ordinal, and detection_method are required")
        if not start_locator or not end_locator:
            raise ValueError("scope start and end locators are required")
        start_page, end_page = start_locator.get("physical_page"), end_locator.get("physical_page")
        if start_page is not None and end_page is not None:
            if not isinstance(start_page, int) or not isinstance(end_page, int) or start_page < 1 or end_page < start_page:
                raise ValueError("scope physical-page range must be positive and forward")
        scope_id, timestamp = uid(), now()
        with self.store._connection() as db:
            if not db.execute("SELECT 1 FROM sources WHERE id=?", (source_id,)).fetchone():
                raise KeyError("source not found")
            if parent_scope_id:
                parent = db.execute("SELECT source_id FROM source_scopes WHERE id=?", (parent_scope_id,)).fetchone()
                if not parent or parent["source_id"] != source_id:
                    raise ValueError("parent scope must belong to the same source")
            db.execute("INSERT INTO source_scopes VALUES(?,?,?,?,?,?,?,?,?,?)", (
                scope_id, source_id, parent_scope_id, scope_kind, title.strip(), ordinal,
                _json(start_locator), _json(end_locator), detection_method.strip(), timestamp))
            self.store._event(db, "source_scope.created", "source_scope", scope_id,
                              {"source_id": source_id, "scope_kind": scope_kind})
        return self.get_scope(scope_id)

    def get_scope(self, scope_id: str) -> dict | None:
        with self.store._connection() as db:
            row = db.execute("SELECT * FROM source_scopes WHERE id=?", (scope_id,)).fetchone()
            return self._scope(row) if row else None

    def list_scopes(self, source_id: str) -> list[dict]:
        with self.store._connection() as db:
            if not db.execute("SELECT 1 FROM sources WHERE id=?", (source_id,)).fetchone():
                raise KeyError("source not found")
            return [self._scope(row) for row in db.execute(
                "SELECT * FROM source_scopes WHERE source_id=? ORDER BY ordinal,id", (source_id,))]

    @staticmethod
    def _scope(row) -> dict:
        result = dict(row)
        result["start_locator"] = json.loads(result["start_locator"])
        result["end_locator"] = json.loads(result["end_locator"])
        return result

    def publish(self, scope_id: str, package: ChapterPackage) -> dict:
        payload = package.model_dump(mode="json")
        package_hash = hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()
        with self.store._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            scope = db.execute("SELECT * FROM source_scopes WHERE id=?", (scope_id,)).fetchone()
            if not scope:
                raise KeyError("source scope not found")
            source_row = db.execute("SELECT metadata FROM sources WHERE id=?", (scope["source_id"],)).fetchone()
            source_metadata = json.loads(source_row["metadata"])
            registered_hash = (source_metadata.get("local_file") or {}).get("sha256")
            if registered_hash and registered_hash != package.source_sha256:
                raise ValueError("chapter package source_sha256 does not match the registered source file")
            prior = db.execute("SELECT * FROM chapter_editions WHERE publication_key=?",
                               (package.publication_key,)).fetchone()
            if prior:
                if prior["scope_id"] != scope_id or prior["package_hash"] != package_hash:
                    raise ValueError("publication_key is already bound to a different complete chapter package")
                return self.get_edition(prior["id"])

            revision = db.execute(
                "SELECT COALESCE(MAX(revision),0)+1 FROM chapter_editions WHERE scope_id=?", (scope_id,)).fetchone()[0]
            edition_id, timestamp = uid(), now()
            db.execute("INSERT INTO chapter_editions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
                edition_id, scope_id, revision, package.source_sha256, "complete", package_hash,
                package.publication_key, package.generator, package.model, package.prompt_version,
                _json(package.skill_versions), timestamp))

            block_ids = {block.stable_key: uid() for block in package.blocks}
            for block in sorted(package.blocks, key=lambda item: item.ordinal):
                content_hash = hashlib.sha256(block.source_content.encode("utf-8")).hexdigest()
                db.execute("INSERT INTO edition_blocks VALUES(?,?,?,?,?,?,?,?,?,?)", (
                    block_ids[block.stable_key], edition_id, block.stable_key, None, block.ordinal,
                    block.kind, block.source_content, _json(block.source_locator), content_hash,
                    _json(block.metadata)))
            for block in package.blocks:
                if block.parent_key:
                    db.execute("UPDATE edition_blocks SET parent_block_id=? WHERE id=?",
                               (block_ids[block.parent_key], block_ids[block.stable_key]))

            for annotation in package.annotations:
                annotation_id = uid()
                db.execute("INSERT INTO edition_annotations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    annotation_id, edition_id, annotation.stable_key, annotation.origin,
                    annotation.intent, annotation.visual_role, annotation.placement, annotation.body,
                    _json(annotation.payload), annotation.importance, annotation.confidence,
                    _json(annotation.provenance), _json(annotation.metadata)))
                self._insert_anchors(db, annotation_id, annotation.anchors, block_ids)

            for item in sorted(package.checkable_items, key=lambda value: value.ordinal):
                item_id = uid()
                db.execute("INSERT INTO checkable_items VALUES(?,?,?,?,?,?,?,?)", (
                    item_id, edition_id, item.stable_key, item.ordinal, item.item_kind, item.label,
                    _json([anchor.model_dump(mode="json") for anchor in item.anchors]), item.material_hash))

            self.store._event(db, "chapter_edition.published", "chapter_edition", edition_id,
                              {"scope_id": scope_id, "revision": revision, "complete": True})
        return self.get_edition(edition_id)

    @staticmethod
    def _insert_anchors(db, annotation_id: str, anchors: list[AnchorSpec], block_ids: dict[str, str]) -> None:
        for ordinal, anchor in enumerate(anchors):
            db.execute("INSERT INTO annotation_anchors VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
                annotation_id, ordinal, anchor.kind,
                block_ids.get(anchor.block_key or ""), block_ids.get(anchor.after_key or ""),
                block_ids.get(anchor.before_key or ""), anchor.exact_quote, anchor.prefix,
                anchor.suffix, anchor.formula_label, anchor.segment_hint,
                _json(anchor.bbox) if anchor.bbox is not None else None))

    def latest(self, scope_id: str) -> dict | None:
        with self.store._connection() as db:
            if not db.execute("SELECT 1 FROM source_scopes WHERE id=?", (scope_id,)).fetchone():
                raise KeyError("source scope not found")
            row = db.execute("SELECT id FROM chapter_editions WHERE scope_id=? AND status='complete' "
                             "ORDER BY revision DESC LIMIT 1", (scope_id,)).fetchone()
        return self.get_edition(row["id"]) if row else None

    def get_edition(self, edition_id: str) -> dict | None:
        with self.store._connection() as db:
            edition = db.execute("SELECT * FROM chapter_editions WHERE id=?", (edition_id,)).fetchone()
            if not edition:
                return None
            result = dict(edition)
            result["skill_versions"] = json.loads(result["skill_versions"])
            blocks = [dict(row) for row in db.execute(
                "SELECT * FROM edition_blocks WHERE edition_id=? ORDER BY ordinal,id", (edition_id,))]
            block_keys = {row["id"]: row["stable_key"] for row in blocks}
            for block in blocks:
                block["parent_key"] = block_keys.get(block.pop("parent_block_id"))
                block["source_locator"] = json.loads(block["source_locator"])
                block["metadata"] = json.loads(block["metadata"])
            result["blocks"] = blocks

            annotations = []
            for row in db.execute("SELECT * FROM edition_annotations WHERE edition_id=? ORDER BY id", (edition_id,)):
                annotation = dict(row)
                annotation["payload"] = json.loads(annotation["payload"])
                annotation["provenance"] = json.loads(annotation["provenance"])
                annotation["metadata"] = json.loads(annotation["metadata"])
                anchors = []
                for raw in db.execute("SELECT * FROM annotation_anchors WHERE annotation_id=? ORDER BY ordinal", (row["id"],)):
                    anchor = dict(raw)
                    anchor.pop("annotation_id")
                    anchor["kind"] = anchor.pop("anchor_kind")
                    anchor["block_key"] = block_keys.get(anchor.pop("block_id"))
                    anchor["after_key"] = block_keys.get(anchor.pop("after_block_id"))
                    anchor["before_key"] = block_keys.get(anchor.pop("before_block_id"))
                    anchor["bbox"] = json.loads(anchor["bbox"]) if anchor["bbox"] else None
                    anchors.append(anchor)
                annotation["anchors"] = anchors
                annotations.append(annotation)
            result["annotations"] = annotations

            items = []
            for row in db.execute("SELECT * FROM checkable_items WHERE edition_id=? ORDER BY ordinal,id", (edition_id,)):
                item = dict(row)
                item["anchors"] = json.loads(item.pop("anchor_spec"))
                checks = [dict(check) for check in db.execute(
                    "SELECT * FROM study_checks_v2 WHERE checkable_item_id=? ORDER BY checked_at,id", (row["id"],))]
                for check in checks:
                    check["understood"] = bool(check["understood"])
                item["checks"] = checks
                item["current_check"] = checks[-1] if checks else None
                items.append(item)
            result["checkable_items"] = items
            return result

    def record_check(self, item_id: str, understood: bool, reconfirmation_reason: str = "",
                     carried_from_check_id: str | None = None) -> dict:
        check_id, timestamp = uid(), now()
        with self.store._connection() as db:
            item = db.execute("SELECT stable_key,material_hash FROM checkable_items WHERE id=?", (item_id,)).fetchone()
            if not item:
                raise KeyError("checkable item not found")
            if carried_from_check_id:
                old = db.execute("""SELECT c.id,i.stable_key,i.material_hash FROM study_checks_v2 c
                    JOIN checkable_items i ON i.id=c.checkable_item_id WHERE c.id=?""",
                                 (carried_from_check_id,)).fetchone()
                if not old or old["stable_key"] != item["stable_key"] or old["material_hash"] != item["material_hash"]:
                    raise ValueError("carried check must belong to unchanged material with the same stable item key")
            db.execute("INSERT INTO study_checks_v2 VALUES(?,?,?,?,?,?)", (
                check_id, item_id, int(understood), timestamp, carried_from_check_id,
                reconfirmation_reason.strip()))
            self.store._event(db, "study_check_v2.recorded", "checkable_item", item_id,
                              {"check_id": check_id, "understood": bool(understood)})
        return {"id": check_id, "checkable_item_id": item_id, "understood": bool(understood),
                "checked_at": timestamp, "carried_from_check_id": carried_from_check_id,
                "reconfirmation_reason": reconfirmation_reason.strip()}

