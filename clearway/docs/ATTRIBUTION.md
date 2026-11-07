# Clearway attribution

## Project inspirations

- [God's Eye View](https://github.com/bilawalsidhu/gods-eye-view), bilawalsidhu: inspiration for a spatial interface using Cesium and 3D city imagery. Its reviewed [license](https://github.com/bilawalsidhu/gods-eye-view/blob/c0a5d4141d4fa6f7648910cedd98654f2381989d/LICENSE) distinguishes source-code rights from third-party assets. No GEV application code was copied into Clearway.
- [HawkWatch / Treehacks2025](https://github.com/Grace-Shao/Treehacks2025), Grace-Shao and contributors: inspiration for visual observations and timestamped evidence review. A license file was not found in the reviewed tree; do not assume permission to copy its code or bundled videos. No HawkWatch application code was copied into Clearway.

Clearway is a fresh implementation. Exact reviewed source files and revisions are in `REFERENCES.md`. Hackathon eligibility is separate from software licensing; record any future copied code, pinned revision, and applicable notices before submission.

Expo reference checkout: God's Eye View is cloned locally under ignored `.local/references/gods-eye-view`, pinned at `ca6eace79e60f29770597ea26871d5427b504b2b`. Its source license does not grant rights to every bundled dataset; no GEV code or datasets were imported. See `MAP-SETUP.md`.

## Local object detection

The detector uses [Megvii YOLOX](https://github.com/Megvii-BaseDetection/YOLOX), official `0.1.1rc0` YOLOX-Tiny ONNX weights, SHA-256 `427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7`. Preprocessing and grid decoding follow its [ONNX example](https://github.com/Megvii-BaseDetection/YOLOX/tree/main/demo/ONNXRuntime), Apache-2.0, Copyright (c) Megvii, Inc. and its affiliates. The full notice is retained in `clearway/licenses/YOLOX-APACHE-2.0.txt` from the repository root. Clearway adds provenance validation, normalized replay overlays, and an explicitly hypothetical gate comparison. Keep the notice with redistributed detector code; downloaded weights remain local.

Optional detection requirements are pinned separately: NumPy 2.5.4, OpenCV headless 4.14.0.94, and ONNX Runtime 1.31.1. Their installed distributions include their own licenses and third-party notices. The serving process reads prepared detection JSON without loading those inference libraries.

## Person-in-roadway footage

**Busy Indian Highway with Traffic and Pedestrians** — md Jahangir alam / [Pexels source](https://www.pexels.com/video/busy-indian-highway-with-traffic-and-pedestrians-35532487/), [Pexels License](https://www.pexels.com/license/). Full source metadata, original/derivative hashes, and limits are in `person-footage-candidate.json`.

Replay changes: downscaled 2160×3840 to 720×1280 H.264, no audio, all 319 frames with original duration, framing, and speed retained. Display creator/source/license links. This roadside stock clip is not verified municipal CCTV. It shows an upright person among vehicles, not an established injury, collapse, collision, or emergency. Do not imply endorsement or fault by the people shown; do not redistribute the raw clip as standalone stock.

## Installed software and font

Versions and license declarations below were checked against `web/package-lock.json`, installed package metadata/license files, and the installed Python distributions on November 7, 2026. This is a core dependency summary, not a complete transitive license inventory.

| Component | Installed version | License verified in installed files |
| --- | --- | --- |
| React / React DOM | 19.3.1 / 19.3.1 | MIT; Meta Platforms, Inc. and affiliates |
| CesiumJS | 1.147.0 | Apache-2.0; CesiumJS Contributors. Installed engine 26.5.0 and widgets 16.3.1 also declare Apache-2.0. |
| qrcode.react | 4.2.0 | ISC; Paul O’Shannessy. Its bundled QR Code generator credits Project Nayuki under MIT. |
| hls.js | 1.7.4 | Apache-2.0; installed package license retained by the bundled dependency notice build. Used for official public HLS playback where native playback is unavailable. |
| Manrope Variable (`@fontsource-variable/manrope`) | 5.2.8 package | SIL Open Font License 1.1; The Manrope Project Authors |
| FastAPI / Pydantic | 0.162.0 / 2.14.3 | MIT |
| Starlette / Uvicorn | 1.10.0 / 0.54.0 | BSD-3-Clause |
| python-dotenv | 1.2.4 | BSD-3-Clause, checked in installed distribution metadata |
| Vite / React Vite plugin / static-copy plugin | 8.3.6 / 6.2.1 / 4.1.1 | MIT; Vite's installed license file also lists its bundled third-party licenses |
| TypeScript | 5.9.3 | Apache-2.0; retain its third-party notice file |
| HTTPX / pytest (test dependencies) | 0.28.1 / 9.2.0 | BSD-3-Clause / MIT |
| Vitest / jsdom (frontend test dependencies) | 5.1.0 / 31.0.0 | MIT / MIT, checked in installed package metadata |

Evidence: each frontend package's `LICENSE`, `LICENSE.md`, or `LICENSE.txt` under `web/node_modules/`; Python `*.dist-info/licenses/` files in `.venv/`. Keep dependency notices with redistributed bundles rather than treating this summary as a replacement for the license texts.

The Vite build is configured to emit `assets/licenses/bundled-dependencies.md` and copy `cesium-LICENSE.md`, Cesium's third-party JSON notices, and `manrope-OFL.txt` into `web/dist/assets/licenses/`. Preserve that folder when distributing the built frontend. Final build verification is recorded in `MORNING_REPORT.md`.

The UI imports Manrope through Fontsource and serves its font assets locally. Font copyright: **Copyright 2019 The Manrope Project Authors (https://github.com/sharanda/manrope)**. Its full OFL text is in `web/node_modules/@fontsource-variable/manrope/LICENSE`; preserve that copyright and license with distributed font files. The font remains OFL-1.1, independently of Clearway's application source license.

## Selected positive footage

**Utility Workers Clearing Storm Debris on Road** — [Ibrahim Bennett](https://www.pexels.com/@ibrahim-bennett-2187162/) / [Pexels source](https://www.pexels.com/video/utility-workers-clearing-storm-debris-on-road-30567549/), [Pexels License](https://www.pexels.com/license/).

Original: `data/footage/storm-obstruction-30567549-original.mp4`.
Demo: `data/footage/road-obstruction-demo.mp4`.

Changes: resized from 3840×2160 to 1920×1080 and re-encoded to H.264; original duration and speed retained. Poster/contact sheet: extracted and resized frames. The original download is unchanged.

Display credit: **Video: Ibrahim Bennett / Pexels — licensed recorded replay; resized and re-encoded.** Link to the source and license in the evidence view. Retain the [Pexels terms](https://www.pexels.com/terms-of-service/); do not redistribute raw footage as standalone stock or imply endorsement. This asset is not Creative Commons and is not relicensed as project code.

## Earlier development clips

| Clip | Creator / source | License | Changes |
| --- | --- | --- | --- |
| Traffic Jam | Melvin Loi, [Flickr original](https://www.flickr.com/photos/54943237@N04/51068986922/), [Commons](https://commons.wikimedia.org/wiki/File:Traffic_Jam.webm) | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/) | Original unchanged; review sheet uses resized extracted frames. Preserve applicable ShareAlike terms for adapted media. |
| Street traffic | Editor (YouTube), [original](https://www.youtube.com/watch?v=_7sCYyxw4Ic), [Commons](https://commons.wikimedia.org/wiki/File:Street_traffic.webm) | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) | Original unchanged; review sheet uses resized extracted frames. |

Three additional Pexels repair/tire clips were inspected but not selected. Their creator/source/license records are retained under `reviewed_alternatives` in `footage-sources.json`. Keep them local rather than implying their inclusion in the submitted demo.

All paths here are relative to `clearway/`. Full provenance and checksums are in `footage-sources.json`. None of these clips is a live North Carolina observation, and none supplies calibrated coordinates for the selected obstruction.

## Live CCTV detector profiles

Public-camera inference now selects **YOLO11s VisDrone**, after the user's explicit AGPL approval on November 7, 2026. Source: [RISEF's pinned model revision](https://huggingface.co/RISEF/yolov11s-visdrone/tree/16d8d1709ae6fd7a9920398fbed5612e6208e0f0), including the model card and training configuration. Artifact: `weights/best.onnx`; SHA-256: `5abd18e5b630c330e68fe56b2bdc3875b10fbea07fe6912bde3cb9e68b58ca23`. The model card declares **AGPL-3.0**. Clearway uses ONNX Runtime; no Ultralytics Python package is bundled. Full AGPL text is in the root LICENSE and `clearway/licenses/AGPL-3.0.txt`, and is included in the web build. Operator/responder pages link to the license and public corresponding source. Existing third-party notices remain in place.

Official **YOLOX-M 0.1.1rc0** remains an explicitly selectable alternative: SHA-256 `21ff6cfdeb53b013bac2249599e55f00bff3cfdfdab37ed7a4620818c1d15b3f`, from the [Megvii YOLOX release](https://github.com/Megvii-BaseDetection/YOLOX/releases/tag/0.1.1rc0), Apache-2.0. The existing Apache notice covers the referenced preprocessing/grid-decoding patterns. Recorded replay weights and caches remain YOLOX-Tiny. Selecting Apache model weights does not change the Clearway source license.

No model weights, downloaded camera frames, or source media are published in this repository. See [CCTV-QUALITY.md](CCTV-QUALITY.md) for setup and detection limits.
