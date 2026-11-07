"""Smoke-run orchestration must not invent observations or bypass the policy."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("gemini_smoke", Path(__file__).resolve().parents[1] / "scripts/run_gemini.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class Service:
    def __init__(self, *, ready=True, candidate=True, cached_miss=False, cache_calls_network=False):
        self.calls = 0
        self.ready = ready
        self.candidate = candidate
        self.cached_miss = cached_miss
        self.cache_calls_network = cache_calls_network

    def telemetry(self):
        return {"network_inference_calls": self.calls}

    def readiness(self):
        return {"ready": self.ready, "message": "Test policy is not ready"}

    def analyze(self, source_id, mode):
        if mode == "fresh" or self.cache_calls_network:
            self.calls += 1
        if self.cached_miss:
            return {"mode": "unavailable", "status": "unavailable", "message": "No genuine cache"}
        return {"mode": mode, "status": "complete", "candidate": self.candidate,
                "observations": [{"timestamp_seconds": 4, "observation": "Test observation"}],
                "provenance": {"fixture": False, "cache_key": "unit-test-only"}}


@pytest.fixture(autouse=True)
def no_real_metadata(monkeypatch):
    monkeypatch.setattr(smoke, "get_model_metadata", lambda **kwargs: {"test_only": True})


def test_unready_policy_blocks_even_metadata_probe(monkeypatch):
    monkeypatch.setattr(smoke, "get_model_metadata", lambda **kwargs: pytest.fail("Should not contact provider"))
    service = Service(ready=False)
    assert smoke.validate_source(service, "road-obstruction")["status"] == "blocked"
    assert service.calls == 0


def test_fresh_then_cache_preserves_result_and_one_generation():
    report = smoke.validate_source(Service(), "road-obstruction")
    assert report["status"] == "passed"
    assert report["generation_calls_this_run"] == 1
    assert report["cache_replay_verified"] is True
    assert report["result"]["observations"][0]["observation"] == "Test observation"


def test_cached_only_never_probes_credential_or_creates_missing_result(monkeypatch):
    monkeypatch.setattr(smoke, "get_model_metadata", lambda **kwargs: pytest.fail("No network in frozen mode"))
    service = Service(ready=False, cached_miss=True)
    assert smoke.validate_source(service, "road-obstruction", cached_only=True)["status"] == "unavailable"
    assert service.calls == 0


def test_cache_network_call_fails_validation():
    report = smoke.validate_source(Service(cache_calls_network=True), "road-obstruction")
    assert report["status"] == "cache_verification_failed"


def test_valid_no_candidate_is_not_replaced_with_expected_obstruction():
    report = smoke.validate_source(Service(candidate=False), "road-obstruction")
    assert report["status"] == "passed"
    assert report["result"]["candidate"] is False
