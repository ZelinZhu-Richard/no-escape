"""Expo process boundaries and shutdown state; no real public connection."""
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import threading
import time

import pytest


def load_script(name):
    spec = spec_from_file_location(name, Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tunnel = load_script("tunnel")
serve = load_script("serve")


def test_expo_processes_never_reload_or_expose_operator():
    for _, app, port in serve.SERVICES:
        cmd = serve.command(Path("/venv/python"), app, port)
        assert "--reload" not in cmd
        assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
        assert "--no-access-log" in cmd
    cmd = tunnel.cloudflared_command(Path("/verified/cloudflared"), Path("/empty/config"))
    assert cmd[cmd.index("--url") + 1] == "http://127.0.0.1:8001"
    assert "8000" not in " ".join(cmd)
    assert "--no-autoupdate" in cmd
    assert cmd[cmd.index("--metrics") + 1] == "127.0.0.1:0"


def test_tunnel_process_does_not_receive_provider_or_tunnel_secrets(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "private")
    monkeypatch.setenv("TUNNEL_TOKEN", "private")
    monkeypatch.setenv("TUNNEL_URL", "http://127.0.0.1:8000")
    environment = tunnel.clean_environment()
    assert not {"GEMINI_API_KEY", "TUNNEL_TOKEN", "TUNNEL_URL"} & environment.keys()


def test_runtime_matches_configured_data_directory(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(tunnel, "load_local_environment", lambda: calls.append("loaded"))
    monkeypatch.setenv("CLEARWAY_DATA_DIR", str(tmp_path / "custom-data"))
    assert tunnel.runtime_directory() == tmp_path / "custom-data/runtime"
    assert calls == ["loaded"]


def test_runtime_defaults_without_reading_private_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(tunnel, "load_local_environment", lambda: None)
    monkeypatch.setattr(tunnel, "ROOT", tmp_path)
    monkeypatch.delenv("CLEARWAY_DATA_DIR", raising=False)
    assert tunnel.runtime_directory() == tmp_path / "clearway/data/runtime"


def test_stale_tunnel_never_reports_active(tmp_path):
    tunnel.atomic_json(tmp_path / "tunnel.json", {
        "active": True, "status": "ready", "public_base_url": "https://test.trycloudflare.com",
        "updated_at": (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat(),
    })
    assert tunnel.read_state(tmp_path)["active"] is False
    assert tunnel.read_state(tmp_path)["status"] == "stale"


def test_stop_hides_qr_immediately_and_addresses_only_owned_session(tmp_path):
    tunnel.atomic_json(tmp_path / "tunnel.json", {
        "active": True, "status": "ready", "session_id": "owned-session", "updated_at": tunnel.now(),
    })
    assert tunnel.stop(tmp_path)["status"] == "stop_requested"
    assert tunnel.read_state(tmp_path)["active"] is False
    assert json.loads((tmp_path / "tunnel-stop.json").read_text()) == {"session_id": "owned-session"}


def test_no_stop_signal_is_sent_for_unknown_or_stale_pid(tmp_path):
    assert tunnel.stop(tmp_path)["status"] == "not_running"
    assert not (tmp_path / "tunnel-stop.json").exists()


def test_checksums_refuse_modified_existing_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(tunnel, "ROOT", tmp_path)
    monkeypatch.setattr(tunnel.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(tunnel.platform, "machine", lambda: "arm64")
    binary = tmp_path / f".local/bin/cloudflared-{tunnel.VERSION}"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"unexpected binary")
    with pytest.raises(tunnel.TunnelError, match="checksum differs"):
        tunnel.prepare_binary()


def test_console_lines_redact_key_and_url_queries():
    assert "private-value" not in serve.safe_line("API_KEY=private-value")
    assert "private-value" not in serve.safe_line("https://example.com/?token=private-value")
    assert "AIza" not in serve.safe_line("AIza" + "a" * 35)
    assert "private-value" not in serve.safe_line("Authorization: Bearer private-value")


def test_foreground_tunnel_stops_owned_child_and_clears_active_state(tmp_path, monkeypatch):
    binary = tmp_path / "fake-cloudflared"
    binary.write_text(f"#!{sys.executable}\nimport time\nprint('https://unit-test.trycloudflare.com', flush=True)\nprint('Registered tunnel connection', flush=True)\ntime.sleep(30)\n")
    binary.chmod(0o755)
    monkeypatch.setattr(tunnel, "prepare_binary", lambda: binary)
    monkeypatch.setattr(tunnel, "check_responder", lambda: None)
    observed = {}

    def stop_when_ready():
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = tunnel.read_state(tmp_path)
            if state.get("active"):
                observed.update(state)
                tunnel.stop(tmp_path)
                return
            time.sleep(0.05)
        # Avoid a hanging test if the fake subprocess failed unexpectedly.
        state = tunnel.read_state(tmp_path)
        if state.get("session_id"):
            tunnel.stop(tmp_path)

    worker = threading.Thread(target=stop_when_ready)
    worker.start()
    assert tunnel.start(tmp_path) == 0
    worker.join(timeout=1)
    assert observed["public_base_url"] == "https://unit-test.trycloudflare.com"
    assert observed["origin_url"] == "http://127.0.0.1:8001"
    assert tunnel.read_state(tmp_path)["status"] == "stopped"
    assert tunnel.read_state(tmp_path)["active"] is False
    with pytest.raises(ProcessLookupError):
        os.kill(observed["pid"], 0)


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="POSIX terminal hangup")
def test_terminal_hangup_cleans_tunnel_and_runtime_state(tmp_path):
    binary = tmp_path / "fake-cloudflared"
    binary.write_text(f"#!{sys.executable}\nimport time\nprint('https://hangup-test.trycloudflare.com', flush=True)\nprint('Registered tunnel connection', flush=True)\ntime.sleep(30)\n")
    binary.chmod(0o755)
    module_path = Path(tunnel.__file__)
    runner = f"""
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
spec=spec_from_file_location('tunnel', {str(module_path)!r})
module=module_from_spec(spec); spec.loader.exec_module(module)
module.prepare_binary=lambda: Path({str(binary)!r})
module.check_responder=lambda: None
raise SystemExit(module.start(Path({str(tmp_path)!r})))
"""
    owner = subprocess.Popen([sys.executable, "-c", runner], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    child_pid = None
    try:
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            state = tunnel.read_state(tmp_path)
            child_pid = state.get("pid") or child_pid
            if state.get("active"):
                break
            assert owner.poll() is None
            time.sleep(0.05)
        assert state.get("active"), "Fake tunnel did not become ready"
        owner.send_signal(signal.SIGHUP)
        assert owner.wait(timeout=10) == 0
        assert tunnel.read_state(tmp_path)["active"] is False
        assert tunnel.read_state(tmp_path)["status"] == "stopped"
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
    finally:
        if owner.poll() is None:
            owner.terminate()
            owner.wait(timeout=10)
        # Regression failures must not leak the deliberately spawned fake child.
        if child_pid:
            try:
                os.kill(child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        owner.stderr.close()


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="POSIX terminal hangup")
def test_terminal_hangup_cleans_both_expo_services(tmp_path):
    root = tmp_path / "clearway"
    (root / ".venv/bin").mkdir(parents=True)
    (root / ".venv/bin/python").touch()
    (root / "web/dist").mkdir(parents=True)
    (root / "web/dist/index.html").write_text("test")
    runner = f"""
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import sys
spec=spec_from_file_location('serve', {str(Path(serve.__file__))!r})
module=module_from_spec(spec); spec.loader.exec_module(module)
module.__file__={str(root / 'scripts/serve.py')!r}
def command(python, app, port):
    code="import os,time; from pathlib import Path; Path(%r).write_text(str(os.getpid())); time.sleep(30)" % str(Path({str(tmp_path)!r}) / (str(port)+'.pid'))
    return [sys.executable, '-c', code]
module.command=command
module.health=lambda *_: True
raise SystemExit(module.main())
"""
    owner = subprocess.Popen([sys.executable, "-c", runner], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    children = []
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            children = [int(path.read_text()) for path in (tmp_path / "8000.pid", tmp_path / "8001.pid") if path.exists() and path.read_text()]
            if len(children) == 2:
                break
            assert owner.poll() is None
            time.sleep(0.05)
        assert len(children) == 2
        owner.send_signal(signal.SIGHUP)
        assert owner.wait(timeout=10) == 0
        for pid in children:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
    finally:
        if owner.poll() is None:
            owner.terminate()
            owner.wait(timeout=10)
        for pid in children:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        owner.stderr.close()
