#!/usr/bin/env python3
"""Restore only the licensed person-roadway replay, preserving source identity.

Media remains local and ignored. The source hash is mandatory; an existing
unknown original or invalid replay is never overwritten. Downloads have a
100 MB limit, a 90-second deadline, and a 10-second per-I/O timeout.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

MAX_BYTES = 100_000_000
DOWNLOAD_SECONDS = 90
IO_TIMEOUT_SECONDS = 10
ALLOWED_HOST = "videos.pexels.com"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def require_media_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    try:
        permitted = (
            parsed.scheme == "https" and parsed.hostname == ALLOWED_HOST
            and parsed.port in (None, 443)
            and parsed.username is None and parsed.password is None
            and not parsed.fragment
        )
    except ValueError:
        permitted = False
    if not permitted:
        raise ValueError("Source and redirects must use HTTPS on videos.pexels.com.")


class MediaRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        require_media_url(newurl)
        return super().redirect_request(request, fp, code, message, headers, newurl)


def checked_existing(path: Path, expected_hash: str) -> bool:
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlink at {path.name}.")
    if not path.exists():
        return False
    if not path.is_file() or digest(path) != expected_hash:
        raise RuntimeError(f"Existing {path.name} differs from the source checksum; refusing to overwrite it.")
    return True


def publish_new(temporary: Path, target: Path) -> None:
    """Publish a complete same-filesystem file without replacing a racing writer."""
    try:
        os.link(temporary, target)
    except FileExistsError:
        raise RuntimeError(f"Another file appeared at {target.name}; refusing to overwrite it.") from None


def download_original(url: str, target: Path, expected_hash: str) -> Path:
    require_media_url(url)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise ValueError("A complete SHA-256 source checksum is required.")
    if checked_existing(target, expected_hash):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(MediaRedirectHandler())
    request = urllib.request.Request(url, headers={"User-Agent": "ClearwayDemo/1.0 (licensed source media)"})
    deadline = time.monotonic() + DOWNLOAD_SECONDS
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".person-download-", suffix=".part", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with opener.open(request, timeout=IO_TIMEOUT_SECONDS) as response, temporary.open("wb") as output:
            require_media_url(response.geturl())
            length = response.headers.get("Content-Length")
            if length and (not length.isdigit() or int(length) > MAX_BYTES):
                raise RuntimeError("Source exceeds the 100 MB download limit or reports an invalid length.")
            total = 0
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Person footage download exceeded its time limit.")
                chunk = response.read(1024 * 1024)
                if time.monotonic() >= deadline:
                    raise TimeoutError("Person footage download exceeded its time limit.")
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise RuntimeError("Source exceeds the 100 MB download limit.")
                output.write(chunk)
        if digest(temporary) != expected_hash:
            raise RuntimeError("Source checksum mismatch; downloaded file was not accepted.")
        publish_new(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def validate_derivative(path: Path, ffmpeg: str, ffprobe: str) -> None:
    probe = json.loads(subprocess.check_output([
        ffprobe, "-v", "error", "-count_frames", "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,nb_read_frames",
        "-of", "json", str(path),
    ], timeout=30))
    streams = probe["streams"]
    if len(streams) != 1:
        raise ValueError("Replay must contain exactly one video stream and no audio.")
    stream = streams[0]
    shape = (stream["codec_type"], stream["codec_name"], stream["width"], stream["height"], int(stream["nb_read_frames"]))
    if shape != ("video", "h264", 720, 1280, 319):
        raise ValueError("Replay must contain all 319 H.264 frames at 720x1280.")
    numerator, denominator = map(int, stream["r_frame_rate"].split("/"))
    if denominator <= 0 or abs(numerator / denominator - 30) > 0.001:
        raise ValueError("Replay must retain the source's 30 fps playback speed.")
    if abs(float(probe["format"]["duration"]) - 10.633333) > 0.04:
        raise ValueError("Replay duration differs from the source.")
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(path),
        "-map", "0:v:0", "-an", "-f", "null", "-",
    ], check=True, capture_output=True, timeout=30)


def prepare_derivative(original: Path, target: Path, reference_hash: str) -> None:
    if target.is_symlink():
        raise RuntimeError("Replay must be a regular file, not a symlink.")
    if target.is_file() and digest(target) == reference_hash:
        return  # Byte-identical to the fully decoded reference derivative.
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe are needed to prepare or validate the replay.")
    if target.exists():
        try:
            validate_derivative(target, ffmpeg, ffprobe)
        except (ValueError, KeyError, IndexError, subprocess.SubprocessError) as error:
            raise RuntimeError("Existing replay is invalid; remove only the derived copy and rerun. The original is retained.") from error
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".person-preparing-", suffix=".mp4", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(original),
            "-map", "0:v:0", "-an", "-vf", "scale=720:1280", "-c:v", "libx264",
            "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary),
        ], check=True, capture_output=True, timeout=120)
        validate_derivative(temporary, ffmpeg, ffprobe)
        publish_new(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_poster(demo: Path, target: Path) -> None:
    if target.exists():
        return
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is needed to prepare the replay poster.")
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".person-poster-", suffix=".jpg", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", "4", "-i", str(demo), "-frames:v", "1", str(temporary)], check=True, capture_output=True, timeout=30)
        if temporary.stat().st_size == 0:
            raise RuntimeError("No poster frame was produced.")
        publish_new(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "docs/person-footage-candidate.json").read_text())
    if manifest["id"] != "person-roadway":
        raise ValueError("This restoration command supports only the selected person-roadway source.")
    media = root / "data/footage"
    original = download_original(manifest["download_url"], media / "person-roadway-original.mp4", manifest["original"]["sha256"])
    demo = media / "person-roadway-demo.mp4"
    prepare_derivative(original, demo, manifest["replay"]["sha256"])
    prepare_poster(demo, media / "person-roadway-poster.jpg")
    receipt = {
        "source_id": "person-roadway", "source_sha256": digest(original),
        "local_demo_sha256": digest(demo), "reference_demo_sha256": manifest["replay"]["sha256"],
        "note": "Original checksum verified. Encoding bytes can vary with ffmpeg versions; nonidentical derivatives require metadata and full decode validation. No evaluation labels created.",
    }
    (root / "data/person-footage-download-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Ready: {manifest['title']} — {manifest['author']}")
    print(f"License: {manifest['license_url']}")
    print("Person in roadway replay verified locally. Media remains excluded from Git.")


if __name__ == "__main__":
    main()
