"""Read a small public camera inventory snapshot without network requests.

These are geographic context points, never incident corroboration or a claim
that a stream is online. Latitude/longitude are publisher attributes, not
coordinates inferred from the demo video or centroids of buffer polygons.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "docs" / "camera-context.json"
ITEM_ID = "384ee5b6105e48cba8009ad842b508c4"
SOURCE_URL = f"https://www.arcgis.com/home/item.html?id={ITEM_ID}"
ITEM_API = f"https://www.arcgis.com/sharing/rest/content/items/{ITEM_ID}"
LAYER_URL = "https://services.arcgis.com/NuWFvHYDMVmmxMeM/arcgis/rest/services/NCDOT_CCTV_Buffer_1Mile/FeatureServer/0"
TTL_SECONDS = 86_400
MAX_POINTS = 20
NOTE = "Camera inventory only; stream status unverified. Unrelated to replay footage; not incident corroboration."
ATTRIBUTION = "NCDOT / NCDIT-Transportation GIS Unit"
CENTER = (35.9940, -78.8986)


def _time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Missing snapshot time")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Snapshot time must contain a timezone")
    return parsed.astimezone(timezone.utc)


def _coordinate(value: object, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("Invalid coordinate")
    number = float(value)
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError("Coordinate outside the selected Durham region")
    return number


def _distance(point: dict) -> float:
    lat, lon = math.radians(point["latitude"]), math.radians(point["longitude"])
    lat0, lon0 = map(math.radians, CENTER)
    return math.sin((lat - lat0) / 2) ** 2 + math.cos(lat) * math.cos(lat0) * math.sin((lon - lon0) / 2) ** 2


def make_snapshot(features: list, fetched_at: str, source_updated_at: str | None = None) -> dict:
    """Normalize a bounded ArcGIS response; select only explicitly named CCTVs."""
    _time(fetched_at)
    if source_updated_at is not None:
        _time(source_updated_at)
    if not isinstance(features, list) or len(features) > 250:
        raise ValueError("Unexpected camera inventory size")
    points, seen = [], set()
    for feature in features:
        attrs = feature.get("attributes", {}) if isinstance(feature, dict) else {}
        name = attrs.get("Name")
        if not isinstance(name, str) or "CCTV" not in name.upper() or attrs.get("DeviceType") != "Encoder":
            continue
        identifier = attrs.get("OBJECTID")
        description = attrs.get("LocationDescr")
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier <= 0:
            raise ValueError("Invalid camera identifier")
        if not isinstance(description, str) or not description.strip() or len(name) > 100 or len(description) > 100:
            raise ValueError("Invalid camera description")
        if name in seen:
            continue
        seen.add(name)
        points.append({
            "id": f"ncdot-cctv-{identifier}", "name": name.strip(),
            "description": description.strip(),
            "latitude": _coordinate(attrs.get("Lat"), 35.85, 36.10),
            "longitude": _coordinate(attrs.get("Long"), -79.05, -78.70),
            "quality": "official_inventory", "status": "metadata_only",
        })
    points.sort(key=lambda point: (_distance(point), point["id"]))
    if not points:
        raise ValueError("No camera inventory points in selected region")
    return {
        "schema_version": 1, "mode": "inventory_snapshot",
        "fetched_at": fetched_at, "source_updated_at": source_updated_at,
        "source_url": SOURCE_URL, "layer_url": LAYER_URL,
        "attribution": ATTRIBUTION, "note": NOTE,
        "terms": "Public NCDOT item; publisher disclaims accuracy. Consult the linked source for verification and current terms.",
        "selection": "Nearest 20 explicitly CCTV-named Encoder records to central Durham, using original Lat/Long attributes; no buffer geometry or imagery.",
        "points": points[:MAX_POINTS],
    }


def camera_context_record(path: Path | None = None, *, now: datetime | None = None) -> dict:
    """Return validated, visibly dated inventory; missing/corrupt data stays unavailable."""
    source = Path(path) if path is not None else SNAPSHOT_PATH
    unavailable = {
        "status": "unavailable", "mode": "inventory_snapshot", "fetched_at": None,
        "stale": True, "ttl_seconds": TTL_SECONDS, "attribution": ATTRIBUTION,
        "source_url": SOURCE_URL, "note": NOTE, "points": [],
        "message": "Camera inventory snapshot is unavailable; no locations were substituted.",
    }
    try:
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 100_000:
            return unavailable
        content = json.loads(source.read_text(encoding="utf-8"))
        if content.get("schema_version") != 1 or content.get("mode") != "inventory_snapshot" or content.get("source_url") != SOURCE_URL:
            raise ValueError("Unsupported snapshot provenance")
        fetched = _time(content.get("fetched_at"))
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or fetched > current:
            raise ValueError("Invalid snapshot time")
        points = content.get("points")
        if not isinstance(points, list) or not 1 <= len(points) <= MAX_POINTS:
            raise ValueError("Unexpected camera count")
        seen = set()
        for point in points:
            if not isinstance(point, dict) or point.get("quality") != "official_inventory" or point.get("status") != "metadata_only":
                raise ValueError("Invalid point provenance")
            identifier = point.get("id", "")
            if not isinstance(identifier, str) or not identifier.startswith("ncdot-cctv-") or not identifier.removeprefix("ncdot-cctv-").isdigit() or identifier in seen:
                raise ValueError("Invalid camera identifier")
            seen.add(identifier)
            for field in ("name", "description"):
                if not isinstance(point.get(field), str) or not 1 <= len(point[field]) <= 100:
                    raise ValueError("Invalid camera label")
            _coordinate(point.get("latitude"), 35.85, 36.10)
            _coordinate(point.get("longitude"), -79.05, -78.70)
        # Only explicitly supported fields cross the UI boundary.
        return {
            "status": "available", "mode": "inventory_snapshot",
            "fetched_at": content["fetched_at"], "source_updated_at": content.get("source_updated_at"),
            "stale": (current - fetched).total_seconds() > TTL_SECONDS,
            "ttl_seconds": TTL_SECONDS, "attribution": ATTRIBUTION,
            "source_url": SOURCE_URL, "note": NOTE,
            "points": [{key: point[key] for key in ("id", "name", "description", "latitude", "longitude", "quality", "status")} for point in points],
        }
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return unavailable
