#!/usr/bin/env python3
"""Explicitly install and select one pinned local CCTV detector profile."""
from pathlib import Path
import argparse
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.configuration import load_local_environment  # noqa: E402
from api.traffic_detection import DEFAULT_PROFILE, PROFILES, TrafficDetectionError, install_profile  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=tuple(PROFILES), default=DEFAULT_PROFILE)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--from-file", type=Path, help="Copy an existing local file after checking the pinned digest.")
    source.add_argument("--download", action="store_true", help="Explicitly download the selected profile from its pinned source.")
    parser.add_argument("--accept-agpl", action="store_true", help="Explicitly select the optional AGPL-3.0 licensed profile; does not replace legal/license review.")
    parser.add_argument("--camera-id", help="Select this profile for one camera only; preserve the default and other camera selections.")
    args = parser.parse_args()
    load_local_environment()
    data_dir = Path(os.environ.get("CLEARWAY_DATA_DIR", ROOT / "data"))
    try:
        profile = install_profile(data_dir, args.profile, from_file=args.from_file,
                                  download=args.download, accept_agpl=args.accept_agpl,
                                  camera_id=args.camera_id)
        print(json.dumps({"status": "prepared", "profile": profile.id, "model": profile.name,
                          "license": profile.license, "weights_sha256": profile.sha256,
                          "camera_id": args.camera_id,
                          "message": "Restart the operator to load this profile. Replay YOLO remains separate."}, indent=2))
        return 0
    except TrafficDetectionError as error:
        print(json.dumps({"status": "unavailable", "message": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
