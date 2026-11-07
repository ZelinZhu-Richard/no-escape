import importlib.util
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location("fetch_footage", Path(__file__).resolve().parents[1] / "scripts/fetch_footage.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_interrupted_transcode_does_not_leave_final_copy(tmp_path, monkeypatch):
    source = tmp_path / "original.mp4"
    source.write_bytes(b"test source")
    target = tmp_path / "demo.mp4"
    monkeypatch.setattr(module.shutil, "which", lambda name: name)

    def interrupted(command, **kwargs):
        Path(command[-1]).write_bytes(b"truncated")
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(module.subprocess, "run", interrupted)
    with pytest.raises(subprocess.CalledProcessError):
        module.prepare_derivative(source, target, "reference")
    assert not target.exists()
    assert list(tmp_path.glob(".demo-preparing-*")) == []
    assert source.read_bytes() == b"test source"


def test_existing_invalid_derivative_is_not_treated_as_ready(tmp_path, monkeypatch):
    target = tmp_path / "demo.mp4"
    target.write_bytes(b"truncated")
    monkeypatch.setattr(module.shutil, "which", lambda name: name)
    monkeypatch.setattr(module, "validate_derivative", lambda *args: (_ for _ in ()).throw(ValueError("invalid")))
    with pytest.raises(RuntimeError, match="Remove only this derived copy"):
        module.prepare_derivative(tmp_path / "original.mp4", target, "reference")
    assert target.read_bytes() == b"truncated"
