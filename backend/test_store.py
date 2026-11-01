import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

from backend.store import Store
from backend.worker_protocol import run_job


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "service.sqlite3"
        self.store = Store(self.path)

    def tearDown(self): self.tmp.cleanup()

    def make_revision(self):
        source = self.store.register_source("Mechanics", {"kind": "textbook"}, [
            {"title": "Forces", "units": [{"title": "Newton's laws"}]}
        ])
        unit_id = source["sections"][0]["units"][0]["id"]
        return unit_id, self.store.save_revision(unit_id, "First edition")

    def test_saved_edition_survives_restart_and_is_immutable(self):
        unit, first = self.make_revision()
        second = self.store.save_revision(unit, "Second edition")
        self.assertEqual((first["revision"], second["revision"]), (1, 2))
        self.assertNotEqual(first["id"], second["id"])
        self.assertLessEqual(first["created_at"], second["created_at"])
        reopened = Store(self.path)
        self.assertEqual(reopened.read_edition(unit)["content"], "Second edition")
        self.assertEqual(reopened.read_edition(unit)["id"], second["id"])

    def test_manual_checks_are_persisted_and_reads_do_not_enqueue(self):
        _, revision = self.make_revision()
        check = self.store.add_check(revision["id"], "notation", False, "Check sign convention")
        self.assertTrue(check["created_at"])
        reopened = Store(self.path)
        self.assertEqual(reopened.get_checks(revision["id"])[0]["detail"], "Check sign convention")
        self.assertEqual(reopened.read_edition(revision["unit_id"])["id"], revision["id"])
        self.assertEqual(reopened.jobs(), [])

    def test_section_signoff_includes_only_understood_units_and_can_retract(self):
        specs = [{"title": "Chapter", "units": [{"title": f"Unit {i}"} for i in range(8)]}]
        source = self.store.register_source("Eight units", sections=specs)
        section = source["sections"][0]
        revisions = []
        for unit in section["units"]:
            revision = self.store.save_revision(unit["id"], "edition")
            revisions.append(revision)
        for revision in revisions[:6]:
            self.store.add_check(revision["id"], "understood", True)
        # A later false state retracts this unit from the next signoff snapshot.
        self.store.add_check(revisions[0]["id"], "understood", False)
        self.assertFalse(self.store.understanding(revisions[0]["id"]))
        self.store.add_check(revisions[0]["id"], "understood", True)
        job = self.store.signoff_section(section["id"], "reviewer", "section-signoff:1")
        reopened = Store(self.path)
        repeated = reopened.signoff_section(section["id"], "reviewer", "section-signoff:1")
        self.assertEqual(job["id"], repeated["id"])
        import json
        included = json.loads(job["payload"])["included_units"]
        self.assertEqual(len(included), 6)
        self.assertTrue(all(item["unit_id"] in {u["id"] for u in section["units"][:6]} for item in included))

    def test_explicit_job_types_and_idempotency(self):
        first = self.store.enqueue("prepare", "source-id", "prep:1")
        same = self.store.enqueue("prepare", "source-id", "prep:1")
        self.assertEqual(first["id"], same["id"])
        self.assertEqual(self.store.get_job(first["id"])["status"], "queued")
        with self.assertRaises(ValueError): self.store.enqueue("infer", "x", "bad")

    def test_claim_complete_and_fail_transitions_are_guarded_and_durable(self):
        first = self.store.enqueue("prepare", "src", "transition:1")
        with self.assertRaises(ValueError): self.store.complete_job(first["id"], {"ok": True})
        claimed = self.store.claim_job()
        self.assertEqual(claimed["id"], first["id"])
        self.assertEqual(claimed["status"], "running")
        self.assertIsNone(self.store.claim_job())
        failed = self.store.fail_job(first["id"], "worker unavailable")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error"], "worker unavailable")

        second = self.store.enqueue("revise", "unit", "transition:2")
        self.store.claim_job()
        complete = self.store.complete_job(second["id"], {"revision_id": "new-rev"})
        self.assertEqual(complete["status"], "succeeded")
        self.assertEqual(complete["result"], '{"revision_id": "new-rev"}')
        reopened = Store(self.path)
        self.assertEqual(reopened.get_job(first["id"])["error"], "worker unavailable")
        self.assertEqual(reopened.get_job(second["id"])["status"], "succeeded")

    def test_stale_running_job_is_requeued_for_retry(self):
        job = self.store.enqueue("signoff", "section", "stale:1")
        self.store.claim_job()
        old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="microseconds")
        with self.store._connection() as db:
            db.execute("UPDATE jobs SET updated_at=? WHERE id=?", (old, job["id"]))
        self.assertEqual(self.store.recover_stale_jobs(60), 1)
        recovered = self.store.get_job(job["id"])
        self.assertEqual(recovered["status"], "queued")
        self.assertIn("stale", recovered["error"])
        self.assertEqual(self.store.recover_stale_jobs(60), 0)
        self.assertEqual(self.store.claim_job()["id"], job["id"])
        with self.assertRaises(ValueError): self.store.fail_job(job["id"], " ")

    def test_unconfigured_worker_cannot_falsely_complete_job(self):
        job = self.store.enqueue("prepare", "src", "worker-stub:1")
        with self.assertRaisesRegex(RuntimeError, "unconfigured"):
            run_job(job)
        self.assertEqual(self.store.get_job(job["id"])["status"], "queued")

    def make_graph(self):
        source = self.store.register_source("Paper")
        ev = {"locator": "p. 4, paragraph 2", "quote": "The system is assumed isolated."}
        first = self.store.create_research_node(source["id"], "assumption", "Isolation", "The model assumes isolation.", evidence=[ev])
        second = self.store.create_research_node(source["id"], "result", "Conservation", "Energy is conserved.", evidence=[{"locator": "p. 5, eq. 3", "quote": "dE/dt = 0"}])
        return source, first, second, ev

    def test_research_graph_is_evidence_linked_and_local(self):
        source, first, second, ev = self.make_graph()
        edge = self.store.create_research_edge(first["id"], second["id"], "requires", "Result relies on isolated-system assumption.", evidence=[{"source_id": source["id"], **ev}])
        graph = self.store.research_graph(source["id"])
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(graph["edges"][0]["relation"], "requires")
        self.assertEqual(graph["edges"][0]["evidence"][0]["locator"], ev["locator"])
        self.assertEqual(self.store.jobs(), [])
        updated = self.store.update_research_node(first["id"], "assumption", "Isolation", "Updated claim", evidence=[ev])
        self.assertEqual(updated["claim"], "Updated claim")
        self.assertTrue(self.store.delete_research_edge(edge["id"]))
        self.assertTrue(self.store.delete_research_node(first["id"]))
        self.assertEqual(self.store.research_graph()["edges"], [])

    def test_source_filtered_graph_keeps_cross_source_edge_endpoints(self):
        source_a = self.store.register_source("Paper A")
        source_b = self.store.register_source("Paper B")
        a = self.store.create_research_node(source_a["id"], "literature", "A", "Paper A is cited.", evidence=[{"locator":"p. 1", "quote":"A claim"}])
        b = self.store.create_research_node(source_b["id"], "result", "B", "Paper B cites A.", evidence=[{"locator":"p. 2", "quote":"B claim"}])
        self.store.create_research_edge(b["id"], a["id"], "cites", "Paper B cites Paper A.", evidence=[{"source_id":source_b["id"], "locator":"p. 2", "quote":"We build on Paper A."}])
        graph = self.store.research_graph(source_b["id"])
        ids = {node["id"] for node in graph["nodes"]}
        self.assertEqual(ids, {a["id"], b["id"]})
        self.assertTrue(all(edge["from_id"] in ids and edge["to_id"] in ids for edge in graph["edges"]))

    def test_graph_rejects_unanchored_claims_and_invalid_relations(self):
        source = self.store.register_source("Paper")
        with self.assertRaises(ValueError):
            self.store.create_research_node(source["id"], "result", "R", "Claim", evidence=[])
        node = self.store.create_research_node(source["id"], "result", "R", "Claim", evidence=[{"locator":"p.1", "quote":"evidence"}])
        with self.assertRaises(ValueError):
            self.store.create_research_edge(node["id"], node["id"], "related", "claim", evidence=[{"source_id":source["id"],"locator":"p.1","quote":"evidence"}])

    def test_problem_catalogue_hides_ladder_and_reveal_does_not_enqueue(self):
        source = self.store.register_source("Mechanics", sections=[{"title":"Ch 1", "units":[{"title":"Forces"}]}])
        assistance = {"orientation":"Identify the forces.", "small_hint":"Draw a free-body diagram.",
                      "strong_hint":"Resolve along the incline.", "partial_solution":"Write Newton's second law.",
                      "full_solution":"CONFIDENTIAL full derivation"}
        problem = self.store.create_problem(source["id"], "Find the acceleration.", "inline", "Forces / exercise 1",
            "mechanics", [{"label":"Newton's laws"}], "familiar", "force balance + kinematics", "multi-step",
            {"locator":"p. 9, problem 2", "quote":"Find the acceleration of the block."}, "I found signs confusing.",
            {"assessment":"moderate", "reason":"Requires resolving weight and friction along a slope."}, assistance)
        listed = self.store.list_problems(source["id"], "acceleration")
        self.assertEqual(listed[0]["id"], problem["id"])
        self.assertNotIn("assistance", str(listed))
        self.assertNotIn("solution", str(listed).lower())
        self.assertEqual(self.store.reveal_problem_level(problem["id"], "small_hint"),
                         {"problem_id":problem["id"], "level":"small_hint", "content":assistance["small_hint"]})
        self.assertEqual(self.store.reveal_problem_level(problem["id"], "full_solution")["content"], assistance["full_solution"])
        with self.store._connection() as db:
            material = db.execute("SELECT content FROM problem_assistance WHERE problem_id=? AND level='full_solution'", (problem["id"],)).fetchone()[0]
            events = " ".join(r[0] for r in db.execute("SELECT payload FROM events"))
            raw_db = " ".join(r[0] for r in db.execute("SELECT content FROM problem_assistance WHERE problem_id=?", (problem["id"],)))
        self.assertNotIn(assistance["full_solution"], material)
        self.assertNotIn(assistance["full_solution"], events)
        self.assertNotIn(assistance["full_solution"], raw_db)
        self.assertEqual(self.store.jobs(), [])
        self.assertEqual(self.store.sources()[0]["id"], source["id"])

    def test_difficulty_rejects_duration_fields(self):
        source = self.store.register_source("Mechanics")
        with self.assertRaisesRegex(ValueError, "only assessment and reason"):
            self.store.create_problem(source["id"], "Prompt", "inline", None, "mechanics", [], "familiar", "one idea", "single-step",
                {"locator":"p.1", "quote":"question"}, "no reflection", {"assessment":"easy", "reason":"one step", "time_estimate":5},
                {"orientation":"a", "small_hint":"b", "strong_hint":"c", "partial_solution":"d", "full_solution":"e"})


if __name__ == "__main__": unittest.main()
