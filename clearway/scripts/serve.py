#!/usr/bin/env python3
"""Run the local operator and isolated read-only responder; never create a tunnel."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python = root / ".venv/bin/python"
    if not python.is_file():
        print("Run `make setup` from the repository root first.", file=sys.stderr)
        return 1
    if not (root / "web/dist/index.html").is_file():
        print("Frontend is not built. Run `make build` first.", file=sys.stderr)
        return 1
    processes: list[subprocess.Popen] = []
    stopped = False

    def stop(_signum=None, _frame=None):
        nonlocal stopped
        stopped = True
        for process in processes:
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        for app, port in [("api.app:app", "8000"), ("api.app:responder_app", "8001")]:
            processes.append(subprocess.Popen([str(python), "-m", "uvicorn", app, "--host", "127.0.0.1", "--port", port], cwd=root, env=os.environ.copy()))
        print("Clearway operator: http://127.0.0.1:8000", flush=True)
        print("Read-only responder: http://127.0.0.1:8001 (no public tunnel)", flush=True)
        print("Private settings load from clearway/.env; restart after changing them.", flush=True)
        print("Press Ctrl+C to stop both services.", flush=True)
        while not stopped:
            for process in processes:
                result = process.poll()
                if result is not None:
                    print(f"A local service exited ({result}); stopping both.", file=sys.stderr)
                    stop()
                    return result or 1
            time.sleep(0.25)
        return 0
    finally:
        stop()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
