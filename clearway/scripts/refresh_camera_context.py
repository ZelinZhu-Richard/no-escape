#!/usr/bin/env python3
"""Refresh the bounded public NCDOT camera-location inventory (no footage).

The app reads the saved snapshot only. Manual refresh is rate-limited to once
per day unless --force is deliberately supplied. Failure retains old data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.camera_context import ITEM_API, LAYER_URL, SNAPSHOT_PATH, camera_context_record, make_snapshot  # noqa: E402

ALLOWED_HOSTS = {"www.arcgis.com", "services.arcgis.com"}


def get_json(url: str, parameters: dict) -> dict:
    request = urllib.request.Request(url + "?" + urllib.parse.urlencode(parameters), headers={"User-Agent": "ClearwayDemo/1.0 (public camera inventory context)", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        final = urllib.parse.urlsplit(response.url)
        if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
            raise ValueError("Unexpected inventory redirect")
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("Inventory response exceeds limit")
    result = json.loads(raw)
    if not isinstance(result, dict) or "error" in result:
        raise ValueError("Inventory source returned an error")
    return result


def refresh(*, force: bool = False) -> dict:
    current = camera_context_record()
    if current["status"] == "available" and not current["stale"] and not force:
        return {"status": "unchanged", "points": len(current["points"]), "fetched_at": current["fetched_at"], "message": "Snapshot is less than one day old; no network request made."}
    item = get_json(ITEM_API, {"f": "json"})
    if item.get("owner") != "GISUnit.NCDOT.GOV" or item.get("access") != "public" or item.get("url") != LAYER_URL.rsplit("/", 1)[0]:
        raise ValueError("Official public inventory provenance changed")
    # Query original coordinate attributes, not polygon centers. Restrict the
    # request to the demo's Durham region and exclude unrelated ITS equipment.
    response = get_json(LAYER_URL + "/query", {
        "f": "json", "where": "Lat BETWEEN 35.85 AND 36.10 AND Long BETWEEN -79.05 AND -78.70 AND Name LIKE '%CCTV%' AND DeviceType = 'Encoder'",
        "outFields": "OBJECTID,Name,LocationDescr,Lat,Long,DeviceType",
        "returnGeometry": "false", "resultRecordCount": 250,
        "orderByFields": "OBJECTID ASC",
    })
    if response.get("exceededTransferLimit"):
        raise ValueError("Inventory query truncated; previous snapshot retained")
    modified = item.get("modified")
    if isinstance(modified, bool) or not isinstance(modified, int):
        raise ValueError("Missing publisher update time")
    updated = datetime.fromtimestamp(modified / 1000, timezone.utc).isoformat()
    snapshot = make_snapshot(response.get("features"), datetime.now(timezone.utc).isoformat(), updated)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=SNAPSHOT_PATH.parent, suffix=".tmp", delete=False) as stream:
            json.dump(snapshot, stream, indent=2, allow_nan=False)
            stream.write("\n")
            temporary = Path(stream.name)
        temporary.replace(SNAPSHOT_PATH)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"status": "refreshed", "points": len(snapshot["points"]), "fetched_at": snapshot["fetched_at"], "source_updated_at": updated, "message": "Saved public camera inventory only; no live imagery or incident evidence fetched."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Bypass the local one-day refresh interval.")
    args = parser.parse_args()
    try:
        print(json.dumps(refresh(force=args.force), indent=2))
        return 0
    except Exception:
        print(json.dumps({"status": "unavailable", "message": "Camera inventory refresh failed; existing snapshot retained. No substitute points created."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
