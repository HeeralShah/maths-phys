# Getting started

## Start the local study app

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe scripts/run_local.py --open-browser
```

The launcher starts the API at `http://127.0.0.1:8000` and the study UI at `http://127.0.0.1:5173`, using the persistent database at `data/local/study.sqlite3`. Press **Ctrl+C** in the launcher terminal to stop both servers. Logs go to `data/local/logs/api.log` and `data/local/logs/ui.log`.

The launcher expects the repository's Python environment, Node.js, and the installed frontend dependencies under `frontend/node_modules`. It refuses to start if either local port is already in use. Opening the browser is optional; omit `--open-browser` to keep the UI closed.

The imported edition and problems below are already in this machine's local database. Starting the app does not prepare a source, call an agent, or create a study check.

## Prepared study material

### B6La: Sturm-Liouville problem

The current local source record is **B6La — Constrained variation of functionals, §7.1 Sturm-Liouville problem** (source ID `9f6253ab-c98f-4c72-9bd9-8d91af96d508` in this machine's database). It refers to `C:\Users\heera\Dropbox\Academic Resources\B6La.pdf`. The imported passage is PDF page 30, printed page 29. The current edition has a prerequisite refresher and three ordered study units covering the first variation, the lowest-eigenvalue quotient, and direct variation of that quotient.

The source's displayed first-variation formula prints a minus sign on its endpoint term. The edition preserves that printed expression and adds a separate explanation that integration by parts yields a plus sign; fixed-end variations vanish at either sign. The eigenvalue quotient discussion also calls out the homogeneous endpoint condition needed to remove the later boundary term.

The page contains visible blue checks, yellow and green highlights, and handwritten notes. Imported source marks are historical and have no known original dates. They are not current learner checks. The app's current mark meanings are green for unclear/error/foreign reference, yellow for explanation, blue for understood, and purple for exercise.

### Classical Dynamics I: Coriolis exercises

The current local source record is **Classical Dynamics I — Lagrangian Formalism, Coriolis questions** (source ID `c3faa659-a3dc-4adf-894b-533ebc6768d7` in this machine's database), referring to `C:\Users\heera\Dropbox\Academic Resources\ClassicalDynamicsI.pdf`. Three prompts are imported verbatim from the lecture notes:

- PDF page 6, printed page 15: the contrast between Coriolis deflection of a projected particle and anti-clockwise hurricane circulation.
- PDF page 7, printed page 16: estimating the Coriolis force, its effect on a plughole, and the direction of a spinning CD.
- PDF page 7, printed page 16: where a dropped ball lands from a tower at the equator.

Each problem has orientation, small hint, strong hint, partial solution, and full solution assistance. Open a problem and reveal only the level you want. Revealing assistance is a local read; it does not create a worker job. Solutions are protected in the local database using this Windows user's DPAPI profile.

The source PDFs remain in the user's Academic Resources folder. The source records store their paths and SHA-256 fingerprints; PDF registration did not copy or commit the originals.

## Checks, signoff, and agent work

Read and assess a unit before recording a current check. Imported marks are historical and do not establish that a unit is understood. Use the app's explicit study controls for any current mark; do not mark material understood just to advance the workflow.

The agent worker is not configured. A signoff may record a request, but it cannot produce a completed Atlas synthesis until a real worker is configured. Do not treat a queued or incomplete job as finished material. An existing, reviewed synthesis plan can be applied through the explicit plan workflow; no plan is fabricated from the imported pages.

## Back up and restore

Create a backup at a destination you choose:

```powershell
.\.venv\Scripts\python.exe scripts/backup_restore.py backup `
  --db data/local/study.sqlite3 `
  --vault vault `
  --output "D:\Study Backups\maths-phys-2026-11-01.zip"
```

The backup uses SQLite's online backup API and contains the database snapshot, vault files, registered PDF assets, a SHA-256 manifest, and a fallback solution key when one is used. It refuses to overwrite an existing output file. Keep the backup archive somewhere private and protected. The ZIP file itself is **not encrypted**; if it includes a Fernet solution key, that key is inside the archive.

Restore only into a new or empty directory:

```powershell
.\.venv\Scripts\python.exe scripts/backup_restore.py restore `
  --backup "D:\Study Backups\maths-phys-2026-11-01.zip" `
  --destination "D:\Study Restores\maths-phys"
```

Restore verifies every archived file against the manifest and rejects path traversal, symbolic links, and non-empty destinations. Registered PDF paths in the restored database are rebound to the PDF copies inside the restore directory. Windows DPAPI-protected solutions can be recovered only under the same Windows user profile; restoring the database under a different profile does not decrypt them.

The backup checks can be run with:

```powershell
.\.venv\Scripts\python.exe -m unittest scripts.test_backup -v
```

### Backup consistency

The backup holds a SQLite writer reservation while staging the database, vault and registered PDF files; app writes wait during staging. Backup and restore refuse an unfinished Atlas recovery journal. Pause direct external vault editors during backup so the file snapshot remains consistent. Backup ZIPs are private archives, not encrypted containers.
