"""Restoration and API consumers must agree on where licensed media lives."""

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys

import pytest

from api import configuration
from api.sources import media_path


@pytest.mark.parametrize("script,source_id", [
    ("fetch_footage", "road-obstruction"),
    ("fetch_person_footage", "person-roadway"),
])
@pytest.mark.parametrize("setting", ["default", "env_file", "process_override"])
def test_restore_uses_consumer_data_directory(tmp_path, monkeypatch, script, source_id, setting):
    spec = importlib.util.spec_from_file_location(
        script, Path(__file__).resolve().parents[1] / f"scripts/{script}.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "app"
    (root / "docs").mkdir(parents=True)
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(configuration, "LOCAL_ENV_PATH", root / ".env")
    # Isolate all settings loaded by the real configuration helper, including defaults.
    monkeypatch.setattr(os, "environ", {
        key: value for key, value in os.environ.items()
        if key not in configuration.ALLOWED_VARIABLES
    })
    data = root / "data"
    if setting != "default":
        data = tmp_path / "configured data"
        (root / ".env").write_text(f'CLEARWAY_DATA_DIR="{data}"\n')
    if setting == "process_override":
        data = tmp_path / "process data"
        monkeypatch.setenv("CLEARWAY_DATA_DIR", str(data))

    original = b"licensed source fixture"
    replay = b"derived replay fixture"
    checksum = hashlib.sha256(original).hexdigest()
    replay_hash = hashlib.sha256(replay).hexdigest()
    url = "https://videos.pexels.com/fixture.mp4"
    selected = {
        "id": source_id, "title": "Fixture", "creator": "Fixture author",
        "author": "Fixture author", "license_url": "https://example.test/license",
        "download_url": url,
        "original": {"filename": f"{source_id}-original.mp4", "sha256": checksum},
        "demo": {"sha256": replay_hash}, "replay": {"sha256": replay_hash},
    }
    if script == "fetch_footage":
        control = {
            "id": "street-traffic", "filename": "street-traffic.webm", "sha256": checksum,
            "download_url": url, "license_url": "https://example.test/license",
        }
        (root / "docs/footage-sources.json").write_text(json.dumps({"clips": [selected, control]}))
        monkeypatch.setattr(sys, "argv", [script, "--with-control"])
        receipt_name = "footage-download-receipt.json"
    else:
        (root / "docs/person-footage-candidate.json").write_text(json.dumps(selected))
        receipt_name = "person-footage-download-receipt.json"

    class Response(io.BytesIO):
        headers = {}

        def __init__(self):
            super().__init__(original)
            self.url = url

        def geturl(self):
            return self.url

    class Opener:
        def open(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(module.urllib.request, "build_opener", lambda *_args: Opener())
    monkeypatch.setattr(module.shutil, "which", lambda command: command)
    monkeypatch.setattr(module, "prepare_derivative", lambda _original, target, _hash: target.write_bytes(replay))
    monkeypatch.setattr(module.subprocess, "run", lambda command, **_kwargs: Path(command[-1]).write_bytes(b"poster"))

    module.main()

    media = data / "footage"
    assert (media / f"{source_id}-original.mp4").read_bytes() == original
    assert media_path(data, source_id, "video") == (media / f"{source_id}-demo.mp4").resolve()
    assert media_path(data, source_id, "poster").read_bytes() == b"poster"
    if script == "fetch_footage":
        assert media_path(data, "street-traffic", "video").read_bytes() == original
    receipt = json.loads((data / receipt_name).read_text())
    assert receipt["source_sha256"] == checksum
    assert receipt["local_demo_sha256"] == replay_hash
    if setting != "default":
        assert not (root / "data").exists()
    if setting == "process_override":
        assert not (tmp_path / "configured data").exists()
