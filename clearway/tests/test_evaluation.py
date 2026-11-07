import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("evaluate", Path(__file__).resolve().parents[1] / "scripts/evaluate.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def label(id, category="normal", source="same-scene"):
    return {"id": id, "label": category, "source_id": source, "reviewer": "Test-only reviewer"}


def prediction(id, category="normal", mode="cached", **kwargs):
    return {"label_id": id, "predicted_category": category, "analysis_mode": mode, "status": "complete", "provenance_id": "test-only-provenance", **kwargs}


def test_no_human_labels_never_produces_accuracy():
    result = module.evaluate([], [prediction("one", "road_obstruction")])
    assert result["status"] == "awaiting_labels"
    assert result["metrics"] is None


def test_fixtures_and_missing_predictions_are_not_accuracy_results():
    result = module.evaluate([label("one"), label("two")], [prediction("one", mode="fixture")])
    assert result["status"] == "awaiting_genuine_predictions"
    assert result["evaluated_window_count"] == 0
    assert result["excluded"]["fixture"] == 1
    assert result["excluded"]["missing_or_unavailable"] == 1


def test_counts_keep_scene_denominator_and_unknown_cost():
    result = module.evaluate(
        [label("one"), label("two"), label("three", "road_obstruction")],
        [prediction("one", "road_obstruction", latency_ms=10, cost_usd=0), prediction("two", latency_ms=20), prediction("three", "road_obstruction", gate_passed=False, gate_mode="local", gate_provenance_id="test-gate")],
    )
    assert result["scene_count"] == 1
    assert result["metrics"]["normal_false_alerts"] == {"numerator": 1, "denominator": 2}
    assert result["gate_metrics"]["known_positive_gate_coverage"] == {"numerator": 0, "denominator": 1, "scenes": 1}
    assert result["metrics"]["latency"]["cached"] == {"n": 2, "median_ms": 15, "max_ms": 20}
    assert result["metrics"]["billable_cost"]["mean_per_window_usd"] is None


def test_duplicate_or_unprovenanced_predictions_rejected():
    with pytest.raises(ValueError, match="Duplicate prediction"):
        module.evaluate([label("one")], [prediction("one"), prediction("one")])
    invalid = prediction("one")
    invalid.pop("provenance_id")
    with pytest.raises(ValueError, match="provenance"):
        module.evaluate([label("one")], [invalid])


def test_gate_miss_without_vlm_call_still_counts():
    passed = prediction("one", "road_obstruction", gate_passed=True, gate_mode="local", gate_provenance_id="test-gate")
    skipped = {"label_id": "two", "status": "skipped", "analysis_mode": "unavailable", "gate_passed": False, "gate_mode": "local", "gate_provenance_id": "test-gate"}
    result = module.evaluate([label("one", "road_obstruction"), label("two", "road_obstruction")], [passed, skipped])
    assert result["evaluated_window_count"] == 1
    assert result["gate_metrics"]["known_positive_gate_coverage"] == {"numerator": 1, "denominator": 2, "scenes": 1}
    assert result["gate_metrics"]["hypothetical_gate_requests_avoided"] == {"numerator": 1, "denominator": 2}


def test_fixture_gates_and_nonfinite_costs_not_reported_as_measurements():
    pred = prediction("one", gate_passed=False, gate_mode="fixture", gate_provenance_id="test-fixture")
    result = module.evaluate([label("one")], [pred])
    assert result["gate_metrics"]["hypothetical_gate_requests_avoided"]["denominator"] == 0
    with pytest.raises(ValueError, match="finite"):
        module.evaluate([label("one")], [prediction("one", cost_usd=float("nan"))])
