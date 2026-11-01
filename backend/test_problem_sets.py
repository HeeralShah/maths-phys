"""Tests for the ordered problem-set API router and persistence."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.problem_sets import CreateProblemSet, UpdateProblemSet, build_router
from backend.store import Store


class ProblemSetRouterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "study.sqlite3")
        self.source = self.store.register_source("Mechanics", {"kind": "lecture"})
        self.problems = [self._make_problem(label) for label in ("first", "second", "third")]
        self.router = build_router(self.store)
        self.routes = {(method, route.path): route.endpoint
                       for route in self.router.routes for method in route.methods}

    def tearDown(self):
        self.temp.cleanup()

    def _make_problem(self, label: str) -> dict:
        assistance = {level: f"private {level} for {label}" for level in
                      ("orientation", "small_hint", "strong_hint", "partial_solution", "full_solution")}
        return self.store.create_problem(
            self.source["id"], f"Prompt {label}", "inline", f"p. {label}", "classical mechanics",
            [], "application", "one idea", "short qualitative", {"locator": f"p. {label}", "quote": f"Prompt {label}"},
            "Not yet attempted", None, assistance)

    def _create(self, ids=None):
        return self.routes[("POST", "/problem-sets")](CreateProblemSet(
            title="Rotating frames", description="A selected practice sequence",
            problem_ids=ids if ids is not None else [self.problems[0]["id"], self.problems[1]["id"]]))

    def test_create_list_and_read_preserve_order_and_never_expose_assistance(self):
        chosen = [self.problems[2]["id"], self.problems[0]["id"]]
        created = self._create(chosen)
        self.assertEqual(created["problem_ids"], chosen)
        self.assertEqual([problem["prompt"] for problem in created["problems"]], ["Prompt third", "Prompt first"])
        self.assertEqual(created["title"], "Rotating frames")
        for problem in created["problems"]:
            self.assertNotIn("assistance", problem)
            self.assertNotIn("solution", problem)

        listed = self.routes[("GET", "/problem-sets")]()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["problem_ids"], chosen)
        self.assertEqual(self.routes[("GET", "/problem-sets/{set_id}")](created["id"]), created)

    def test_update_can_change_metadata_without_changing_membership_then_replace_order(self):
        created = self._create()
        update = self.routes[("PUT", "/problem-sets/{set_id}")]
        renamed = update(created["id"], UpdateProblemSet(title="Updated title"))
        self.assertEqual(renamed["title"], "Updated title")
        self.assertEqual(renamed["problem_ids"], created["problem_ids"])

        reordered_ids = [self.problems[2]["id"], self.problems[1]["id"]]
        replaced = update(created["id"], UpdateProblemSet(problem_ids=reordered_ids))
        self.assertEqual(replaced["problem_ids"], reordered_ids)
        cleared = update(created["id"], UpdateProblemSet(problem_ids=[]))
        self.assertEqual(cleared["problem_ids"], [])
        self.assertEqual(cleared["problems"], [])

    def test_rejects_duplicate_and_nonexistent_ids_without_partial_set(self):
        create = self.routes[("POST", "/problem-sets")]
        first_id = self.problems[0]["id"]
        with self.assertRaises(HTTPException) as duplicate:
            create(CreateProblemSet(title="Bad", problem_ids=[first_id, first_id]))
        self.assertEqual(duplicate.exception.status_code, 422)
        self.assertIn("duplicates", duplicate.exception.detail)

        with self.assertRaises(HTTPException) as missing:
            create(CreateProblemSet(title="Bad", problem_ids=["missing-problem-id"]))
        self.assertEqual(missing.exception.status_code, 404)
        self.assertIn("missing-problem-id", missing.exception.detail["problem_ids"])
        self.assertEqual(self.routes[("GET", "/problem-sets")](), [])

    def test_empty_creation_and_unknown_set_are_rejected(self):
        with self.assertRaises(HTTPException) as empty:
            self.routes[("POST", "/problem-sets")](CreateProblemSet(title="Empty", problem_ids=[]))
        self.assertEqual(empty.exception.status_code, 422)
        with self.assertRaises(HTTPException) as unknown:
            self.routes[("GET", "/problem-sets/{set_id}")]("absent-set")
        self.assertEqual(unknown.exception.status_code, 404)

    def test_schema_migration_is_idempotent_and_existing_set_survives_router_rebuild(self):
        created = self._create()
        first = build_router(self.store)
        second = build_router(self.store)
        self.assertEqual(len(first.routes), len(second.routes))
        with self.store._connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM problem_sets").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM problem_set_members WHERE set_id=?",
                                        (created["id"],)).fetchone()[0], 2)
        rebuilt = {(method, route.path): route.endpoint for route in second.routes for method in route.methods}
        self.assertEqual(rebuilt[("GET", "/problem-sets/{set_id}")](created["id"])["problem_ids"], created["problem_ids"])


if __name__ == "__main__":
    unittest.main()
