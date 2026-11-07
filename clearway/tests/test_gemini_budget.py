"""Paid smoke-run limits use synthetic transports and isolated ledgers only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json

import pytest

from api import analysis
from api.analysis import AnalysisService, FIXTURES, SAMPLE_TIMES, _hash
from api.gemini import API_BASE, ProviderError, ProviderResponse
from api.gemini_budget import PAID_MODEL, estimate_usage, spending


def setup_paid(tmp_path, monkeypatch, **changes):
    monkeypatch.setenv("GEMINI_MODEL", PAID_MODEL)
    monkeypatch.setenv("GEMINI_MODEL_VERSION", PAID_MODEL)
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key-unit-test-only")
    now = datetime.now(timezone.utc)
    policy = {
        "mode": "paid", "provider": "gemini-developer-api", "api_base": API_BASE,
        "model": PAID_MODEL, "model_version": PAID_MODEL,
        "max_billable_usd": 5, "max_requests": 5,
        "approved_by": "test fixture, not a person", "approval_reference": "UNIT TEST ONLY",
        "approved_at": now.isoformat(), "expires_at": (now + timedelta(hours=1)).isoformat(),
        **changes,
    }
    (tmp_path / "gemini-budget-authorization.json").write_text(json.dumps(policy))
    service = AnalysisService(tmp_path)
    monkeypatch.setattr(service, "_frames", lambda source: [(t, b"synthetic-jpeg") for t in SAMPLE_TIMES])
    def forbidden(**kwargs):
        pytest.fail("No real provider transport is allowed in this suite")
    monkeypatch.setattr(analysis, "generate_content", forbidden)
    return service


def answer(usage=None):
    return ProviderResponse(
        document={**FIXTURES["road-obstruction"], "unknowns": ["Synthetic transport result only."]},
        model_version=PAID_MODEL,
        usage=usage if usage is not None else {
            "promptTokenCount": 450, "candidatesTokenCount": 100,
            "thoughtsTokenCount": 25, "totalTokenCount": 575,
        },
    )


def test_success_prices_input_output_and_thinking_without_total_double_count(tmp_path, monkeypatch):
    service = setup_paid(tmp_path, monkeypatch)
    monkeypatch.setattr(analysis, "generate_content", lambda **kwargs: answer())
    result = service.analyze("road-obstruction", "fresh")
    assert result["mode"] == "fresh"
    telemetry = service.telemetry()
    assert telemetry["network_inference_calls"] == 1
    assert telemetry["reserved_spend_usd"] == 0.5
    assert telemetry["estimated_billable_cost_usd"] == pytest.approx(0.0004475)
    assert telemetry["estimated_spend_usd"] == pytest.approx(0.0004475)
    assert telemetry["unknown_cost_requests"] == 0
    cached = service.analyze("road-obstruction", "cached")
    assert cached["mode"] == "cached" and cached["provenance"]["fixture"] is False
    assert service.telemetry()["network_inference_calls"] == 1


def test_missing_usage_retains_unknown_cost_and_reservation(tmp_path, monkeypatch):
    service = setup_paid(tmp_path, monkeypatch)
    monkeypatch.setattr(analysis, "generate_content", lambda **kwargs: answer({}))
    result = service.analyze("road-obstruction", "fresh")
    assert result["mode"] == "fresh"
    telemetry = service.telemetry()
    assert telemetry["estimated_billable_cost_usd"] is None
    assert telemetry["estimated_spend_usd"] == telemetry["reserved_spend_usd"] == 0.5
    assert telemetry["unknown_cost_requests"] == 1
    (tmp_path / "gemini-budget-authorization.json").unlink()
    monkeypatch.delenv("GEMINI_API_KEY")
    assert service.analyze("road-obstruction", "cached")["mode"] == "cached"


def test_concurrent_failures_never_exceed_five_and_renewal_does_not_reset_cap(tmp_path, monkeypatch):
    service = setup_paid(tmp_path, monkeypatch)
    calls = []
    def fail(**kwargs):
        calls.append(1)
        raise ProviderError("Do not expose raw transport text")
    monkeypatch.setattr(analysis, "generate_content", fail)
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: service.analyze("road-obstruction", "fresh"), range(18)))
    assert all(result["mode"] == "unavailable" for result in results)
    assert len(calls) == 5
    telemetry = service.telemetry()
    assert telemetry["reserved_spend_usd"] == telemetry["estimated_spend_usd"] == 2.5
    assert telemetry["estimated_billable_cost_usd"] is None
    assert telemetry["unknown_cost_requests"] == 5
    refreshed = setup_paid(tmp_path, monkeypatch)
    assert "cap reached" in refreshed.analyze("road-obstruction", "fresh")["message"]
    assert refreshed.readiness()["remaining_requests"] == 0
    assert "raw transport" not in service.ledger_path.read_text()


def test_dollar_cap_stops_before_a_second_reservation(tmp_path, monkeypatch):
    service = setup_paid(tmp_path, monkeypatch, max_billable_usd=0.75)
    def fail(**kwargs):
        raise ProviderError("synthetic failure")
    monkeypatch.setattr(analysis, "generate_content", fail)
    service.analyze("road-obstruction", "fresh")
    assert "dollar cap" in service.analyze("road-obstruction", "fresh")["message"]
    assert service.telemetry()["network_inference_calls"] == 1
    assert service.readiness()["ready"] is False


def test_separate_service_instances_share_the_same_request_ceiling(tmp_path, monkeypatch):
    first = setup_paid(tmp_path, monkeypatch)
    second = setup_paid(tmp_path, monkeypatch)
    calls = []
    def fail(**kwargs):
        calls.append(1)
        raise ProviderError("synthetic failure")
    monkeypatch.setattr(analysis, "generate_content", fail)
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda i: (first if i % 2 else second).analyze("road-obstruction", "fresh"), range(15)))
    assert all(result["mode"] == "unavailable" for result in results)
    assert len(calls) == 5
    assert first.telemetry()["reserved_spend_usd"] == second.telemetry()["reserved_spend_usd"] == 2.5


@pytest.mark.parametrize("change", [
    {"max_billable_usd": 5.01}, {"max_billable_usd": float("nan")},
    {"max_billable_usd": float("inf")}, {"max_billable_usd": True},
    {"max_requests": 6}, {"max_requests": True}, {"max_requests": 0},
    {"model": "gemini-other-model"}, {"model_version": "different-version"},
    {"provider": "vertex-ai"}, {"api_base": "https://untrusted.example"},
    {"expires_at": "2000-01-01T00:00:00+00:00"},
    {"approved_by": ""}, {"approval_reference": ""}, {"mode": "free"},
])
def test_invalid_paid_authorization_never_calls_provider(tmp_path, monkeypatch, change):
    service = setup_paid(tmp_path, monkeypatch, **change)
    assert service.analyze("road-obstruction", "fresh")["mode"] == "unavailable"
    assert service.telemetry()["network_inference_calls"] == 0
    assert not service.readiness()["ready"]


def test_partial_reservation_counts_even_without_started_event(tmp_path, monkeypatch):
    service = setup_paid(tmp_path, monkeypatch)
    policy = service._verified_policy(PAID_MODEL, PAID_MODEL)
    identity = service._identity("road-obstruction", PAID_MODEL, PAID_MODEL, service._frames("road-obstruction"))
    for _ in range(5):
        service._reserve(policy, _hash(identity), identity)
    assert service.analyze("road-obstruction", "fresh")["mode"] == "unavailable"
    assert service.telemetry()["network_inference_calls"] == 0
    assert service.telemetry()["reserved_spend_usd"] == 2.5


def test_readiness_is_offline_and_never_touches_footage(tmp_path, monkeypatch):
    service = setup_paid(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "_frames", lambda source: pytest.fail("Readiness must not extract frames"))
    ready = service.readiness()
    assert ready["ready"] and ready["max_billable_usd"] == 5
    assert ready["remaining_requests"] == ready["max_requests"] == 5
    assert "not-a-real-key" not in json.dumps(ready)
    monkeypatch.delenv("GEMINI_API_KEY")
    assert not service.readiness()["ready"]
    assert service.readiness()["max_billable_usd"] == 5


def test_generation_settings_change_invalidates_cache_identity(tmp_path, monkeypatch):
    service = setup_paid(tmp_path, monkeypatch)
    frames = service._frames("road-obstruction")
    before = _hash(service._identity("road-obstruction", PAID_MODEL, PAID_MODEL, frames))
    monkeypatch.setattr(analysis, "generation_config", lambda model: {"changed": True})
    after = _hash(service._identity("road-obstruction", PAID_MODEL, PAID_MODEL, frames))
    assert before != after


@pytest.mark.parametrize("usage", [
    {}, {"totalTokenCount": 1},
    {"promptTokenCount": 1, "candidatesTokenCount": 1, "totalTokenCount": 1},
    {"promptTokenCount": 1, "candidatesTokenCount": 1, "thoughtsTokenCount": -1, "totalTokenCount": 1},
    {"promptTokenCount": True, "candidatesTokenCount": 0, "totalTokenCount": 1},
    {"promptTokenCount": 2_000_000, "candidatesTokenCount": 1, "totalTokenCount": 2_000_001},
])
def test_incomplete_or_impossible_usage_is_not_reported_as_zero(usage):
    assert estimate_usage(usage) is None


def test_corrupt_paid_reservation_cannot_be_reported_as_zero():
    with pytest.raises(ValueError):
        spending([{"event": "request_reserved", "request_id": "test", "provider": "gemini-developer-api", "billing_mode": "paid"}])
