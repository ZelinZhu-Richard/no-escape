import importlib.util
import json
from pathlib import Path

import pytest

from api.configuration import ConfigurationError, DEFAULT_MODEL, load_local_environment


def test_private_file_preserves_process_values_and_ignores_unrelated_settings(tmp_path, capsys):
    path = tmp_path / ".env"
    path.write_text("GEMINI_API_KEY=private-test-value\nGEMINI_MODEL=from-file\nPATH=do-not-replace\n")
    env = {"GEMINI_MODEL": "from-process", "PATH": "original"}
    assert load_local_environment(path, environ=env) is True
    assert env == {"GEMINI_API_KEY": "private-test-value", "GEMINI_MODEL": "from-process", "GEMINI_MODEL_VERSION": DEFAULT_MODEL, "PATH": "original"}
    assert capsys.readouterr() == ("", "")


def test_shell_expressions_and_variable_references_are_literal(tmp_path):
    sentinel = tmp_path / "should-not-exist"
    path = tmp_path / ".env"
    value = "${EXAMPLE_SECRET}$(touch " + str(sentinel) + ")`whoami`"
    path.write_text("GEMINI_API_KEY='" + value + "'\n")
    env = {"EXAMPLE_SECRET": "not-expanded"}
    load_local_environment(path, environ=env)
    assert env["GEMINI_API_KEY"] == value
    assert not sentinel.exists()


def test_missing_file_and_empty_process_value_are_preserved(tmp_path):
    env = {"GEMINI_API_KEY": ""}
    assert load_local_environment(tmp_path / "absent", environ=env) is False
    path = tmp_path / ".env"
    path.write_text("GEMINI_API_KEY=file-value\nGEMINI_MODEL\n")
    load_local_environment(path, environ=env)
    assert env == {"GEMINI_API_KEY": "", "GEMINI_MODEL": DEFAULT_MODEL, "GEMINI_MODEL_VERSION": DEFAULT_MODEL}


def test_key_only_file_receives_selected_model_defaults(tmp_path):
    path = tmp_path / ".env"
    path.write_text("GEMINI_API_KEY=private-test-value\n")
    env = {}
    load_local_environment(path, environ=env)
    assert env["GEMINI_MODEL"] == DEFAULT_MODEL
    assert env["GEMINI_MODEL_VERSION"] == DEFAULT_MODEL


def test_invalid_private_file_errors_do_not_echo_contents(tmp_path, capsys):
    path = tmp_path / ".env"
    path.write_bytes(b"GEMINI_API_KEY=secret-test-value\xff")
    with pytest.raises(ConfigurationError, match="Could not read private configuration") as error:
        load_local_environment(path, environ={})
    assert "secret-test-value" not in str(error.value)
    assert capsys.readouterr() == ("", "")


def test_symlink_is_not_followed(tmp_path):
    source = tmp_path / "source"
    source.write_text("GEMINI_API_KEY=test-only\n")
    link = tmp_path / ".env"
    link.symlink_to(source)
    with pytest.raises(ConfigurationError, match="regular local"):
        load_local_environment(link, environ={})


def test_offline_doctor_never_returns_configuration_values(tmp_path, monkeypatch):
    module_path = Path(__file__).resolve().parents[1] / "scripts/check_gemini.py"
    spec = importlib.util.spec_from_file_location("check_gemini", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.shutil, "which", lambda name: "/test/bin/" + name)
    footage = tmp_path / "data/footage"
    footage.mkdir(parents=True)
    (footage / "road-obstruction-demo.mp4").write_bytes(b"test-only")
    secret = "private-test-value"
    report = module.offline_report(root=tmp_path, environ={
        "GEMINI_API_KEY": secret,
        "GEMINI_MODEL": "test-model",
        "GEMINI_MODEL_VERSION": "test-version",
    })
    assert report["status"] == "offline_prerequisites_ready"
    assert report["network_requests"] == 0
    assert report["billing_or_model_access_verified"] is False
    assert report["paid_authorization_record"] == {"present": False, "dates_current": False}
    assert report["fresh_policy_blocker"]
    assert secret not in json.dumps(report)
    assert "test-model" not in json.dumps(report)


def test_doctor_checks_policy_dates_without_claiming_authorization(tmp_path):
    from datetime import datetime, timedelta, timezone
    module_path = Path(__file__).resolve().parents[1] / "scripts/check_gemini.py"
    spec = importlib.util.spec_from_file_location("check_gemini_dates", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    now = datetime.now(timezone.utc)
    path = tmp_path / "gemini-budget-authorization.json"
    # Intentionally incomplete policy: the doctor must only report its dates.
    path.write_text(json.dumps({"approved_at": (now - timedelta(minutes=1)).isoformat(), "expires_at": (now + timedelta(hours=1)).isoformat()}))
    assert module.policy_presence(tmp_path) == {"present": True, "dates_current": True}
    path.write_text(json.dumps({"approved_at": (now - timedelta(hours=2)).isoformat(), "expires_at": (now - timedelta(hours=1)).isoformat()}))
    assert module.policy_presence(tmp_path) == {"present": True, "dates_current": False}
