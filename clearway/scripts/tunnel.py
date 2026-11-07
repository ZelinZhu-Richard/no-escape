#!/usr/bin/env python3
"""Explicit, temporary Cloudflare Quick Tunnel for the read-only responder only.

Foreground owner with atomic heartbeat/status and cooperative stop. No personal
Cloudflare configuration or credentials are read; no operator port is exposed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import queue
import re
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "clearway"))
RUNTIME = ROOT / "clearway/data/runtime"
VERSION = "2026.10.7"
ARCHIVE_URL = f"https://github.com/cloudflare/cloudflared/releases/download/{VERSION}/cloudflared-darwin-arm64.tgz"
ARCHIVE_SHA256 = "3586ccf397e98e5f437e60e7c307ca6ac463e110580503af8bb8e6f9ebf831bd"
BINARY_SHA256 = "2136431d5eb467bf447d2ee514b713e192719b143aec1d9e09bf7dc290d5bb12"
ORIGIN = "http://127.0.0.1:8001"
URL_PATTERN = re.compile(r"https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com(?![a-z0-9.-])")
EMPTY_ID = "00000000-0000-0000-0000-000000000000"


class TunnelError(RuntimeError):
    """Safe messages only; never raw subprocess or remote error bodies."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_local_environment() -> None:
    try:
        from api.configuration import load_local_environment as load
    except ModuleNotFoundError:
        raise TunnelError("Use clearway/.venv/bin/python clearway/scripts/tunnel.py after make setup.") from None
    load()


def runtime_directory() -> Path:
    """Use the same private settings and data directory as the operator."""
    load_local_environment()
    data = Path(os.environ.get("CLEARWAY_DATA_DIR", ROOT / "clearway/data")).resolve()
    return data / "runtime"


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.chmod(0o600)
    temporary.replace(path)


def read_state(runtime: Path = RUNTIME) -> dict:
    try:
        path = runtime / "tunnel.json"
        if path.is_symlink() or path.stat().st_size > 8192:
            return {"active": False, "status": "invalid_state"}
        state = json.loads(path.read_text())
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(state["updated_at"])).total_seconds()
        if not 0 <= age <= 15:
            return {**state, "active": False, "status": "stale"}
        return state
    except (OSError, ValueError, KeyError, TypeError):
        return {"active": False, "status": "stopped"}


def prepare_binary() -> Path:
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise TunnelError("Automatic verified setup supports this expo's macOS ARM64 machine only; see TUNNEL.md for other systems.")
    target = ROOT / f".local/bin/cloudflared-{VERSION}"
    if target.is_file() and not target.is_symlink():
        if hashlib.sha256(target.read_bytes()).hexdigest() == BINARY_SHA256:
            return target
        raise TunnelError("Local cloudflared binary checksum differs from the verified release. Stop and inspect it.")
    try:
        request = Request(ARCHIVE_URL, headers={"User-Agent": "Clearway-expo-setup"})
        with urlopen(request, timeout=45) as response:
            archive = response.read(30_000_001)
        if len(archive) > 30_000_000 or hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA256:
            raise TunnelError("Cloudflare release archive failed its pinned checksum/size check.")
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            members = [m for m in bundle.getmembers() if m.name in ("cloudflared", "./cloudflared") and m.isfile()]
            if len(members) != 1 or members[0].size > 80_000_000:
                raise TunnelError("Cloudflare archive did not contain the expected executable.")
            binary = bundle.extractfile(members[0]).read()
        if hashlib.sha256(binary).hexdigest() != BINARY_SHA256:
            raise TunnelError("Cloudflare executable failed its pinned checksum check.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("wb", dir=target.parent, delete=False) as stream:
            stream.write(binary)
            temporary = Path(stream.name)
        temporary.chmod(0o755)
        temporary.replace(target)
        return target
    except (OSError, URLError, tarfile.TarError):
        raise TunnelError("Could not download or install the verified Cloudflare binary.") from None


def check_responder() -> None:
    """Fail closed if port 8001 exposes an operator or lacks the responder UI."""
    try:
        for path in ("/api/state", "/api/config", "/api/labels", "/api/sources"):
            try:
                with urlopen(ORIGIN + path, timeout=3):
                    raise TunnelError("Port 8001 exposes an operator route; refusing to create a tunnel.")
            except HTTPError as error:
                if error.code != 404:
                    raise TunnelError("Read-only responder boundary check did not return the required 404.") from None
        with urlopen(f"{ORIGIN}/respond/{EMPTY_ID}/{EMPTY_ID}", timeout=3) as response:
            if response.status != 200 or response.headers.get_content_type() != "text/html":
                raise TunnelError("Responder frontend is not ready on port 8001.")
    except (OSError, URLError):
        raise TunnelError("Responder is unavailable on 127.0.0.1:8001; run make serve first.") from None


def cloudflared_command(binary: Path, config: Path) -> list[str]:
    return [str(binary), "tunnel", "--config", str(config), "--no-autoupdate",
            "--url", ORIGIN, "--metrics", "127.0.0.1:0", "--protocol", "http2",
            "--loglevel", "info", "--grace-period", "3s"]


def clean_environment() -> dict[str, str]:
    # Do not inherit provider keys or named-tunnel configuration overrides.
    keep = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR")
    return {key: os.environ[key] for key in keep if key in os.environ}


def stop(runtime: Path = RUNTIME) -> dict:
    state = read_state(runtime)
    session = state.get("session_id")
    if not session or state.get("status") in ("stopped", "stale", "failed", "invalid_state"):
        return {"active": False, "status": "not_running"}
    atomic_json(runtime / "tunnel-stop.json", {"session_id": session})
    # Hide the QR immediately; the owner then terminates and waits for its child.
    atomic_json(runtime / "tunnel.json", {**state, "active": False, "status": "stopping", "updated_at": now()})
    return {"active": False, "status": "stop_requested"}


def start(runtime: Path = RUNTIME) -> int:
    runtime.mkdir(parents=True, exist_ok=True)
    lock = (runtime / "tunnel.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise TunnelError("A managed tunnel is already running. Use status or stop; do not start a second one.") from None
    process = None
    stopped = False
    status = "starting"
    session = str(uuid4())
    public_url = None
    registered = False
    lines: queue.Queue[str] = queue.Queue()
    log_path = runtime / "tunnel-events.jsonl"

    def event(name: str, **details):
        record = {"time": now(), "event": name, "session_id": session, **details}
        with log_path.open("a") as stream:
            stream.write(json.dumps(record) + "\n")

    def publish():
        atomic_json(runtime / "tunnel.json", {
            "public_base_url": public_url, "active": status == "ready",
            "status": status, "pid": process.pid if process else None, "owner_pid": os.getpid(),
            "session_id": session, "origin_url": ORIGIN, "updated_at": now(),
        })

    def request_stop(_signum=None, _frame=None):
        nonlocal stopped, status
        stopped = True
        status = "stopping"

    handled_signals = (signal.SIGINT, signal.SIGTERM) + ((signal.SIGHUP,) if hasattr(signal, "SIGHUP") else ())
    previous = {sig: signal.signal(sig, request_stop) for sig in handled_signals}
    try:
        check_responder()
        binary = prepare_binary()
        config = runtime / "cloudflared-quick.yml"
        config.write_text("# Deliberately empty: never load personal or named-tunnel configuration.\n")
        config.chmod(0o600)
        process = subprocess.Popen(cloudflared_command(binary, config), cwd=runtime,
            env=clean_environment(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, start_new_session=True)
        publish()
        event("started", child_pid=process.pid)

        def drain():
            for line in process.stdout:
                lines.put(line)
        threading.Thread(target=drain, daemon=True).start()
        began = time.monotonic()
        heartbeat = 0.0
        while not stopped:
            try:
                request = json.loads((runtime / "tunnel-stop.json").read_text())
                if request.get("session_id") == session:
                    request_stop()
                    break
            except (OSError, ValueError, TypeError):
                pass
            if process.poll() is not None:
                event("process_exit", code=process.returncode)
                status = "failed"
                raise TunnelError(f"Cloudflare tunnel exited with code {process.returncode}; no public connection is active.")
            try:
                while True:
                    line = lines.get_nowait()
                    match = URL_PATTERN.search(line)
                    if match and public_url is None:
                        public_url = match.group()
                        event("origin_assigned")
                    if "Registered tunnel connection" in line:
                        registered = True
                    if "Unregistered tunnel connection" in line or "failed to serve tunnel connection" in line.lower():
                        registered = False
                        status = "reconnecting"
                        event("connection_interrupted")
            except queue.Empty:
                pass
            if public_url and registered and status != "ready":
                status = "ready"
                event("ready")
                print(json.dumps({"status": status, "public_base_url": public_url, "origin_url": ORIGIN}), flush=True)
                print("Keep this terminal running. Ctrl+C or tunnel.py stop closes this temporary public connection.", flush=True)
            if time.monotonic() - began > 60 and status == "starting":
                status = "failed"
                raise TunnelError("Cloudflare did not establish the temporary connection within 60 seconds; tunnel stopped.")
            if time.monotonic() >= heartbeat:
                publish()
                heartbeat = time.monotonic() + 3
            time.sleep(0.2)
        return 0
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=7)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        status = "failed" if status == "failed" else "stopped"
        publish()
        event("stopped")
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "start", "status", "stop"))
    args = parser.parse_args()
    try:
        if args.action == "install":
            print(json.dumps({"status": "verified", "version": VERSION, "path": str(prepare_binary())}))
        else:
            runtime = runtime_directory()
            if args.action == "start":
                return start(runtime)
            if args.action == "status":
                print(json.dumps(read_state(runtime), indent=2))
            else:
                print(json.dumps(stop(runtime), indent=2))
        return 0
    except TunnelError as error:
        print(json.dumps({"status": "failed", "message": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
