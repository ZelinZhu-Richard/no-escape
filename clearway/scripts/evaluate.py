#!/usr/bin/env python3
"""Summarize submitted human labels and explicit prediction records.

No labels or predictions are generated. A label file is an array or {labels:[]};
predictions are an array or {predictions:[]}. See docs/EVALUATION.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import urllib.request
from pathlib import Path


def evaluate(labels: list[dict], predictions: list[dict]) -> dict:
    report: dict = {
        "status": "awaiting_labels" if not labels else "awaiting_predictions",
        "label_count": len(labels),
        "scene_count": len({item["source_id"] for item in labels}),
        "labeler_count": len({item["reviewer"] for item in labels}),
        "prediction_count": len(predictions),
        "natural_incident_recall": "not measurable on natural data; no natural-incident sample established",
        "scope": "Development/demo windows; adjacent windows are not independent incidents.",
        "metrics": None,
    }
    if not labels:
        return report
    by_label: dict[str, dict] = {}
    for prediction in predictions:
        key = prediction["label_id"]
        if key in by_label:
            raise ValueError(f"Duplicate prediction for label {key}; select one frozen evaluation output.")
        by_label[key] = prediction
    if len({item["id"] for item in labels}) != len(labels):
        raise ValueError("Duplicate label IDs")
    if set(by_label) - {item["id"] for item in labels}:
        raise ValueError("Predictions reference unknown label IDs")
    # A gate can suppress the VLM call entirely. Count its decisions before
    # filtering for complete model predictions so suppressed positives remain.
    gate_windows = []
    for label in labels:
        pred = by_label.get(label["id"], {})
        if (label["label"] != "uncertain" and type(pred.get("gate_passed")) is bool
                and pred.get("gate_mode") == "local" and pred.get("gate_provenance_id")):
            gate_windows.append((label, pred))
    positive_gates = [(label, pred) for label, pred in gate_windows if label["label"] == "road_obstruction"]
    report["gate_metrics"] = {
        "known_positive_gate_coverage": {"numerator": sum(pred["gate_passed"] for _, pred in positive_gates), "denominator": len(positive_gates), "scenes": len({label["source_id"] for label, _ in positive_gates})},
        "hypothetical_gate_requests_avoided": {"numerator": sum(not pred["gate_passed"] for _, pred in gate_windows), "denominator": len(gate_windows)},
    }
    eligible = []
    omitted = {"fixture": 0, "missing_or_unavailable": 0, "uncertain_label": 0}
    for label in labels:
        if label["label"] not in {"normal", "road_obstruction", "queue", "uncertain"}:
            raise ValueError("Unknown human label category")
        if not label.get("reviewer", "").strip():
            raise ValueError("Every submitted human label requires a reviewer")
        if label["label"] == "uncertain":
            omitted["uncertain_label"] += 1
            continue
        pred = by_label.get(label["id"])
        if not pred or pred.get("status") != "complete":
            omitted["missing_or_unavailable"] += 1
            continue
        if pred.get("analysis_mode") == "fixture":
            omitted["fixture"] += 1
            continue
        if pred.get("analysis_mode") not in {"fresh", "cached"} or not pred.get("provenance_id"):
            raise ValueError("Real accuracy requires fresh/cached prediction provenance; fixtures must be marked fixture")
        if pred.get("predicted_category") not in {"normal", "road_obstruction", "queue", "uncertain"}:
            raise ValueError("Unknown predicted category")
        eligible.append((label, pred))
    report["excluded"] = omitted
    report["evaluated_window_count"] = len(eligible)
    report["evaluated_scene_count"] = len({label["source_id"] for label, _ in eligible})
    if not eligible:
        report["status"] = "development_gate_results" if gate_windows else ("awaiting_genuine_predictions" if predictions else "awaiting_predictions")
        return report
    normal = [(label, pred) for label, pred in eligible if label["label"] == "normal"]
    positive = [(label, pred) for label, pred in eligible if label["label"] == "road_obstruction"]
    latency = {}
    for mode in ["fresh", "cached"]:
        values = [float(pred["latency_ms"]) for _, pred in eligible if pred["analysis_mode"] == mode and pred.get("latency_ms") is not None]
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("Latency must be finite and nonnegative")
        latency[mode] = {"n": len(values), "median_ms": statistics.median(values) if values else None, "max_ms": max(values) if values else None}
    costs = [pred.get("cost_usd") for _, pred in eligible]
    known_costs = [float(value) for value in costs if value is not None]
    if any(not math.isfinite(value) or value < 0 for value in known_costs):
        raise ValueError("Costs must be finite and nonnegative")
    report["status"] = "development_results"
    report["metrics"] = {
        "normal_false_alerts": {"numerator": sum(pred["predicted_category"] in {"road_obstruction", "queue"} for _, pred in normal), "denominator": len(normal)},
        "positive_obstruction_detections": {"numerator": sum(pred["predicted_category"] == "road_obstruction" for _, pred in positive), "denominator": len(positive), "scenes": len({label["source_id"] for label, _ in positive})},
        "uncertain_model_windows": sum(pred["predicted_category"] == "uncertain" for _, pred in eligible),
        "latency": latency,
        "billable_cost": {"known_sum_usd": sum(known_costs), "known_cost_windows": len(known_costs), "unknown_cost_windows": len(costs) - len(known_costs), "mean_per_window_usd": sum(known_costs) / len(costs) if len(known_costs) == len(costs) else None},
    }
    return report


def read_records(path: Path, key: str) -> list[dict]:
    value = json.loads(path.read_text())
    return value[key] if isinstance(value, dict) else value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data/evaluation/report.json")
    args = parser.parse_args()
    if args.labels:
        labels = read_records(args.labels, "labels")
    else:
        with urllib.request.urlopen(args.base_url.rstrip("/") + "/api/labels", timeout=10) as response:
            labels = json.load(response)["labels"]
    predictions = read_records(args.predictions, "predictions") if args.predictions else []
    report = evaluate(labels, predictions)
    report["input_sha256"] = hashlib.sha256(json.dumps({"labels": labels, "predictions": predictions}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
