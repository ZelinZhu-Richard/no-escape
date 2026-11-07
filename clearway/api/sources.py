"""Small explicit media registry: no user-provided paths or archive browsing."""

from copy import deepcopy
from pathlib import Path


SOURCES = {
    "road-obstruction": {
        "id": "road-obstruction",
        "title": "Road obstruction / utility work zone",
        "duration_seconds": 11.1111,
        "video": "road-obstruction-demo.mp4",
        "poster": "road-obstruction-poster.jpg",
        "control_status": "reference_scenario_not_human_evaluation",
        "attribution": {
            "creator": "Ibrahim Bennett",
            "title": "Utility Workers Clearing Storm Debris on Road",
            "source_url": "https://www.pexels.com/video/utility-workers-clearing-storm-debris-on-road-30567549/",
            "license": "Pexels License",
            "license_url": "https://www.pexels.com/license/",
        },
        "location": {
            "latitude": 35.9940,
            "longitude": -78.8986,
            "quality": "simulated",
            "label": "Demo placement · Durham",
        },
    },
    "street-traffic": {
        "id": "street-traffic",
        "title": "Street traffic · control candidate",
        "duration_seconds": 35.004,
        "video": "street-traffic.webm",
        "poster": "street-traffic-review.jpg",
        "control_status": "awaiting_human_labels",
        "attribution": {
            "creator": "Editor (YouTube channel)",
            "title": "Street traffic",
            "source_url": "https://commons.wikimedia.org/wiki/File:Street_traffic.webm",
            "license": "CC BY 3.0",
            "license_url": "https://creativecommons.org/licenses/by/3.0/",
        },
        "location": {
            "latitude": 37.79456,
            "longitude": -122.39467,
            "quality": "known_camera",
            "label": "Commons camera metadata · uncalibrated",
        },
    },
    "traffic-jam": {
        "id": "traffic-jam",
        "title": "Dense traffic · development footage",
        "duration_seconds": 11.2,
        "video": "traffic-jam.webm",
        "poster": "traffic-jam-review.jpg",
        "control_status": "awaiting_human_labels",
        "attribution": {
            "creator": "Melvin Loi",
            "title": "Traffic Jam",
            "source_url": "https://commons.wikimedia.org/wiki/File:Traffic_Jam.webm",
            "license": "CC BY-SA 2.0",
            "license_url": "https://creativecommons.org/licenses/by-sa/2.0/",
        },
        "location": {
            "latitude": None,
            "longitude": None,
            "quality": "unknown",
            "label": "Source location unknown",
        },
    },
}


def media_path(data_dir: Path, source_id: str, kind: str) -> Path | None:
    source = SOURCES.get(source_id)
    if not source or kind not in ("video", "poster"):
        return None
    folder = (data_dir / "footage").resolve()
    path = folder / source[kind]
    # A replaced file must not become a symlink escape from the media directory.
    if path.is_symlink() or path.resolve().parent != folder or not path.is_file():
        return None
    return path


def source_record(data_dir: Path, source_id: str, responder_prefix: str | None = None) -> dict:
    source = deepcopy(SOURCES[source_id])
    source.pop("video")
    source.pop("poster")
    prefix = responder_prefix or f"/api/media/{source_id}"
    source.update(
        source_mode="recorded_replay",
        video_url=f"{prefix}/video",
        poster_url=f"{prefix}/poster",
        media_available=media_path(data_dir, source_id, "video") is not None,
        poster_available=media_path(data_dir, source_id, "poster") is not None,
        capture_time=None,
    )
    return source
