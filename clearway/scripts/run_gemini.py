#!/usr/bin/env python3
"""Analyze one licensed clip, then verify a zero-network genuine cache replay.

Uses the same adapter, budget authorization, frame sampler, cache, and ledger as
the application. Never writes evaluation labels or confirms an incident.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.analysis import AnalysisService, SOURCE_FILES  # noqa: E402
from api.configuration import load_local_environment  # noqa: E402
from api.gemini import ProviderError, get_model_metadata  # noqa: E402


def validate_source(service: AnalysisService, source_id: str, *, cached_only: bool = False) -> dict:
    """Return a report without substituting expected labels for model output."""
    before = service.telemetry()
    if before["network_inference_calls"] is None:
        return {"status": "blocked", "message": "The local spend ledger is unavailable."}
    metadata = None
    if not cached_only:
        readiness = service.readiness()
        if not readiness["ready"]:
            return {"status": "blocked", "message": readiness["message"], "readiness": readiness}
        try:
            metadata = get_model_metadata(api_key=os.environ.get("GEMINI_API_KEY", ""), model=os.environ.get("GEMINI_MODEL", ""))
        except ProviderError as error:
            return {"status": "blocked", "message": error.safe_message,
                    "access_check": "failed; no generation request made"}
    result = service.analyze(source_id, "cached" if cached_only else "fresh")
    if result["status"] != "complete" or result["mode"] not in {"fresh", "cached"} or result["provenance"]["fixture"] is not False:
        return {"status": "unavailable", "source_id": source_id, "message": result["message"],
                "telemetry": service.telemetry()}
    after_analysis = service.telemetry()
    cached = service.analyze(source_id, "cached")
    after_cache = service.telemetry()
    cache_ok = (
        cached["mode"] == "cached" and cached["status"] == "complete"
        and cached["provenance"]["fixture"] is False
        and cached["provenance"]["cache_key"] == result["provenance"]["cache_key"]
        and cached["observations"] == result["observations"]
        and after_cache["network_inference_calls"] == after_analysis["network_inference_calls"]
        and after_cache["network_inference_calls"] is not None
    )
    return {
        "status": "passed" if cache_ok else "cache_verification_failed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source_id": source_id, "source_mode": "recorded_replay",
        "model_access_check": metadata, "result": result,
        "cache_replay_verified": cache_ok,
        "generation_calls_this_run": after_cache["network_inference_calls"] - before["network_inference_calls"] if after_cache["network_inference_calls"] is not None else None,
        "telemetry": after_cache,
        "review": "Actual model output; inspect it against the clip. This is not a human label, accuracy measurement, or confirmed incident.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=tuple(SOURCE_FILES), default="road-obstruction")
    parser.add_argument("--cached-only", action="store_true", help="No credential check or inference network calls; require an existing genuine cache.")
    args = parser.parse_args()
    load_local_environment()
    service = AnalysisService(Path(os.environ.get("CLEARWAY_DATA_DIR", ROOT / "data")))
    report = validate_source(service, args.source, cached_only=args.cached_only)
    if report["status"] in {"passed", "cache_verification_failed"}:
        directory = service.data_dir / "inference"
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=directory, suffix=".tmp", delete=False) as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
            temporary = Path(stream.name)
        temporary.replace(directory / f"{args.source}-validation.json")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
