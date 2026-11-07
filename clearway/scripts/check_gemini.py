#!/usr/bin/env python3
"""Check local Gemini prerequisites without calling a provider or printing keys.

Run from the repository root:
  clearway/.venv/bin/python clearway/scripts/check_gemini.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


def policy_presence(data: Path) -> dict:
    """Inspect only the local record's presence and dates, never account access."""
    path = data / "gemini-budget-authorization.json"
    if not path.exists():
        return {"present": False, "dates_current": False}
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 32_768:
            return {"present": True, "dates_current": False}
        document = json.loads(path.read_text())
        approved = datetime.fromisoformat(document["approved_at"])
        expires = datetime.fromisoformat(document["expires_at"])
        now = datetime.now(timezone.utc)
        current = bool(approved.tzinfo and expires.tzinfo and approved <= now < expires
                       and (expires - approved).total_seconds() <= 24 * 3600)
        return {"present": True, "dates_current": current}
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return {"present": True, "dates_current": False}


def offline_report(*, root: Path = ROOT, environ=None) -> dict:
    """Read presence/validity only; do not return any configuration values."""
    env = os.environ if environ is None else environ
    data = Path(env.get("CLEARWAY_DATA_DIR") or root / "data")
    checks = {
        "api_key_present": bool(env.get("GEMINI_API_KEY", "").strip()),
        "model_identifier_configured": bool(MODEL_PATTERN.fullmatch(env.get("GEMINI_MODEL", ""))),
        "model_version_configured": bool(MODEL_PATTERN.fullmatch(env.get("GEMINI_MODEL_VERSION", ""))),
        "obstruction_footage_present": (data / "footage/road-obstruction-demo.mp4").is_file(),
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "ffprobe_available": shutil.which("ffprobe") is not None,
    }
    policy = policy_presence(data)
    return {
        "status": "offline_prerequisites_ready" if all(checks.values()) else "configuration_incomplete",
        "checks": checks,
        "paid_authorization_record": policy,
        "fresh_policy_blocker": None if policy["present"] and policy["dates_current"] else "A current local budget authorization record is missing or its dates are invalid; fresh analysis remains blocked unless an eligible zero-charge policy is separately verified.",
        "network_requests": 0,
        "billing_or_model_access_verified": False,
        "note": "This offline check inspects configuration presence and policy dates only. AnalysisService validates all policy terms; account/model access and billing are not verified here. No Gemini call is made.",
    }


def main() -> int:
    try:
        from api.configuration import ConfigurationError, load_local_environment
    except ImportError:
        print(json.dumps({"status": "dependencies_missing", "message": "Run make setup, then use clearway/.venv/bin/python for this check."}))
        return 2
    try:
        load_local_environment()
    except ConfigurationError as error:
        print(json.dumps({"status": "configuration_error", "message": str(error)}))
        return 2
    report = offline_report()
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "offline_prerequisites_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
