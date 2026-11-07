"""Selected-camera access to Caltrans' public, current CCTV snapshots.

Catalog reads are offline. Only an explicitly selected allowlisted camera can
fetch an image; no archive, background fleet polling, inference, or incident
corroboration is performed. A refreshed still image is not continuous video.
"""
from __future__ import annotations

import base64
from collections import OrderedDict, deque
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "docs" / "live-camera-sources.json"
CATALOG_URL = "https://cwwp2.dot.ca.gov/data/d4/cctv/cctvStatusD04.json"
PROVIDER_URL = "https://cwwp2.dot.ca.gov/closed-circuit-television-cameras.html"
TERMS_URL = "https://dot.ca.gov/conditions-of-use"
CATALOG_TTL = 86400
MAX_CAMERAS = 100
MAX_IMAGE_BYTES = 1_000_000
MIN_REFRESH_SECONDS = 30
NOTE = "Public Caltrans camera snapshots, separate from licensed replay scenes. No live incident detection or corroboration is performed."
CAMERA_ID = re.compile(r"caltrans-d4-\d+(?:-\d+)?\Z")
IMAGE_PATH = re.compile(r"/data/d4/cctv/image/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+\.jpg\Z")
STREAM_PATH = re.compile(r"/D4/[A-Za-z0-9_.-]+/playlist\.m3u8\Z")


def valid_provider_url(value: object, *, stream: bool = False) -> bool:
    if not isinstance(value, str) or len(value) > 500:
        return False
    try:
        url = urllib.parse.urlsplit(value)
        return bool(url.scheme == "https" and url.hostname == ("wzmedia.dot.ca.gov" if stream else "cwwp2.dot.ca.gov")
                    and not url.username and not url.password and not url.port and not url.query and not url.fragment
                    and (STREAM_PATH if stream else IMAGE_PATH).fullmatch(url.path))
    except ValueError:
        return False


def _iso(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Missing catalog time")
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("Missing timezone")
    return moment.astimezone(timezone.utc)


def _text(value: object, max_length: int = 160) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError("Invalid public camera field")
    return value.strip()


def _coordinate(value: object, lower: float, upper: float) -> float:
    if isinstance(value, bool):
        raise ValueError("Invalid coordinate")
    result = float(value)
    if not math.isfinite(result) or not lower <= result <= upper:
        raise ValueError("Camera outside Bay Area selection")
    return result


def _distance(camera: dict) -> float:
    # Rank authentic publisher locations around the San Francisco/Oakland core.
    lat, lon = math.radians(camera["latitude"]), math.radians(camera["longitude"])
    lat0, lon0 = math.radians(37.79), math.radians(-122.36)
    return math.sin((lat-lat0)/2)**2 + math.cos(lat)*math.cos(lat0)*math.sin((lon-lon0)/2)**2


def normalize_catalog(payload: dict, fetched_at: str) -> dict:
    _iso(fetched_at)
    records = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(records, list) or not 1 <= len(records) <= 3000:
        raise ValueError("Unexpected Caltrans catalog")
    cameras, seen = [], set()
    for wrapper in records:
        try:
            row = wrapper["cctv"]
            loc, image = row["location"], row["imageData"]
            static = image["static"]
            identifier = "caltrans-d4-" + str(row["index"])
            if not CAMERA_ID.fullmatch(identifier) or identifier in seen or str(loc.get("district")) != "4" or row.get("inService") != "true":
                continue
            image_url = static.get("currentImageURL")
            if not valid_provider_url(image_url):
                continue
            county = _text(loc["county"], 100)
            interval = static.get("currentImageUpdateFrequency", "")
            # The official field is minutes, NOT seconds. Unknown cadence uses
            # a conservative five-minute cache rather than assuming live FPS.
            seconds = int(interval) * 60 if str(interval).isdigit() and 1 <= int(interval) <= 1440 else 300
            stream_url = image.get("streamingVideoURL")
            camera = {
                "id": identifier, "name": _text(loc["locationName"]),
                "latitude": _coordinate(loc["latitude"], 36.8, 39.0),
                "longitude": _coordinate(loc["longitude"], -123.5, -121.0),
                "region_id": re.sub(r"[^a-z0-9]+", "-", county.lower()).strip("-"),
                "region_name": county, "roadway": _text(loc["route"], 30),
                "direction": _text(loc.get("direction") or "Not reported", 40),
                "provider": "Caltrans", "provider_url": PROVIDER_URL,
                "mode": "refreshed_snapshot", "in_service_reported": True,
                "capture_time": None, "source_refresh_seconds": seconds,
                "image_url": image_url,
                "streaming_url": stream_url if valid_provider_url(stream_url, stream=True) else None,
            }
            cameras.append(camera)
            seen.add(identifier)
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    cameras.sort(key=lambda camera: (_distance(camera), camera["id"]))
    if len(cameras) < 30:
        raise ValueError("Too few supported public cameras; previous catalog retained")
    return {
        "schema_version": 1, "provider": "Caltrans", "source_url": CATALOG_URL,
        "provider_url": PROVIDER_URL, "terms_url": TERMS_URL,
        "fetched_at": fetched_at,
        "attribution": "California Department of Transportation / Caltrans",
        "terms_summary": "Caltrans explicitly provides these CCTV datasets for application integration without charge. Follow its fair-use policy; no high-volume polling or archive is performed.",
        "selection": "100 in-service-reported District 4 camera locations nearest the San Francisco/Oakland core. Availability of individual images is checked only when selected.",
        "note": NOTE, "cameras": cameras[:MAX_CAMERAS],
    }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def fetch_image(url: str) -> tuple[bytes, dict]:
    """Strict public host/path allowlist, verified HTTPS, no redirects or retries."""
    if not valid_provider_url(url):
        raise ValueError("Unsupported image URL")
    request = urllib.request.Request(url, headers={"User-Agent": "ClearwayDemo/1.0 (selected public CCTV snapshot)", "Accept": "image/jpeg"})
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=10) as response:
        if response.status != 200 or response.headers.get_content_type() != "image/jpeg":
            raise ValueError("Image unavailable")
        length = response.headers.get("Content-Length")
        if length is not None and (not length.isdigit() or int(length) > MAX_IMAGE_BYTES):
            raise ValueError("Image response exceeds limit")
        raw = response.read(MAX_IMAGE_BYTES + 1)
        if not 4 <= len(raw) <= MAX_IMAGE_BYTES or not raw.startswith(b"\xff\xd8\xff") or not raw.endswith(b"\xff\xd9"):
            raise ValueError("Invalid JPEG response")
        return raw, {"Last-Modified": response.headers.get("Last-Modified")}


class LiveCameraService:
    def __init__(self, catalog_path: Path | None = None, *, image_fetcher=None, clock=None, monotonic=None):
        self.catalog_path = Path(catalog_path) if catalog_path else CATALOG_PATH
        self._fetch = image_fetcher or fetch_image
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic or time.monotonic
        self._lock = threading.RLock()
        self._cache: OrderedDict[str, dict] = OrderedDict()
        # Deadlines outlive the four-image LRU, so cycling through five cameras
        # cannot evade the publisher's refresh cadence. Catalog caps this at 100.
        self._deadlines: dict[str, dict] = {}
        self._attempts = deque()

    def _read(self) -> dict:
        path = self.catalog_path
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 300_000:
            raise ValueError("Catalog unavailable")
        doc = json.loads(path.read_text())
        if doc.get("schema_version") != 1 or doc.get("source_url") != CATALOG_URL or doc.get("provider") != "Caltrans":
            raise ValueError("Invalid camera provenance")
        fetched = _iso(doc.get("fetched_at"))
        if fetched > self._clock():
            raise ValueError("Invalid catalog time")
        cameras = doc.get("cameras")
        if not isinstance(cameras, list) or not 1 <= len(cameras) <= MAX_CAMERAS:
            raise ValueError("Invalid catalog size")
        seen = set()
        for camera in cameras:
            identifier = camera.get("id", "")
            if not CAMERA_ID.fullmatch(identifier) or identifier in seen or not valid_provider_url(camera.get("image_url")):
                raise ValueError("Invalid camera source")
            seen.add(identifier)
            if camera.get("provider") != "Caltrans" or camera.get("provider_url") != PROVIDER_URL or camera.get("mode") != "refreshed_snapshot" or camera.get("capture_time") is not None or camera.get("in_service_reported") is not True:
                raise ValueError("Invalid camera provenance")
            for key in ("name", "region_id", "region_name", "roadway", "direction"):
                _text(camera.get(key))
            _coordinate(camera.get("latitude"), 36.8, 39.0)
            _coordinate(camera.get("longitude"), -123.5, -121.0)
            seconds = camera.get("source_refresh_seconds")
            if isinstance(seconds, bool) or not isinstance(seconds, int) or not 60 <= seconds <= 86400:
                raise ValueError("Invalid source cadence")
            if camera.get("streaming_url") is not None and not valid_provider_url(camera["streaming_url"], stream=True):
                raise ValueError("Invalid provider stream")
        return doc

    def catalog(self) -> dict:
        base = {"provider": "Caltrans", "mode": "live_snapshot_catalog", "refresh_interval_seconds": MIN_REFRESH_SECONDS, "note": NOTE, "attribution": "California Department of Transportation / Caltrans", "provider_url": PROVIDER_URL}
        try:
            doc = self._read()
            cameras = [{key: value for key, value in row.items() if key != "image_url"} for row in doc["cameras"]]
            regions = [{"id": identifier, "name": name} for identifier, name in sorted({(c["region_id"], c["region_name"]) for c in cameras})]
            return {**base, "status": "available", "fetched_at": doc["fetched_at"], "stale": (self._clock()-_iso(doc["fetched_at"])).total_seconds() > CATALOG_TTL, "regions": regions, "cameras": cameras}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return {**base, "status": "unavailable", "fetched_at": None, "stale": True, "regions": [], "cameras": [], "message": "Public camera catalog unavailable; no camera locations substituted."}

    def snapshot(self, camera_id: str) -> dict:
        base = {"status": "unavailable", "camera_id": camera_id, "mode": "refreshed_snapshot", "image_data_url": None, "fetched_at": None, "source_last_modified": None, "capture_time": None, "stale": True, "refresh_after_seconds": MIN_REFRESH_SECONDS}
        try:
            if not isinstance(camera_id, str) or not CAMERA_ID.fullmatch(camera_id):
                raise ValueError("Invalid camera")
            camera = next((item for item in self._read()["cameras"] if item["id"] == camera_id), None)
            if camera is None:
                raise ValueError("Unknown camera")
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return {**base, "message": "Selected public camera is unavailable; no image substituted."}
        interval = max(MIN_REFRESH_SECONDS, camera["source_refresh_seconds"])
        with self._lock:
            now_tick = self._monotonic()
            cached = self._cache.get(camera_id)
            if cached and cached["url"] == camera["image_url"] and now_tick < cached["next_fetch"]:
                self._cache.move_to_end(camera_id)
                return {**cached["result"], "refresh_after_seconds": max(1, math.ceil(cached["next_fetch"]-now_tick))}
            deadline = self._deadlines.get(camera_id)
            if deadline and deadline["url"] == camera["image_url"] and now_tick < deadline["next_fetch"]:
                return {**base, "status": "throttled", "message": "This camera was fetched recently; its image was released from memory. Wait for the next source refresh.", "refresh_after_seconds": max(1, math.ceil(deadline["next_fetch"]-now_tick))}
            self._deadlines = {key: value for key, value in self._deadlines.items() if value["next_fetch"] > now_tick}
            if camera_id not in self._deadlines and len(self._deadlines) >= MAX_CAMERAS:
                return {**base, "status": "throttled", "message": "Camera refresh capacity reached; wait for existing source refresh windows.", "refresh_after_seconds": MIN_REFRESH_SECONDS}
            while self._attempts and self._attempts[0] <= now_tick-60:
                self._attempts.popleft()
            if len(self._attempts) >= 20 or (self._attempts and now_tick-self._attempts[-1] < 2):
                return {**base, "status": "throttled", "message": "Camera switching is rate limited; retry shortly.", "refresh_after_seconds": 5}
            self._attempts.append(now_tick)
            try:
                raw, headers = self._fetch(camera["image_url"])
                if not 4 <= len(raw) <= MAX_IMAGE_BYTES or not raw.startswith(b"\xff\xd8\xff") or not raw.endswith(b"\xff\xd9"):
                    raise ValueError("Invalid image")
                fetched = self._clock()
                modified = None
                try:
                    parsed = parsedate_to_datetime(headers.get("Last-Modified") or "")
                    if parsed.tzinfo is not None and parsed <= fetched:
                        modified = parsed.astimezone(timezone.utc)
                except (TypeError, ValueError, OverflowError):
                    pass
                stale = modified is not None and (fetched-modified).total_seconds() > max(900, interval*2)
                result = {**base, "status": "available", "image_data_url": "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii"), "fetched_at": fetched.isoformat(), "source_last_modified": modified.isoformat() if modified else None, "stale": stale, "refresh_after_seconds": interval, "source_refresh_seconds": interval, "message": "Latest provider snapshot fetched; exact capture time is unknown." if not stale else "Provider image metadata is old; this snapshot may be stale."}
                next_fetch = self._monotonic()+interval
            except Exception:
                result = {**base, "message": "Public camera image unavailable; no substitute image or inference result created."}
                if cached and cached["url"] == camera["image_url"] and cached["result"].get("image_data_url"):
                    result.update({key: cached["result"][key] for key in ("image_data_url", "fetched_at", "source_last_modified")})
                    result["message"] = "Refresh failed; showing the previous snapshot marked stale."
                next_fetch = self._monotonic()+MIN_REFRESH_SECONDS
            self._cache[camera_id] = {"url": camera["image_url"], "result": result, "next_fetch": next_fetch}
            self._deadlines[camera_id] = {"url": camera["image_url"], "next_fetch": next_fetch}
            self._cache.move_to_end(camera_id)
            while len(self._cache) > 4:
                self._cache.popitem(last=False)
            return result
