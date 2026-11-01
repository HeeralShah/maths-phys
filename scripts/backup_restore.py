"""Create and restore validated local-first study backups (ZIP format, v1)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

FORMAT = "maths-phys-backup-v1"
MANIFEST = "manifest.json"


class BackupError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_archive_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise BackupError(f"invalid archive path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts) or ":" in path.parts[0]:
        raise BackupError(f"unsafe archive path: {raw!r}")
    normalized = path.as_posix()
    if normalized != raw.rstrip("/"):
        raise BackupError(f"non-canonical archive path: {raw!r}")
    return normalized


def _vault_tree(root: Path) -> tuple[list[tuple[str, Path]], list[str]]:
    files: list[tuple[str, Path]] = []
    directories: list[str] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(current)
        for name in list(dirnames):
            child = base / name
            if child.is_symlink():
                raise BackupError(f"vault contains a symlink; refusing to follow it: {child}")
            directories.append((child.relative_to(root).as_posix()))
        for name in filenames:
            child = base / name
            if child.is_symlink() or not child.is_file():
                raise BackupError(f"vault contains a non-regular file: {child}")
            files.append((f"vault/{child.relative_to(root).as_posix()}", child))
    files.sort(key=lambda pair: pair[0])
    directories.sort()
    return files, directories


def _registered_assets(snapshot: Path) -> tuple[list[dict], list[tuple[str, Path]], set[str]]:
    db = sqlite3.connect(f"file:{snapshot.as_posix()}?mode=ro", uri=True)
    try:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "sources" not in tables:
            return [], [], set()
        sources = db.execute("SELECT id,metadata FROM sources ORDER BY id").fetchall()
        protection_schemes = set()
        for table, condition in (("problem_assistance", "level='full_solution'"),
                                 ("problem_material", "kind='solution'")):
            if table in tables:
                for (content,) in db.execute(f"SELECT content FROM {table} WHERE {condition}"):
                    if isinstance(content, str) and ":" in content:
                        scheme = content.split(":", 1)[0]
                        if scheme in ("fernet", "dpapi"):
                            protection_schemes.add(scheme)
        pdfs, assets, seen = [], [], set()
        for source_id, raw_metadata in sources:
            metadata = json.loads(raw_metadata or "{}")
            local_file = metadata.get("local_file")
            if not isinstance(local_file, dict) or not local_file.get("path"):
                continue
            original = Path(local_file["path"]).expanduser().resolve(strict=True)
            if not original.is_file():
                raise BackupError(f"registered PDF is not a regular file: {original}")
            actual_sha = sha256_file(original)
            recorded_sha = local_file.get("sha256")
            if recorded_sha and recorded_sha != actual_sha:
                raise BackupError(f"registered PDF has changed since registration: {original}")
            asset_path = f"assets/pdfs/{source_id}/{original.name}"
            entry = {"source_id": source_id, "archive_path": asset_path,
                     "original_path": str(original), "sha256": actual_sha,
                     "page_count": local_file.get("page_count")}
            pdfs.append(entry)
            if asset_path not in seen:
                assets.append((asset_path, original))
                seen.add(asset_path)
        key_path = Path(str(snapshot) + ".solution.key")
        if "fernet" in protection_schemes and not key_path.is_file():
            raise BackupError("the database contains Fernet-protected solutions but its .solution.key file is missing")
        return pdfs, assets, protection_schemes
    finally:
        db.close()


def _reject_applying_atlas_operations(database_path: Path) -> None:
    """Never snapshot or restore a journal that could replay absolute paths on startup."""
    db = sqlite3.connect(database_path)
    try:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='atlas_operations'"
        ).fetchone()
        if exists and db.execute(
            "SELECT 1 FROM atlas_operations WHERE status='applying' LIMIT 1"
        ).fetchone():
            raise BackupError(
                "database has an interrupted Atlas file operation; let the app recover it "
                "before backing up or restoring"
            )
    finally:
        db.close()


def create_backup(db_path: Path, vault_path: Path, output_path: Path) -> dict:
    db_path = db_path.expanduser().resolve(strict=True)
    vault_path = vault_path.expanduser().resolve(strict=True)
    output_path = output_path.expanduser().absolute()
    if not db_path.is_file():
        raise BackupError(f"database is not a regular file: {db_path}")
    if not vault_path.is_dir():
        raise BackupError(f"vault is not a directory: {vault_path}")
    if output_path.exists():
        raise BackupError(f"backup destination already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="maths-phys-backup-") as temp_name:
        temp = Path(temp_name)
        snapshot = temp / "study.sqlite3"
        # Hold SQLite's writer reservation while taking the DB snapshot and copying
        # the matching vault/assets. An Atlas apply either finishes before this lock
        # (so both sides are included) or waits until after the backup snapshot.
        lock_db = sqlite3.connect(db_path, timeout=30)
        try:
            lock_db.execute("BEGIN IMMEDIATE")
            source_db = sqlite3.connect(db_path, timeout=30)
            target_db = sqlite3.connect(snapshot)
            try:
                source_db.backup(target_db, pages=128, sleep=0.05)
            finally:
                target_db.close()
                source_db.close()

            _reject_applying_atlas_operations(snapshot)
            vault_files, vault_dirs = _vault_tree(vault_path)
            registered_pdfs, pdf_assets, protection_schemes = _registered_assets(snapshot)
            staged_assets = temp / "consistent-copy"
            staged_assets.mkdir()
            payloads: list[tuple[str, Path]] = [("database/study.sqlite3", snapshot)]
            for member, live_path in vault_files + pdf_assets:
                staged_path = staged_assets / Path(*PurePosixPath(member).parts)
                staged_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(live_path, staged_path)
                payloads.append((member, staged_path))

            key_path = Path(str(db_path) + ".solution.key")
            key_member = None
            protection = {"schemes": sorted(protection_schemes)}
            if key_path.is_file():
                key_member = "database/study.sqlite3.solution.key"
                staged_key = staged_assets / key_member
                staged_key.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(key_path, staged_key)
                payloads.append((key_member, staged_key))
                protection["fernet_key"] = "included in the backup archive; protect the archive as a secret"
            elif "fernet" in protection_schemes:
                raise BackupError("the database contains Fernet-protected solutions but its .solution.key file is missing")
            if "dpapi" in protection_schemes or os.name == "nt":
                protection["dpapi_recovery"] = "Windows DPAPI data requires the same Windows user profile"
            if not protection_schemes and not key_member:
                protection["schemes"] = ["no protected solution material present"]
        finally:
            lock_db.rollback()
            lock_db.close()

        file_entries = []
        for member, path in payloads:
            file_entries.append({"path": member, "size": path.stat().st_size, "sha256": sha256_file(path)})
        manifest = {
            "format": FORMAT,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "database_member": "database/study.sqlite3",
            "vault_member": "vault/",
            "registered_pdfs": registered_pdfs,
            "solution_protection": protection,
            "files": file_entries,
            "directories": [f"vault/{name}" for name in vault_dirs],
        }
        archive_created = False
        try:
            with zipfile.ZipFile(output_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive_created = True
                for directory in manifest["directories"]:
                    archive.writestr(directory.rstrip("/") + "/", b"")
                for member, path in payloads:
                    archive.write(path, member)
                archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        except Exception:
            if archive_created and output_path.exists():
                output_path.unlink()
            raise
    return {"backup": str(output_path.resolve()), "files": len(file_entries),
            "registered_pdfs": len(registered_pdfs), "solution_protection": protection}


def _validate_archive(archive: zipfile.ZipFile) -> tuple[dict, dict[str, zipfile.ZipInfo]]:
    infos = archive.infolist()
    names: dict[str, zipfile.ZipInfo] = {}
    for info in infos:
        name = info.filename.rstrip("/") if info.is_dir() else info.filename
        if name == MANIFEST:
            if name in names:
                raise BackupError("archive contains a duplicate manifest")
            names[name] = info
            continue
        safe = _safe_archive_path(name)
        if safe in names:
            raise BackupError(f"archive contains a duplicate member: {safe}")
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise BackupError(f"archive contains a symbolic link: {safe}")
        if info.flag_bits & 1:
            raise BackupError("encrypted ZIP members are not supported")
        names[safe] = info
    if MANIFEST not in names:
        raise BackupError("archive has no manifest.json")
    try:
        manifest = json.loads(archive.read(names[MANIFEST]).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, KeyError) as exc:
        raise BackupError("manifest.json is invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise BackupError("unsupported or malformed backup manifest")
    files = manifest.get("files")
    directories = manifest.get("directories", [])
    if not isinstance(files, list) or not isinstance(directories, list):
        raise BackupError("manifest file/directory lists are invalid")
    expected_files = {}
    for entry in files:
        if not isinstance(entry, dict):
            raise BackupError("manifest file entries must be objects")
        member = _safe_archive_path(entry.get("path"))
        if member in expected_files:
            raise BackupError(f"manifest contains duplicate path: {member}")
        expected_files[member] = entry
    expected_dirs = {_safe_archive_path(item) for item in directories}
    if len(expected_dirs) != len(directories):
        raise BackupError("manifest contains duplicate directories")
    if not isinstance(manifest.get("registered_pdfs", []), list):
        raise BackupError("manifest registered_pdfs must be a list")
    actual_members = set(names) - {MANIFEST}
    expected_members = set(expected_files) | expected_dirs
    if actual_members != expected_members:
        raise BackupError("archive members do not match the manifest")
    for member, entry in expected_files.items():
        info = names[member]
        digest = hashlib.sha256(archive.read(info)).hexdigest()
        if digest != entry.get("sha256") or info.file_size != entry.get("size"):
            raise BackupError(f"backup integrity check failed: {member}")
    db_member = manifest.get("database_member")
    if db_member != "database/study.sqlite3" or db_member not in expected_files:
        raise BackupError("manifest database member is missing or invalid")
    if manifest.get("vault_member") != "vault/":
        raise BackupError("manifest vault member is invalid")
    for item in manifest.get("registered_pdfs", []):
        if not isinstance(item, dict) or not isinstance(item.get("source_id"), str):
            raise BackupError("manifest registered PDF entry is invalid")
        member = _safe_archive_path(item.get("archive_path"))
        if not member.startswith(f"assets/pdfs/{item['source_id']}/") or member not in expected_files:
            raise BackupError("manifest registered PDF member is missing or invalid")
    return manifest, names


def _rebind_pdf_paths(database_path: Path, root: Path, final_root: Path,
                      registered_pdfs: list[dict]) -> None:
    db = sqlite3.connect(database_path)
    try:
        for item in registered_pdfs:
            source_id = item.get("source_id")
            member = _safe_archive_path(item.get("archive_path"))
            staged_file = (root / Path(*PurePosixPath(member).parts)).resolve(strict=True)
            restored_file = (final_root / Path(*PurePosixPath(member).parts)).resolve()
            try:
                staged_file.relative_to(root.resolve(strict=True))
                restored_file.relative_to(final_root.resolve())
            except ValueError as exc:
                raise BackupError(f"registered PDF path escapes restore root: {member}") from exc
            if sha256_file(staged_file) != item.get("sha256"):
                raise BackupError(f"registered PDF asset hash mismatch: {member}")
            row = db.execute("SELECT metadata FROM sources WHERE id=?", (source_id,)).fetchone()
            if not row:
                raise BackupError(f"registered PDF references missing source {source_id}")
            metadata = json.loads(row[0] or "{}")
            local = metadata.get("local_file")
            if not isinstance(local, dict) or local.get("sha256") not in (None, item.get("sha256")):
                raise BackupError(f"registered PDF metadata does not match archive for source {source_id}")
            local["path"] = str(restored_file)
            local["sha256"] = item["sha256"]
            db.execute("UPDATE sources SET metadata=? WHERE id=?",
                       (json.dumps(metadata, ensure_ascii=False, sort_keys=True), source_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def restore_backup(backup_path: Path, destination: Path) -> dict:
    backup_path = backup_path.expanduser().resolve(strict=True)
    destination = destination.expanduser().absolute()
    if not backup_path.is_file():
        raise BackupError(f"backup is not a regular file: {backup_path}")
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir():
            raise BackupError(f"restore destination must be a new empty directory: {destination}")
        if any(destination.iterdir()):
            raise BackupError(f"restore destination is not empty: {destination}")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(backup_path, "r") as archive:
        manifest, names = _validate_archive(archive)
        with tempfile.TemporaryDirectory(prefix="maths-phys-restore-", dir=parent) as stage_name:
            stage = Path(stage_name)
            for directory in manifest.get("directories", []):
                relative = _safe_archive_path(directory)
                (stage / Path(*PurePosixPath(relative).parts)).mkdir(parents=True, exist_ok=True)
            for member, info in names.items():
                if member == MANIFEST or info.is_dir():
                    continue
                relative = _safe_archive_path(member)
                target = stage / Path(*PurePosixPath(relative).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as src, target.open("xb") as dst:
                    shutil.copyfileobj(src, dst)
            database_path = stage / Path(*PurePosixPath(manifest["database_member"]).parts)
            if not database_path.is_file():
                raise BackupError("restored database is missing")
            # Store startup rolls back applying journals using absolute paths from the
            # original machine. Refuse such a snapshot rather than risk writing there.
            _reject_applying_atlas_operations(database_path)
            _rebind_pdf_paths(database_path, stage, destination, manifest.get("registered_pdfs", []))
            if destination.exists():
                # The destination was confirmed empty; remove only that empty directory for atomic rename.
                destination.rmdir()
            os.replace(stage, destination)
    return {"restored_to": str(destination.resolve()),
            "database": str((destination / Path(*PurePosixPath(manifest["database_member"]).parts)).resolve()),
            "vault": str((destination / "vault").resolve()),
            "registered_pdfs": len(manifest.get("registered_pdfs", [])),
            "solution_protection": manifest.get("solution_protection", {})}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup", help="create a consistent backup archive")
    backup.add_argument("--db", type=Path, required=True)
    backup.add_argument("--vault", type=Path, required=True)
    backup.add_argument("--output", type=Path, required=True)
    restore = sub.add_parser("restore", help="restore to a new empty directory")
    restore.add_argument("--backup", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "backup":
            result = create_backup(args.db, args.vault, args.output)
        else:
            result = restore_backup(args.backup, args.destination)
    except (BackupError, OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
        print(f"backup/restore failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
