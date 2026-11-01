import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from pydantic import ValidationError

from backend.chapter_editions import ChapterRepository
from backend.chapter_routes import build_router as build_chapter_router
from backend.contracts.chapter_v2 import ChapterPackage
from backend.contracts.literature_v2 import LiteratureMapPackage
from backend.literature import LiteratureRepository
from backend.literature_routes import build_router as build_literature_router
from backend.store import Store


def chapter_payload(publication_key="chapter:one"):
    return {
        "schema_version": 2,
        "complete": True,
        "publication_key": publication_key,
        "source_sha256": "b" * 64,
        "generator": "test harness",
        "model": "provider-neutral-test",
        "prompt_version": "reader-v2",
        "skill_versions": {"annotation": "1"},
        "blocks": [
            {"stable_key": "eq-a", "ordinal": 0, "kind": "equation", "source_content": "x=x",
             "source_locator": {"physical_page": 1}},
            {"stable_key": "eq-b", "ordinal": 1, "kind": "equation", "source_content": "x+0=x",
             "source_locator": {"physical_page": 1}},
            {"stable_key": "claim", "ordinal": 2, "kind": "paragraph",
             "source_content": "Therefore the two expressions agree.", "source_locator": {"physical_page": 1}}
        ],
        "annotations": [{
            "stable_key": "bridge-a-b", "origin": "generated", "intent": "derivation",
            "visual_role": "yellow_explanation", "placement": "interlinear",
            "anchors": [{"kind": "gap", "after_key": "eq-a", "before_key": "eq-b"}],
            "payload": {
                "rows": [
                    {"id": "r1", "segments": [{"id": "x", "latex": "x"}]},
                    {"id": "r2", "segments": [{"id": "x", "latex": "x"}, {"id": "z", "latex": "+0"}]}
                ],
                "correspondences": [{"from_row": "r1", "from_segment": "x", "to_row": "r2",
                                      "to_segment": "x", "role": "preserved"}],
                "rules": [{"after_row": "r1", "label": "Additive identity",
                           "explanation": "Adding zero leaves the expression unchanged."}]
            },
            "provenance": [{"kind": "source", "page": 1}]
        }],
        "checkable_items": [{
            "stable_key": "check-equality", "ordinal": 0, "item_kind": "equation_group",
            "label": "The additive-identity step", "anchors": [{"kind": "block", "block_key": "eq-b"}],
            "material_hash": "a" * 64
        }],
        "coverage": {"represented_blocks": ["eq-a", "eq-b", "claim"], "typed_omissions": []}
    }


def literature_payload(publication_key="map:one"):
    return {
        "schema_version": 2,
        "complete": True,
        "publication_key": publication_key,
        "focal_work_key": "focal",
        "generator": "test harness",
        "model": "provider-neutral-test",
        "works": [
            {"local_key": "focal", "work_type": "paper", "title": "A focal paper",
             "authors": ["Ada Author"], "year": 2020, "doi": "10.1000/focal",
             "metadata_provenance": {"provider": "publisher"}},
            {"local_key": "prior", "work_type": "paper", "title": "A prior theorem",
             "authors": ["Priya Prior"], "year": 2010, "doi": "10.1000/prior",
             "metadata_provenance": {"provider": "publisher"}}
        ],
        "map_works": [
            {"work_key": "focal", "roles": ["focal"], "importance_reason": "Selected paper", "lane": "focal"},
            {"work_key": "prior", "roles": ["predecessor"], "importance_reason": "Supplies the theorem",
             "lane": "predecessor"}
        ],
        "evidence": [
            {"local_key": "focal-text", "work_key": "focal", "evidence_kind": "direct_text",
             "locator": "Section 2", "quote": "We apply the theorem of Prior."},
            {"local_key": "prior-text", "work_key": "prior", "evidence_kind": "direct_text",
             "locator": "Theorem 1", "quote": "The theorem holds under assumption A."},
            {"local_key": "citation", "work_key": "focal", "evidence_kind": "bibliographic_metadata",
             "locator": "References", "quote": "Prior, A prior theorem."}
        ],
        "paper_records": [{
            "stable_key": "result", "record_type": "result", "label": "Main result",
            "claim": "The focal result uses the prior theorem.", "section_label": "Section 2",
            "locator": {"section": "2"}, "evidence_keys": ["focal-text"]
        }],
        "relationships": [
            {"stable_key": "citation-link", "from_work_key": "focal", "to_work_key": "prior",
             "relationship_class": "citation", "relation_type": "cites",
             "claim": "The focal paper cites the prior paper.", "epistemic_status": "bibliographic_fact",
             "citation_status": "cites", "evidence_keys": ["citation"]},
            {"stable_key": "result-link", "from_work_key": "focal", "to_work_key": "prior",
             "relationship_class": "intellectual", "relation_type": "uses_result_from",
             "claim": "The focal proof uses the prior theorem.", "epistemic_status": "stated",
             "citation_status": "cites", "evidence_keys": ["focal-text", "prior-text"],
             "contexts": [{"section_label": "Section 2", "paper_record_key": "result",
                           "source_anchor": {"section": "2"}}]}
        ],
        "research_scope": {"included": "direct theorem ancestry"},
        "cutoff_reason": "Stopped after the direct prerequisite was evidenced.",
        "provider_provenance": {"provider": "test fixture"}
    }


class V2FoundationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "study.sqlite3"
        self.store = Store(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_chapter_publication_is_complete_atomic_idempotent_and_granular(self):
        source = self.store.register_source("Chapter source")
        chapters = ChapterRepository(self.store)
        scope = chapters.create_scope(source["id"], "chapter", "Chapter 1", 0,
                                      {"physical_page": 1}, {"physical_page": 8}, "learner_confirmed")
        package = ChapterPackage.model_validate(chapter_payload())
        published = chapters.publish(scope["id"], package)
        repeated = chapters.publish(scope["id"], package)
        self.assertEqual(published["id"], repeated["id"])
        self.assertEqual(published["status"], "complete")
        self.assertEqual([block["stable_key"] for block in published["blocks"]], ["eq-a", "eq-b", "claim"])
        self.assertEqual(published["annotations"][0]["anchors"][0]["after_key"], "eq-a")
        item = published["checkable_items"][0]
        checked = chapters.record_check(item["id"], True)
        self.assertTrue(checked["understood"])
        self.assertTrue(chapters.latest(scope["id"])["checkable_items"][0]["current_check"]["understood"])
        self.assertEqual(self.store.jobs(), [], "publishing and reading saved chapters must not invoke an agent")

        changed = chapter_payload()
        changed["blocks"][2]["source_content"] = "Changed source"
        with self.assertRaisesRegex(ValueError, "different complete chapter"):
            chapters.publish(scope["id"], ChapterPackage.model_validate(changed))
        with self.store._connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM chapter_editions").fetchone()[0], 1)

    def test_chapter_contract_rejects_unresolved_anchors_coverage_and_bad_derivations(self):
        bad_anchor = chapter_payload("bad-anchor")
        bad_anchor["annotations"][0]["anchors"][0]["before_key"] = "missing"
        with self.assertRaisesRegex(ValidationError, "gap anchor block does not resolve"):
            ChapterPackage.model_validate(bad_anchor)

        bad_coverage = chapter_payload("bad-coverage")
        bad_coverage["coverage"]["represented_blocks"].pop()
        with self.assertRaisesRegex(ValidationError, "coverage must list every source block"):
            ChapterPackage.model_validate(bad_coverage)

        bad_derivation = chapter_payload("bad-derivation")
        bad_derivation["annotations"][0]["payload"]["rules"] = []
        with self.assertRaises(ValidationError):
            ChapterPackage.model_validate(bad_derivation)

        generated_blue = chapter_payload("generated-blue")
        generated_blue["annotations"][0]["visual_role"] = "blue_historical"
        with self.assertRaisesRegex(ValidationError, "generated understanding is forbidden"):
            ChapterPackage.model_validate(generated_blue)

    def test_literature_map_contains_works_only_and_separates_citation_from_intellectual_claims(self):
        maps = LiteratureRepository(self.store)
        package = LiteratureMapPackage.model_validate(literature_payload())
        published = maps.publish(package)
        repeated = maps.publish(package)
        self.assertEqual(published["id"], repeated["id"])
        self.assertEqual(len(published["works"]), 2)
        self.assertEqual({item["relationship_class"] for item in published["relationships"]},
                         {"citation", "intellectual"})
        self.assertTrue(all(item["id"] for item in published["works"]))
        self.assertEqual(maps.latest(published["focal_work_id"])["id"], published["id"])
        self.assertEqual(self.store.jobs(), [], "reading a saved literature map must not invoke an agent")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store._connection() as db:
                db.execute("""UPDATE literature_relationships
                    SET relationship_class='intellectual', relation_type='extends'
                    WHERE relationship_class='citation'""")

        bare_influence = literature_payload("bad-influence")
        bare_influence["relationships"][1]["evidence_keys"] = ["citation"]
        with self.assertRaisesRegex(ValidationError, "direct-text evidence"):
            LiteratureMapPackage.model_validate(bare_influence)

        disguised = literature_payload("bad-class")
        disguised["relationships"][0]["relationship_class"] = "intellectual"
        disguised["relationships"][0]["epistemic_status"] = "inferred"
        with self.assertRaisesRegex(ValidationError, "intellectual relationships"):
            LiteratureMapPackage.model_validate(disguised)

    def test_literature_publication_rolls_back_when_durable_reference_is_invalid(self):
        maps = LiteratureRepository(self.store)
        invalid = literature_payload("map:invalid-source")
        invalid["evidence"][0]["source_id"] = "missing-source"
        package = LiteratureMapPackage.model_validate(invalid)
        with self.assertRaisesRegex(ValueError, "source_id does not resolve"):
            maps.publish(package)
        with self.store._connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM works").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM paper_analyses").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM literature_maps").fetchone()[0], 0)

    def test_v2_routers_are_present_without_replacing_v1(self):
        app = FastAPI()
        app.include_router(build_chapter_router(self.store))
        app.include_router(build_literature_router(self.store))
        paths = set(app.openapi()["paths"])
        self.assertTrue({
            "/sources/{source_id}/scopes",
            "/source-scopes/{scope_id}/editions/publish",
            "/source-scopes/{scope_id}/editions/latest",
            "/chapter-editions/{edition_id}",
            "/checkable-items/{item_id}/checks",
            "/literature-maps/publish",
            "/literature-maps/{map_id}",
            "/works/{work_id}/literature-maps/latest",
        }.issubset(paths))


class MigrationTests(unittest.TestCase):
    def test_current_store_database_upgrades_additively_and_only_once(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "legacy.sqlite3"
            db = sqlite3.connect(path)
            db.execute("""CREATE TABLE sources(
                id TEXT PRIMARY KEY, title TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL)""")
            db.execute("INSERT INTO sources VALUES(?,?,?,?)",
                       ("legacy-source", "Preserved source", json.dumps({"legacy": True}), "2020-01-01"))
            db.commit()
            db.close()

            upgraded = Store(path)
            with upgraded._connection() as connection:
                self.assertEqual(connection.execute(
                    "SELECT title FROM sources WHERE id='legacy-source'").fetchone()[0], "Preserved source")
                self.assertEqual(connection.execute(
                    "SELECT name FROM schema_migrations WHERE version=1").fetchone()[0],
                    "chapter_editions_and_literature_maps")
                self.assertEqual(connection.execute(
                    "SELECT name FROM schema_migrations WHERE version=2").fetchone()[0],
                    "enforce_top_level_scope_order")
                self.assertEqual(connection.execute(
                    "SELECT name FROM schema_migrations WHERE version=3").fetchone()[0],
                    "guard_work_only_relationship_semantics")
                self.assertTrue(connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='chapter_editions'").fetchone())
                self.assertTrue(connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='literature_maps'").fetchone())

            Store(path)
            connection = sqlite3.connect(path)
            try:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 3)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0], 1)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()

