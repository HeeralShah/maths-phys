"""Run the local API and frontend together, with logs written under data/local."""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def port_is_free(host: str, port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def wait_ready(proc: subprocess.Popen, url: str, timeout: float = 25) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.25)
    return False


def stop_process(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                       creationflags=CREATE_NO_WINDOW)
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "local" / "study.sqlite3")
    parser.add_argument("--api-host", default="127.0.0.1")
    parser.add_argument("--ui-host", default="127.0.0.1")
    parser.add_argument("--ui-port", type=int, default=5173)
    parser.add_argument("--open-browser", action="store_true", help="open the local study UI after startup")
    args = parser.parse_args()

    node = shutil.which("node")
    vite = ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    if not node or not vite.is_file():
        parser.error("Node.js and frontend/node_modules are required; run npm install in frontend first")
    api_port = 8000  # frontend/vite.config.ts proxies /api to this fixed local port.
    for host, port, label in ((args.api_host, api_port, "API"), (args.ui_host, args.ui_port, "UI")):
        if not port_is_free(host, port):
            parser.error(f"{label} address {host}:{port} is already in use")

    db_path = args.db.expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logs = ROOT / "data" / "local" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    api_log = (logs / "api.log").open("ab")
    ui_log = (logs / "ui.log").open("ab")
    api_url = f"http://{args.api_host}:{api_port}"
    ui_url = f"http://{args.ui_host}:{args.ui_port}"
    api_env = os.environ.copy()
    api_env["MATHSPHYS_DB"] = str(db_path)

    api = ui = None
    try:
        api = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app:app", "--host",
                                args.api_host, "--port", str(api_port)],
                               cwd=ROOT, env=api_env, stdin=subprocess.DEVNULL,
                               stdout=api_log, stderr=subprocess.STDOUT, creationflags=CREATE_NO_WINDOW)
        if not wait_ready(api, f"{api_url}/sources"):
            raise RuntimeError(f"API failed to start; see {logs / 'api.log'}")
        ui = subprocess.Popen([node, str(vite), "--host", args.ui_host, "--port", str(args.ui_port), "--strictPort"],
                              cwd=ROOT / "frontend", stdin=subprocess.DEVNULL,
                              stdout=ui_log, stderr=subprocess.STDOUT, creationflags=CREATE_NO_WINDOW)
        if not wait_ready(ui, ui_url):
            raise RuntimeError(f"frontend failed to start; see {logs / 'ui.log'}")
        print(f"Study UI: {ui_url}")
        print(f"Local API: {api_url}")
        print(f"Database: {db_path}")
        print(f"Logs: {logs}")
        if args.open_browser:
            webbrowser.open(ui_url)
        print("Press Ctrl+C to stop both local servers.")
        while api.poll() is None and ui.poll() is None:
            time.sleep(0.5)
        if api.poll() is not None:
            raise RuntimeError(f"API stopped; see {logs / 'api.log'}")
        raise RuntimeError(f"frontend stopped; see {logs / 'ui.log'}")
    except KeyboardInterrupt:
        print("Stopping local study app…")
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        stop_process(ui)
        stop_process(api)
        api_log.close()
        ui_log.close()


if __name__ == "__main__":
    raise SystemExit(main())
