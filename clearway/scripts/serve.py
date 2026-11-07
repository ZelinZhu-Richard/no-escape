#!/usr/bin/env python3
"""Run the expo services without reload; record exits and health transitions."""
from __future__ import annotations

import os
from datetime import datetime, timezone
import json
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


SERVICES = (("operator", "api.app:app", 8000), ("responder", "api.app:responder_app", 8001))
EMPTY_ID = "00000000-0000-0000-0000-000000000000"


def command(python: Path, app: str, port: int) -> list[str]:
    # Expo serving is intentionally separate from a Vite development server.
    return [str(python), "-m", "uvicorn", app, "--host", "127.0.0.1",
            "--port", str(port), "--no-access-log"]


def safe_line(line: str) -> str:
    """Defensive redaction; requests/headers and environment are never logged."""
    line = re.sub(r"(?i)(authorization\s*[:=]\s*)[^\n]+", r"\1[redacted]", line)
    line = re.sub(r"(?i)((?:api[_-]?key|authorization|access[_-]?token|password|secret)\s*[:=]\s*)[^\s,;]+", r"\1[redacted]", line)
    line = re.sub(r"AIza[A-Za-z0-9_-]{20,}", "[redacted-key]", line)
    return re.sub(r"(https?://[^\s?]+)\?[^\s]+", r"\1?[redacted-query]", line).rstrip()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def health(name: str, port: int) -> bool:
    path = "/api/health" if name == "operator" else f"/respond/{EMPTY_ID}/{EMPTY_ID}"
    try:
        with urlopen(f"http://127.0.0.1:{port}{path}", timeout=2) as response:
            if response.status != 200:
                return False
            if name == "operator":
                return json.loads(response.read(1000)).get("status") == "ok"
            return response.headers.get_content_type() == "text/html"
    except (OSError, URLError, HTTPError, ValueError):
        return False


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
    readers: list[threading.Thread] = []
    log_dir = root / "data/runtime/logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    session = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{os.getpid()}"
    log_lock = threading.Lock()
    launcher_log = log_dir / f"{session}-launcher.log"
    stopped = False

    def report(message: str):
        line = f"{timestamp()} {message}"
        print(line, flush=True)
        with log_lock, launcher_log.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    def drain(process, name: str):
        path = log_dir / f"{session}-{name}.log"
        with path.open("a", encoding="utf-8") as stream:
            for line in process.stdout:
                stream.write(f"{timestamp()} {safe_line(line)}\n")
                stream.flush()

    def stop(_signum=None, _frame=None):
        nonlocal stopped
        stopped = True
        for process in processes:
            if process.poll() is None:
                process.terminate()

    handled_signals = (signal.SIGINT, signal.SIGTERM) + ((signal.SIGHUP,) if hasattr(signal, "SIGHUP") else ())
    previous_handlers = {sig: signal.signal(sig, stop) for sig in handled_signals}
    try:
        for name, app, port in SERVICES:
            process = subprocess.Popen(command(python, app, port), cwd=root,
                env=os.environ.copy(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            processes.append(process)
            reader = threading.Thread(target=drain, args=(process, name), daemon=True)
            readers.append(reader)
            reader.start()
            report(f"Started {name} PID {process.pid}; reload disabled.")
        report("Clearway operator: http://127.0.0.1:8000")
        report("Read-only responder: http://127.0.0.1:8001; tunnel starts only by explicit command.")
        report(f"Service logs: {log_dir}/{session}-*.log")
        report("Private settings load from clearway/.env; restart after changing them. Ctrl+C stops both services.")
        last_health: dict[str, bool] = {}
        next_health = time.monotonic() + 1
        while not stopped:
            for (name, _, _), process in zip(SERVICES, processes):
                result = process.poll()
                if result is not None:
                    report(f"{name} exited with code {result}; stopping both. No automatic restart. Inspect its service log.")
                    stop()
                    return result or 1
            if time.monotonic() >= next_health:
                for name, _, port in SERVICES:
                    ready = health(name, port)
                    if last_health.get(name) != ready:
                        report(f"{name} HTTP health: {'ready' if ready else 'unavailable'}.")
                        last_health[name] = ready
                next_health = time.monotonic() + 5
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
        for reader in readers:
            reader.join(timeout=1)
        report("Expo services stopped.")
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
