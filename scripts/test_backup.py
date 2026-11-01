"""Tests for validated local backup creation and restore."""
from __future__ import annotations

import json
import base64
import hashlib
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.backup_restore import BackupError, create_backup, restore_backup


class BackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "source.sqlite3"
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.pdf = self.root / "source.pdf"
        self.pdf.write_bytes(b"registered pdf test asset")
        self.vault.joinpath("topic.md").write_text("# Topic\nA preserved note.\n", encoding="utf-8")
        self.vault.joinpath(".obsidian").mkdir()
        self.vault.joinpath(".obsidian", "app.json").write_text("{}", encoding="utf-8")
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE sources(id TEXT PRIMARY KEY, title TEXT, metadata TEXT, created_at TEXT)")
        conn.execute("CREATE TABLE atlas_operations(id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE, status TEXT, payload TEXT, result TEXT, error TEXT, created_at TEXT, updated_at TEXT)")
        metadata = {"local_file": {"path": str(self.pdf), "sha256": self._sha(self.pdf), "page_count": 2}}
        conn.execute("INSERT INTO sources VALUES(?,?,?,?)", ("src-1", "Test source", json.dumps(metadata), "now"))
        conn.commit()
        conn.close()
        self.archive = self.root / "backup.zip"

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _sha(path: Path) -> str:
        import hashlib
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_round_trip_restores_database_vault_pdf_and_rebound_path(self):
        info = create_backup(self.db, self.vault, self.archive)
        self.assertEqual(info["registered_pdfs"], 1)
        destination = self.root / "restored"
        destination.mkdir()  # An existing empty directory is a valid restore target.
        result = restore_backup(self.archive, destination)
        self.assertEqual(Path(result["database"]).read_bytes()[:16], b"SQLite format 3\x00")
        self.assertEqual((destination / "vault" / "topic.md").read_text(encoding="utf-8"),
                         "# Topic\nA preserved note.\n")
        self.assertEqual((destination / "vault" / ".obsidian" / "app.json").read_text(), "{}")
        restored_pdf = destination / "assets" / "pdfs" / "src-1" / "source.pdf"
        self.assertEqual(restored_pdf.read_bytes(), self.pdf.read_bytes())
        conn = sqlite3.connect(result["database"])
        metadata = json.loads(conn.execute("SELECT metadata FROM sources WHERE id='src-1'").fetchone()[0])
        conn.close()
        self.assertEqual(Path(metadata["local_file"]["path"]), restored_pdf.resolve())
        self.assertEqual(metadata["local_file"]["sha256"], self._sha(restored_pdf))

    def test_corrupt_payload_is_rejected_before_restore_destination_is_created(self):
        create_backup(self.db, self.vault, self.archive)
        changed = self.root / "changed.zip"
        with zipfile.ZipFile(self.archive) as original, zipfile.ZipFile(changed, "w", zipfile.ZIP_DEFLATED) as output:
            for item in original.infolist():
                payload = original.read(item.filename)
                if item.filename == "vault/topic.md":
                    payload = b"tampered note"
                output.writestr(item, payload)
        destination = self.root / "must-stay-absent"
        with self.assertRaises(BackupError):
            restore_backup(changed, destination)
        self.assertFalse(destination.exists())

    def test_nonempty_destination_is_refused_without_touching_existing_files(self):
        create_backup(self.db, self.vault, self.archive)
        destination = self.root / "existing"
        destination.mkdir()
        sentinel = destination / "keep.txt"
        sentinel.write_text("user data", encoding="utf-8")
        with self.assertRaises(BackupError):
            restore_backup(self.archive, destination)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "user data")
        self.assertEqual(list(destination.iterdir()), [sentinel])

    def test_path_traversal_member_is_rejected_before_writing_outside_restore_root(self):
        create_backup(self.db, self.vault, self.archive)
        changed = self.root / "traversal.zip"
        with zipfile.ZipFile(self.archive) as original, zipfile.ZipFile(changed, "w", zipfile.ZIP_DEFLATED) as output:
            for item in original.infolist():
                output.writestr(item, original.read(item.filename))
            output.writestr("../escaped.txt", b"must not be written")
        destination = self.root / "traversal-restore"
        with self.assertRaises(BackupError):
            restore_backup(changed, destination)
        self.assertFalse(destination.exists())
        self.assertFalse((self.root / "escaped.txt").exists())

    def test_existing_backup_output_is_never_deleted_or_overwritten(self):
        self.archive.write_text("existing user file", encoding="utf-8")
        with self.assertRaises(BackupError):
            create_backup(self.db, self.vault, self.archive)
        self.assertEqual(self.archive.read_text(encoding="utf-8"), "existing user file")

    def test_pending_journal_is_rejected_before_restore_can_touch_original_absolute_path(self):
        create_backup(self.db, self.vault, self.archive)
        original = self.root / "original-atlas.md"
        original.write_text("must survive", encoding="utf-8")
        with tempfile.TemporaryDirectory() as work_name:
            work_db = Path(work_name) / "study.sqlite3"
            with zipfile.ZipFile(self.archive) as source:
                work_db.write_bytes(source.read("database/study.sqlite3"))
                members = [(item.filename, source.read(item.filename), item.is_dir())
                           for item in source.infolist()]
            conn = sqlite3.connect(work_db)
            payload = {"originals": [{"path": str(original), "existed": True,
                                      "content": base64.b64encode(b"overwritten by recovery").decode("ascii")}],
                       "changes": []}
            conn.execute("INSERT INTO atlas_operations VALUES(?,?,?,?,?,?,?,?)",
                         ("pending", "pending-key", "applying", json.dumps(payload), None, None, "t", "t"))
            conn.commit()
            conn.close()
            db_bytes = work_db.read_bytes()

        changed = self.root / "pending-journal.zip"
        with zipfile.ZipFile(self.archive) as source, zipfile.ZipFile(changed, "w", zipfile.ZIP_DEFLATED) as output:
            manifest = json.loads(source.read("manifest.json"))
            entry = next(item for item in manifest["files"] if item["path"] == "database/study.sqlite3")
            entry["size"] = len(db_bytes)
            entry["sha256"] = hashlib.sha256(db_bytes).hexdigest()
            for info in source.infolist():
                if info.filename == "database/study.sqlite3":
                    output.writestr(info, db_bytes)
                elif info.filename == "manifest.json":
                    output.writestr(info, json.dumps(manifest).encode("utf-8"))
                else:
                    output.writestr(info, source.read(info.filename))

        destination = self.root / "pending-restore"
        with self.assertRaisesRegex(BackupError, "interrupted Atlas file operation"):
            restore_backup(changed, destination)
        self.assertFalse(destination.exists())
        self.assertEqual(original.read_text(encoding="utf-8"), "must survive")

    def test_backup_refuses_database_with_applying_journal(self):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO atlas_operations VALUES(?,?,?,?,?,?,?,?)",
                     ("pending", "pending-key", "applying", "{}", None, None, "t", "t"))
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(BackupError, "interrupted Atlas file operation"):
            create_backup(self.db, self.vault, self.archive)
        self.assertFalse(self.archive.exists())


if __name__ == "__main__":
    unittest.main()
