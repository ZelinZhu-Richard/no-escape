import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import urllib.request

import pytest


spec = importlib.util.spec_from_file_location(
    "fetch_person_footage", Path(__file__).resolve().parents[1] / "scripts/fetch_person_footage.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

URL = "https://videos.pexels.com/video-files/35532487/selected.mp4"


class Response(io.BytesIO):
    headers = {}

    def geturl(self):
        return URL


def mock_download(monkeypatch, response):
    class Opener:
        def open(self, request, timeout):
            assert timeout <= 10
            return response

    monkeypatch.setattr(module.urllib.request, "build_opener", lambda *args: Opener())


def test_existing_unknown_original_is_preserved_without_network(tmp_path, monkeypatch):
    target = tmp_path / "original.mp4"
    target.write_bytes(b"private existing file")
    monkeypatch.setattr(module.urllib.request, "build_opener", lambda *args: pytest.fail("Network must not be attempted"))
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        module.download_original(URL, target, "a" * 64)
    assert target.read_bytes() == b"private existing file"


def test_download_checksum_mismatch_never_publishes(tmp_path, monkeypatch):
    mock_download(monkeypatch, Response(b"different source bytes"))
    target = tmp_path / "original.mp4"
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        module.download_original(URL, target, "a" * 64)
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_interrupted_download_cleans_partial(tmp_path, monkeypatch):
    class Interrupted(Response):
        def read(self, _size):
            if self.tell() == 0:
                self.seek(1)
                return b"partial"
            raise TimeoutError("connection timed out")

    mock_download(monkeypatch, Interrupted(b"x"))
    with pytest.raises(TimeoutError):
        module.download_original(URL, tmp_path / "original.mp4", "a" * 64)
    assert list(tmp_path.iterdir()) == []


def test_download_limit_stops_before_publishing(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "MAX_BYTES", 5)
    mock_download(monkeypatch, Response(b"123456"))
    with pytest.raises(RuntimeError, match="download limit"):
        module.download_original(URL, tmp_path / "original.mp4", "a" * 64)
    assert list(tmp_path.iterdir()) == []


def test_download_deadline_stops_before_publishing(tmp_path, monkeypatch):
    clock = iter([0, 0, module.DOWNLOAD_SECONDS + 1])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    mock_download(monkeypatch, Response(b"content"))
    with pytest.raises(TimeoutError, match="time limit"):
        module.download_original(URL, tmp_path / "original.mp4", "a" * 64)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("redirect", [
    "http://videos.pexels.com/video.mp4",
    "https://example.com/video.mp4",
    "https://videos.pexels.com.evil.example/video.mp4",
    "https://user:password@videos.pexels.com/video.mp4",
])
def test_redirect_handler_rejects_outside_https_host_before_following(redirect):
    handler = module.MediaRedirectHandler()
    with pytest.raises(ValueError, match="HTTPS on videos.pexels.com"):
        handler.redirect_request(urllib.request.Request(URL), None, 302, "Found", {}, redirect)


def test_verified_download_publishes_complete_bytes(tmp_path, monkeypatch):
    content = b"verified licensed source"
    mock_download(monkeypatch, Response(content))
    target = tmp_path / "original.mp4"
    assert module.download_original(URL, target, hashlib.sha256(content).hexdigest()) == target
    assert target.read_bytes() == content
    assert list(tmp_path.iterdir()) == [target]


def test_interrupted_transcode_leaves_no_final_copy(tmp_path, monkeypatch):
    source = tmp_path / "original.mp4"
    source.write_bytes(b"verified source")
    target = tmp_path / "demo.mp4"
    monkeypatch.setattr(module.shutil, "which", lambda name: name)

    def interrupted(command, **kwargs):
        Path(command[-1]).write_bytes(b"truncated")
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(module.subprocess, "run", interrupted)
    with pytest.raises(subprocess.TimeoutExpired):
        module.prepare_derivative(source, target, "a" * 64)
    assert not target.exists()
    assert list(tmp_path.glob(".person-preparing-*")) == []
    assert source.read_bytes() == b"verified source"


def test_existing_invalid_replay_is_preserved_and_rejected(tmp_path, monkeypatch):
    target = tmp_path / "demo.mp4"
    target.write_bytes(b"truncated")
    monkeypatch.setattr(module.shutil, "which", lambda name: name)
    monkeypatch.setattr(module, "validate_derivative", lambda *args: (_ for _ in ()).throw(ValueError("invalid")))
    with pytest.raises(RuntimeError, match="remove only the derived copy"):
        module.prepare_derivative(tmp_path / "original.mp4", target, "a" * 64)
    assert target.read_bytes() == b"truncated"
