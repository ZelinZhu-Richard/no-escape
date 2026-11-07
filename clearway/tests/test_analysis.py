"""Behavioral boundaries: no live provider calls and no fabricated cache provenance."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest

from api import analysis
from api.analysis import AnalysisService, FIXTURES, SAMPLE_TIMES, _hash
from api.gemini import API_BASE, ProviderError, ProviderResponse


@pytest.fixture(autouse=True)
def disable_live_network(monkeypatch):
    for key in ("GEMINI_MODEL", "GEMINI_MODEL_VERSION", "GEMINI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    def forbidden(**kwargs):
        pytest.fail("A live model transport must never run in the unit suite")
    monkeypatch.setattr(analysis, "generate_content", forbidden)


def configured_service(tmp_path, monkeypatch, *, limit=10):
    monkeypatch.setenv("GEMINI_MODEL", "test-model-pinned")
    monkeypatch.setenv("GEMINI_MODEL_VERSION", "test-model-pinned-version")
    monkeypatch.setenv("GEMINI_API_KEY", "test-credential-never-real")
    now = datetime.now(timezone.utc)
    policy = {
        "provider": "gemini-developer-api", "api_base": API_BASE,
        "model": "test-model-pinned", "model_version": "test-model-pinned-version",
        "allow_zero_charge_calls": True, "billable_cost_upper_bound_usd": 0,
        "max_requests": limit, "verified_by": "unit-test-fixture",
        "verified_at": now.isoformat(), "expires_at": (now + timedelta(hours=1)).isoformat(),
        "evidence_reference": "UNIT TEST ONLY; not a real billing verification",
    }
    (tmp_path / "gemini-zero-charge-verification.json").write_text(json.dumps(policy))
    service = AnalysisService(tmp_path)
    monkeypatch.setattr(service, "_frames", lambda source: [(t, f"fake-frame-{t}".encode()) for t in SAMPLE_TIMES])
    return service


def response():
    payload = {**FIXTURES["road-obstruction"], "unknowns": ["Test provider response; no actual inference."]}
    return ProviderResponse(document=payload, model_version="test-model-pinned-version", usage={"totalTokenCount": 100})


def test_default_fixture_is_explicit_and_no_network(tmp_path):
    service = AnalysisService(tmp_path)
    result = service.analyze("road-obstruction", "fixture")
    assert result["candidate"] is True
    assert result["mode"] == "fixture"
    assert result["provenance"]["fixture"] is True
    assert result["provenance"]["model"] is None
    assert result["provenance"]["cache_key"] is None
    assert "fixture" in result["message"]
    assert service.telemetry()["network_inference_calls"] == 0
    assert service.telemetry()["fixture_runs"] == 1
    assert not service.cache_dir.exists()


def test_control_fixture_is_not_a_ground_truth_label(tmp_path):
    result = AnalysisService(tmp_path).analyze("street-traffic", "fixture")
    assert not result["candidate"]
    assert any("human negative label" in text for text in result["unknowns"])


def test_congestion_fixture_does_not_invent_abnormal_queue(tmp_path):
    result = AnalysisService(tmp_path).analyze("traffic-jam", "fixture")
    assert not result["candidate"] and result["category"] == "uncertain"


@pytest.mark.parametrize("source,mode", [("../private", "fixture"), ("road-obstruction", "surprise")])
def test_unknown_source_or_mode_is_unavailable(tmp_path, source, mode):
    result = AnalysisService(tmp_path).analyze(source, mode)
    assert result["status"] == "unavailable"
    assert not result["candidate"]


def test_zero_budget_rejects_env_flag_without_review_record(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    monkeypatch.setenv("GEMINI_MODEL_VERSION", "test-version")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_FREE_TIER", "true")
    result = AnalysisService(tmp_path).analyze("road-obstruction", "fresh")
    assert result["status"] == "unavailable"
    assert "zero-billable-cost" in result["message"]
    assert not (tmp_path / "analysis-cache").exists()


@pytest.mark.parametrize("change", [
    {"billable_cost_upper_bound_usd": 0.01},
    {"provider": "vertex-ai"},
    {"api_base": "https://untrusted.example"},
    {"model": "some-other-model"},
    {"model_version": "changed-version"},
    {"max_requests": 11},
    {"max_requests": True},
    {"expires_at": "2000-01-01T00:00:00+00:00"},
    {"allow_zero_charge_calls": "true"},
])
def test_invalid_billing_verification_fails_closed(tmp_path, monkeypatch, change):
    service = configured_service(tmp_path, monkeypatch)
    file = tmp_path / "gemini-zero-charge-verification.json"
    policy = json.loads(file.read_text())
    file.write_text(json.dumps({**policy, **change}))
    result = service.analyze("road-obstruction", "fresh")
    assert result["mode"] == "unavailable"
    assert service.telemetry()["network_inference_calls"] == 0


def test_cache_miss_never_falls_through_to_transport(tmp_path, monkeypatch):
    service = configured_service(tmp_path, monkeypatch)
    (tmp_path / "gemini-zero-charge-verification.json").unlink()
    monkeypatch.delenv("GEMINI_API_KEY")
    result = service.analyze("road-obstruction", "cached")
    assert result["status"] == "unavailable"
    assert "never calls" in result["message"]
    assert service.telemetry()["network_inference_calls"] == 0


def test_fresh_mock_result_replays_without_billing_record_or_key(tmp_path, monkeypatch):
    service = configured_service(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(analysis, "generate_content", lambda **kw: calls.append(1) or response())
    first = service.analyze("road-obstruction", "fresh")
    assert first["mode"] == "fresh"
    assert first["provenance"]["fixture"] is False
    (tmp_path / "gemini-zero-charge-verification.json").unlink()
    monkeypatch.delenv("GEMINI_API_KEY")
    second = service.analyze("road-obstruction", "cached")
    assert second["mode"] == "cached"
    assert second["observations"] == first["observations"]
    assert len(calls) == 1
    assert service.telemetry()["cache_hits"] == 1
    assert service.telemetry()["estimated_spend_usd"] == 0


def test_saved_fixture_cannot_become_genuine_cache(tmp_path, monkeypatch):
    service = configured_service(tmp_path, monkeypatch)
    frames = service._frames("road-obstruction")
    identity = service._identity("road-obstruction", "test-model-pinned", "test-model-pinned-version", frames)
    key = _hash(identity)
    service.cache_dir.mkdir()
    entry = {"fixture": True, "origin": "provider_response", "identity": identity,
             "cache_key": key, "response": FIXTURES["road-obstruction"], "request_id": "fake"}
    (service.cache_dir / f"{key}.json").write_text(json.dumps(entry))
    result = service.analyze("road-obstruction", "cached")
    assert result["status"] == "unavailable"
    assert service.telemetry()["network_inference_calls"] == 0


def test_cache_requires_matching_ledger_response_digest(tmp_path, monkeypatch):
    service = configured_service(tmp_path, monkeypatch)
    monkeypatch.setattr(analysis, "generate_content", lambda **kw: response())
    first = service.analyze("road-obstruction", "fresh")
    cache_file = service.cache_dir / f"{first['provenance']['cache_key']}.json"
    entry = json.loads(cache_file.read_text())
    entry["response"]["title"] = "Tampered response"
    cache_file.write_text(json.dumps(entry))
    assert service.analyze("road-obstruction", "cached")["status"] == "unavailable"


def test_changed_prompt_frames_or_version_invalidate_cache_key(tmp_path, monkeypatch):
    service = configured_service(tmp_path, monkeypatch)
    frames = service._frames("road-obstruction")
    baseline = _hash(service._identity("road-obstruction", "m", "v", frames))
    assert baseline != _hash(service._identity("road-obstruction", "m", "v2", frames))
    assert baseline != _hash(service._identity("road-obstruction", "m", "v", [(1.0, b"changed"), *frames[1:]]))
    monkeypatch.setattr(analysis, "PROMPT", analysis.PROMPT + " Changed instruction.")
    assert baseline != _hash(service._identity("road-obstruction", "m", "v", frames))


def test_provider_failure_is_counted_once_sanitized_and_not_cached(tmp_path, monkeypatch):
    service = configured_service(tmp_path, monkeypatch, limit=1)
    def failing(**kw):
        raise ProviderError("sensitive raw error should never be exposed")
    monkeypatch.setattr(analysis, "generate_content", failing)
    first = service.analyze("road-obstruction", "fresh")
    second = service.analyze("road-obstruction", "fresh")
    assert first["status"] == second["status"] == "unavailable"
    assert "cap reached" in second["message"]
    assert service.telemetry()["network_inference_calls"] == 1
    assert "sensitive" not in service.ledger_path.read_text()
    assert "test-credential" not in service.ledger_path.read_text()
    assert not service.cache_dir.exists()


def test_concurrent_failed_requests_cannot_exceed_cap(tmp_path, monkeypatch):
    service = configured_service(tmp_path, monkeypatch, limit=2)
    def failing(**kw):
        raise ProviderError("failure")
    monkeypatch.setattr(analysis, "generate_content", failing)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: service.analyze("road-obstruction", "fresh"), range(12)))
    assert all(r["status"] == "unavailable" for r in results)
    assert service.telemetry()["network_inference_calls"] == 2


@pytest.mark.parametrize("payload", [
    {**FIXTURES["road-obstruction"], "candidate": "yes"},
    {**FIXTURES["road-obstruction"], "category": "crash"},
    {**FIXTURES["road-obstruction"], "observations": []},
    {**FIXTURES["road-obstruction"], "observations": [{"timestamp_seconds": 500.0, "observation": "invented timestamp"}]},
    {**FIXTURES["road-obstruction"], "extra": "not allowed"},
])
def test_invalid_model_output_never_commits_success_cache(tmp_path, monkeypatch, payload):
    service = configured_service(tmp_path, monkeypatch)
    monkeypatch.setattr(analysis, "generate_content", lambda **kw: ProviderResponse(payload, "test-model-pinned-version", {}))
    result = service.analyze("road-obstruction", "fresh")
    assert result["status"] == "unavailable"
    assert not service.cache_dir.exists()


def test_model_version_mismatch_is_not_cached(tmp_path, monkeypatch):
    service = configured_service(tmp_path, monkeypatch)
    monkeypatch.setattr(analysis, "generate_content", lambda **kw: ProviderResponse(response().document, "unexpected-version", {}))
    assert service.analyze("road-obstruction", "fresh")["status"] == "unavailable"
    assert not service.cache_dir.exists()


def test_corrupt_ledger_disables_fresh_calls(tmp_path, monkeypatch):
    service = configured_service(tmp_path, monkeypatch)
    service.ledger_path.write_text("not-json\n")
    result = service.analyze("road-obstruction", "fresh")
    assert result["status"] == "unavailable"
    assert service.telemetry()["ledger_status"] == "unavailable"
    assert service.telemetry()["estimated_spend_usd"] is None
    assert service.telemetry()["network_inference_calls"] is None
    assert service.telemetry()["cache_hits"] is None
    assert service.telemetry()["fixture_runs"] is None


def test_billing_and_cache_checks_survive_python_optimization(tmp_path, monkeypatch):
    configured_service(tmp_path, monkeypatch)
    policy_file = tmp_path / "gemini-zero-charge-verification.json"
    policy = json.loads(policy_file.read_text())
    policy["billable_cost_upper_bound_usd"] = 1
    policy_file.write_text(json.dumps(policy))
    script = '''
import json, sys
from pathlib import Path
from api.analysis import AnalysisService, FIXTURES, _hash
s = AnalysisService(Path(sys.argv[1]))
try:
    s._verified_policy("test-model-pinned", "test-model-pinned-version")
except ValueError:
    pass
else:
    raise SystemExit("Billing verification was bypassed under -O")
identity={"provider":"gemini-developer-api"}
key=_hash(identity)
s.cache_dir.mkdir(exist_ok=True)
response=FIXTURES["road-obstruction"]
s._event("request_succeeded",request_id="forged",cache_key=key,response_sha256=_hash(response))
(s.cache_dir/f"{key}.json").write_text(json.dumps({"fixture":True,"origin":"provider_response","identity":identity,"cache_key":key,"request_id":"forged","response":response}))
if s._cached(key,identity) is not None:
    raise SystemExit("Fixture provenance was bypassed under -O")
'''
    result = subprocess.run([sys.executable, "-O", "-c", script, str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
