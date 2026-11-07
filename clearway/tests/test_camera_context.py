from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path

import pytest

from api.camera_context import camera_context_record, make_snapshot

NOW = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)


def feature(identifier=146, name="05-1312 CCTV", device_type="Encoder"):
    return {"attributes": {"OBJECTID": identifier, "Name": name, "LocationDescr": "NC 147 @ Magnum St", "Lat": 35.99009092, "Long": -78.90303612, "DeviceType": device_type}}


def save(tmp_path, snapshot):
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(snapshot))
    return path


def test_inventory_is_metadata_only_deduplicated_and_uses_original_coordinates(tmp_path):
    source = feature()
    source["geometry"] = {"rings": [[[0, 0], [1, 1]]]}
    snapshot = make_snapshot([source, feature(147), feature(999, "Printer", "Printer")], NOW.isoformat())
    assert len(snapshot["points"]) == 1
    point = snapshot["points"][0]
    assert (point["latitude"], point["longitude"]) == (35.99009092, -78.90303612)
    record = camera_context_record(save(tmp_path, snapshot), now=NOW)
    assert record["status"] == "available"
    assert record["points"][0]["status"] == "metadata_only"
    assert "not incident corroboration" in record["note"]
    assert record["stale"] is False


def test_old_inventory_remains_visibly_stale(tmp_path):
    path = save(tmp_path, make_snapshot([feature()], NOW.isoformat()))
    result = camera_context_record(path, now=NOW + timedelta(days=2))
    assert result["status"] == "available" and result["stale"] is True


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0, "35.9", True])
def test_invalid_coordinates_cannot_become_map_points(bad):
    source = feature()
    source["attributes"]["Lat"] = bad
    with pytest.raises(ValueError):
        make_snapshot([source], NOW.isoformat())


def test_missing_corrupt_future_and_untrusted_snapshots_are_unavailable(tmp_path):
    path = tmp_path / "inventory.json"
    assert camera_context_record(path, now=NOW)["status"] == "unavailable"
    path.write_text("not-json")
    assert camera_context_record(path, now=NOW)["points"] == []
    data = make_snapshot([feature()], (NOW + timedelta(seconds=1)).isoformat())
    assert camera_context_record(save(tmp_path, data), now=NOW)["status"] == "unavailable"
    data = make_snapshot([feature()], NOW.isoformat())
    data["points"][0]["status"] = "online"
    assert camera_context_record(save(tmp_path, data), now=NOW)["points"] == []


def test_no_automatic_network_on_read_and_no_repeated_refresh(monkeypatch, tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "refresh_camera_context.py"
    spec = importlib.util.spec_from_file_location("refresh_camera_context", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "camera_context_record", lambda: {"status": "available", "stale": False, "points": [1], "fetched_at": NOW.isoformat()})
    monkeypatch.setattr(module, "get_json", lambda *_: pytest.fail("unexpected network"))
    assert module.refresh()["status"] == "unchanged"


def test_selection_caps_at_twenty_nearest_entries():
    features = [feature(i, f"CCTV {i}") for i in range(1, 30)]
    features[-1]["attributes"]["Lat"] = 35.994
    features[-1]["attributes"]["Long"] = -78.8986
    snapshot = make_snapshot(features, NOW.isoformat())
    assert len(snapshot["points"]) == 20
    assert snapshot["points"][0]["id"] == "ncdot-cctv-29"
