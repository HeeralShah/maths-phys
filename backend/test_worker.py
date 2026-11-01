import tempfile
import unittest
from pathlib import Path

import fitz

from backend.claude_worker import Worker, WorkerSettings
from backend.store import Store


class FakeAdapter:
    def __init__(self, output, estimate=0.01):
        self.output, self.estimate, self.calls = output, estimate, []

    def generate(self, job, context, tools, skill_name, budget_usd):
        self.calls.append({"job": job, "context": context, "skill_names": skill_name, "budget_usd": budget_usd})
        if job["job_type"] == "prepare":
            for page in __import__("json").loads(job["payload"]).get("pages", []):
                tools.source_page(context["source"]["id"], int(page))
        return self.output, self.estimate


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "service.sqlite3")
        self.vault = self.root / "vault"
        (self.vault / "02 Atlas").mkdir(parents=True)
        pdf = self.root / "source.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Energy is conserved.")
        doc.save(pdf)
        doc.close()
        self.source = self.store.register_pdf("Physics", str(pdf), sections=[{"title": "Energy", "units": [{"title": "Conservation"}]}])
        self.settings = WorkerSettings("claude", "claude-test-model", 8, 0.2, 2.0, "test-key")

    def tearDown(self): self.tmp.cleanup()

    def test_prepare_imports_only_complete_output_and_records_cost(self):
        job = self.store.enqueue("prepare", self.source["id"], "prepare:worker", {"source_id": self.source["id"], "pages": [1]})
        adapter = FakeAdapter({"complete": True, "edition": {"title": "Energy", "units": [
            {"section_title": "Energy", "unit_title": "Conservation", "content": "Energy is conserved.", "source_refs": [{"page": 1, "locator": "PDF page 1"}]}]}})
        result = Worker(self.store, self.settings, adapter, self.vault).run_once()
        self.assertEqual(result["id"], job["id"])
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(adapter.calls[0]["skill_names"], ["prepare-edition"])
        unit_id = self.source["sections"][0]["units"][0]["id"]
        edition = self.store.read_edition(unit_id)
        self.assertEqual(edition["content"], "Energy is conserved.")
        self.assertEqual(edition["source_refs"], [{"page": 1, "locator": "PDF page 1"}])
        with self.store._connection() as db:
            usage = db.execute("SELECT status,actual_usd FROM agent_budget_usage WHERE job_id=?", (job["id"],)).fetchone()
        self.assertEqual(usage["status"], "settled")
        self.assertEqual(usage["actual_usd"], 0.01)

    def test_incomplete_output_fails_job_without_publishing_any_revision(self):
        job = self.store.enqueue("prepare", self.source["id"], "prepare:incomplete", {"source_id": self.source["id"], "pages": [1]})
        adapter = FakeAdapter({"edition": {"title": "Partial", "units": [
            {"section_title": "Energy", "unit_title": "Conservation", "content": "partial"}]}})
        result = Worker(self.store, self.settings, adapter, self.vault).run_once()
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(self.store.read_edition(self.source["sections"][0]["units"][0]["id"]))

    def test_recovered_job_reuses_atomic_publication_without_second_agent_call(self):
        import json
        job = self.store.enqueue("prepare", self.source["id"], "prepare:recovery", {"source_id": self.source["id"], "pages": [1]})
        unit = self.source["sections"][0]["units"][0]
        package = {"complete": True, "edition": {"title": "Recovery", "units": [
            {"section_title": "Energy", "unit_title": "Conservation", "content": "Energy is conserved.",
             "source_refs": [{"page": 1, "locator": "PDF page 1"}]}]}}
        first = self.store.import_prepared_edition(self.source["id"], package, f"job:{job['id']}")
        adapter = FakeAdapter({})
        recovered = Worker(self.store, self.settings, adapter, self.vault).run_once()
        self.assertEqual(recovered["status"], "succeeded")
        self.assertEqual(json.loads(recovered["result"])["recovered_publication"], True)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(self.store.read_edition(unit["id"])["id"], first["units"][0]["id"])

    def test_signoff_plan_uses_checked_snapshot_and_applies_after_signoff(self):
        section = self.source["sections"][0]
        unit = section["units"][0]
        revision = self.store.save_revision(unit["id"], "Energy is conserved.", source_refs=[{"page": 1}])
        self.store.add_check(revision["id"], "understood", True)
        job = self.store.signoff_section(section["id"], "learner", "signoff:worker")
        import json
        signoff_id = json.loads(job["payload"])["signoff_id"]
        output = {"signoff_id": signoff_id, "source_revision_ids": [revision["id"]],
                  "idempotency_key": f"signoff:{signoff_id}",
                  "expected_hashes": {"02 Atlas/Energy.md": None},
                  "files": [{"path": "02 Atlas/Energy.md", "content": "# Energy\n\nEnergy is conserved.\n"}]}
        adapter = FakeAdapter(output)
        completed = Worker(self.store, self.settings, adapter, self.vault).run_once()
        self.assertEqual(completed["status"], "succeeded")
        plan_id = json.loads(completed["result"])["plan_id"]
        plan = self.store.get_synthesis_plan(plan_id)
        self.assertEqual(plan["status"], "applied_unversioned")
        self.assertTrue((self.vault / "02 Atlas/Energy.md").exists())
        applied = self.store.apply_imported_synthesis_plan(plan_id, self.vault)
        self.assertEqual(applied["versioning_status"], "applied_unversioned")
        self.assertTrue((self.vault / "02 Atlas/Energy.md").exists())

    def test_missing_worker_settings_fails_before_claiming_queued_job(self):
        job = self.store.enqueue("prepare", self.source["id"], "prepare:no-config", {"pages": [1]})
        with self.assertRaises(RuntimeError): WorkerSettings.from_env({})
        with self.assertRaises(RuntimeError): WorkerSettings.from_env({
            "MATHSPHYS_AGENT_ENABLED": "1", "MATHSPHYS_AGENT_PROVIDER": "claude",
            "MATHSPHYS_AGENT_MODEL": "claude-test", "MATHSPHYS_AGENT_MAX_TURNS": "2",
            "MATHSPHYS_AGENT_JOB_BUDGET_USD": "0.1", "MATHSPHYS_AGENT_TOTAL_BUDGET_USD": "NaN",
            "ANTHROPIC_API_KEY": "test"})
        self.assertEqual(self.store.get_job(job["id"])["status"], "queued")

    def test_learning_profile_is_durable_and_never_enqueues_jobs(self):
        profile = self.store.update_learning_profile({"goals": "derive wave equations", "assumed_knowledge": ["integration by parts"],
            "misconceptions": ["boundary terms always vanish"], "preferred_explanations": "worked steps", "preferences": {"notation": "source"}, "notes": "local only"})
        reopened = Store(self.root / "service.sqlite3")
        self.assertEqual(reopened.get_learning_profile()["goals"], profile["goals"])
        self.assertEqual(reopened.get_learning_profile()["preferences"]["notation"], "source")
        self.assertEqual(reopened.jobs(), [])


if __name__ == "__main__": unittest.main()
