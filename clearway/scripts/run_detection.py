#!/usr/bin/env python3
"""Prepare genuine, pinned YOLOX overlays without any paid model calls."""
from pathlib import Path
import argparse
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.configuration import load_local_environment  # noqa: E402
from api.detection import DetectionError, DetectionService, download_model, prepare_detections  # noqa: E402
from api.sources import SOURCES, media_path  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=[*SOURCES, "all"], default="road-obstruction")
    parser.add_argument("--fps", type=float, default=4.0)
    parser.add_argument("--download-model", action="store_true", help="Download checksum-pinned official YOLOX weights if missing.")
    parser.add_argument("--force", action="store_true", help="Recompute an existing genuine cache.")
    args = parser.parse_args()
    load_local_environment()
    data = Path(os.environ.get("CLEARWAY_DATA_DIR", ROOT / "data"))
    try:
        sources = list(SOURCES) if args.source == "all" else [args.source]
        if args.source == "all":
            unavailable = [source for source in sources if media_path(data, source, "video") is None]
            for source in unavailable:
                print(json.dumps({"source_id": source, "status": "skipped", "message": "Registered footage is not downloaded."}), flush=True)
            sources = [source for source in sources if source not in unavailable]
            if not sources:
                raise DetectionError("No registered footage is available; restore licensed footage first.")
        if args.download_model:
            download_model(data)
        service = DetectionService(data)
        for source in sources:
            report = service.get(source)
            if args.force or report["status"] != "available" or report["sample_fps"] != args.fps:
                report = prepare_detections(data, source, sample_fps=args.fps)
            print(json.dumps({"source_id": source, "status": report["status"], "model": report["model"],
                              "processing": report["processing"], "sample_fps": report["sample_fps"],
                              "gate": {key: value for key, value in report["gate"].items() if key != "windows"}}, indent=2), flush=True)
        return 0
    except DetectionError as error:
        print(json.dumps({"status": "unavailable", "message": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
