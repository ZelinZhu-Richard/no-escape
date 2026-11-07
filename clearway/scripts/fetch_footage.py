#!/usr/bin/env python3
"""Restore licensed demo media from its original source, not from GitHub.

Downloads the selected obstruction clip and optional control; verifies original
SHA-256 hashes. The 1080p derivative is created locally with ffmpeg.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_derivative(path: Path, ffmpeg: str, ffprobe: str) -> None:
    probe = json.loads(subprocess.check_output([ffprobe, "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "format=duration:stream=width,height,codec_name,nb_read_frames", "-of", "json", str(path)], timeout=30))
    stream = probe["streams"][0]
    if (stream["width"], stream["height"], stream["codec_name"], int(stream["nb_read_frames"])) != (1920, 1080, "h264", 333):
        raise ValueError("Derivative must contain all 333 H.264 frames at 1920x1080")
    if abs(float(probe["format"]["duration"]) - 11.1111) > .05:
        raise ValueError("Derivative duration does not match the source")
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(path), "-map", "0:v:0", "-an", "-f", "null", "-"], check=True, capture_output=True, timeout=30)


def prepare_derivative(original: Path, target: Path, reference_hash: str) -> None:
    if target.exists() and digest(target) == reference_hash:
        return  # Identical to the already fully decoded reference derivative.
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe are needed to prepare or validate the demo copy")
    if target.exists():
        try:
            validate_derivative(target, ffmpeg, ffprobe)
        except (ValueError, KeyError, IndexError, subprocess.SubprocessError) as error:
            raise RuntimeError(f"Existing {target.name} is invalid. Remove only this derived copy and rerun; the verified original is retained.") from error
        return
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".demo-preparing-", suffix=".mp4", delete=False) as output:
        temporary = Path(output.name)
    try:
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(original), "-map", "0:v:0", "-an", "-vf", "scale=1920:1080", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary)], check=True)
        validate_derivative(temporary, ffmpeg, ffprobe)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-control", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "docs/footage-sources.json").read_text())
    selected = next(item for item in manifest["clips"] if item["id"] == "road-obstruction")
    media = root / "data/footage"
    media.mkdir(parents=True, exist_ok=True)
    allowed_hosts = {"videos.pexels.com", "upload.wikimedia.org"}

    def download(url: str, name: str, checksum: str) -> Path:
        assert Path(name).name == name, "Filename must not contain a path"
        parsed = urllib.parse.urlsplit(url)
        assert parsed.scheme == "https" and parsed.hostname in allowed_hosts
        target = media / name
        if target.exists():
            if digest(target) != checksum:
                raise SystemExit(f"Existing {name} differs from the source checksum; refusing to overwrite it.")
            print(f"Verified existing {name}", flush=True)
            return target
        partial = target.with_suffix(target.suffix + ".part")
        print(f"Downloading {name} from {parsed.hostname}", flush=True)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ClearwayDemo/1.0 (licensed source media)"})
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as output:
                if urllib.parse.urlsplit(response.url).hostname not in allowed_hosts:
                    raise RuntimeError("Unexpected media redirect")
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 200 * 1024 * 1024:
                        raise RuntimeError("Source exceeds the 200 MiB download limit")
                    output.write(chunk)
            if digest(partial) != checksum:
                raise RuntimeError("Source checksum mismatch; downloaded file was not accepted")
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        return target

    print(f"Source: {selected['title']} — {selected['creator']}")
    print(f"License: {selected['license_url']}; reuse notes: docs/ATTRIBUTION.md")
    original = download(selected["download_url"], selected["original"]["filename"], selected["original"]["sha256"])
    demo = media / "road-obstruction-demo.mp4"
    ffmpeg = shutil.which("ffmpeg")
    prepare_derivative(original, demo, selected["demo"]["sha256"])
    poster = media / "road-obstruction-poster.jpg"
    if not poster.exists() and ffmpeg:
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-n", "-ss", "5", "-i", str(demo), "-frames:v", "1", str(poster)], check=True)
    if args.with_control:
        control = next(item for item in manifest["clips"] if item["id"] == "street-traffic")
        print(f"Control license: {control['license_url']}")
        download(control["download_url"], control["filename"], control["sha256"])
    receipt = {
        "source_sha256": digest(original),
        "local_demo_sha256": digest(demo),
        "reference_demo_sha256": selected["demo"]["sha256"],
        "note": "Original checksum is verified. Re-encoding bytes can vary with ffmpeg versions; local derivative hash is recorded separately.",
    }
    (root / "data/footage-download-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("Licensed replay is available locally. Do not commit the media files.")


if __name__ == "__main__":
    main()
