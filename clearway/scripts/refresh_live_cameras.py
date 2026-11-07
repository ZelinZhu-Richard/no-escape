#!/usr/bin/env python3
"""Refresh the free official Caltrans camera catalog, never the camera images."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.live_cameras import CATALOG_PATH, CATALOG_URL, LiveCameraService, _NoRedirect, normalize_catalog  # noqa: E402


def refresh(*, force=False) -> dict:
    existing = LiveCameraService().catalog()
    if existing["status"] == "available" and not existing["stale"] and not force:
        return {"status": "unchanged", "cameras": len(existing["cameras"]), "message": "Catalog is less than one day old; no network request made."}
    request = urllib.request.Request(CATALOG_URL, headers={"User-Agent": "ClearwayDemo/1.0 (public CCTV catalog)", "Accept": "application/json"})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=20) as response:
        raw = response.read(8_000_001)
        if response.status != 200 or len(raw) > 8_000_000:
            raise ValueError("Catalog response unavailable or oversized")
    document = normalize_catalog(json.loads(raw), datetime.now(timezone.utc).isoformat())
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=CATALOG_PATH.parent, suffix=".tmp", delete=False) as stream:
            json.dump(document, stream, indent=2, allow_nan=False)
            stream.write("\n")
            temporary = Path(stream.name)
        temporary.replace(CATALOG_PATH)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return {"status": "refreshed", "cameras": len(document["cameras"]), "fetched_at": document["fetched_at"], "message": "Official camera metadata saved. No images or streams fetched by this command."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Deliberately bypass the one-day metadata refresh interval.")
    args = parser.parse_args()
    try:
        print(json.dumps(refresh(force=args.force), indent=2))
        return 0
    except Exception:
        print(json.dumps({"status": "unavailable", "message": "Catalog refresh failed; the existing catalog was retained."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
