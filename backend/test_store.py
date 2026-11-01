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


if __name__ == "__main__": unittest.main()
