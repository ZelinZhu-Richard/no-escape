# Public CCTV detection quality

Live CCTV uses **YOLO11s VisDrone, 640×640, confidence 0.40**, following the user's explicit AGPL-3.0 approval. Recorded demos retain YOLOX-Tiny and their existing caches. The live page shows the actual model, vehicle/person counts, inference time, source resolution, and update frequency. Labels toggle without restarting the stream.

## What changed

The earlier Tiny/416 profile frequently missed small, elevated-view vehicles. More frequent overlays alone did not improve detection. The selected traffic-trained model gives better visible coverage on the inspected 6th Street view. A wider player and optional labels make the boxes easier to inspect; **Open 6th Street live** selects that view without hiding other cameras.

Frame hashes, playback timestamps, bounded motion estimation, late-result rejection, and pause/seek/source cleanup remain enforced. Downloads occur only during explicit setup. Viewing a camera uses local CPU inference, with no cloud-model calls or recorded camera archive.

Only camera 689 filters detection centers inside its observed burned-in graphics: title `[0,0,0.46,0.08]` and timestamp `[0,0.93,0.52,1]`, normalized to the image. The UI shows dashed outlines and “Camera text regions excluded.” Camera identity and the exact policy enter the cache key and provenance. These are manually inspected graphics regions, not a calibrated road mask; they can need revision if the provider changes its graphics. Other cameras receive no such filter.

## Development comparisons

These are counts on identical saved development frames, **not accuracy, precision, or recall**. There are no new human evaluation labels. Higher counts alone do not prove correctness. The confidence/graphics settings were tuned during development, before any future evaluation.

| Camera | Frame | Previous Tiny | Compared YOLOX-M | Selected YOLO11s |
| --- | --- | ---: | ---: | ---: |
| TV316 — I-80 at 6th Street (37) | 352×240 | 4 vehicles | 13 vehicles | 17 vehicles |
| TV113 — SR-24 at Telegraph (689) | 640×480 | 3 vehicles | 5 vehicles | 10 vehicles, after 10 graphics exclusions |
| TVD33 — Bay Bridge SAS Tower West (53) | 352×240 | 1 apparent text/background false positive | 0 | 0 |

The selected model still misses much of the distant bridge traffic. Zero detections does not establish an empty road. Source 490 delivered a dark image despite an available playlist. Source quality and provider availability remain limits.

Three actual service calls using the final profile took **60.5, 54.4, and 47.7 ms** respectively on this machine (n=3). These are inference spot checks, not throughput guarantees. The built-in browser also played actual 6th Street HLS with YOLO11s overlays at roughly 6–6.5 updates/s; one observed result was 21 vehicles and 51 ms inference. Its current counts change with the moving traffic. Capture, encoding, transport, and drawing add latency beyond model inference. Telegraph also played with the two graphics exclusions disclosed and roughly 6–6.5 updates/s. Desktop and 390×844 overlay/video bounds matched, with no horizontal mobile overflow. Diagnostic images/results remain ignored locally.

## Setup and licenses

```sh
make detection-setup
make live-detect
make build
make serve
```

`make live-detect` downloads the pinned YOLO11s weights, verifies SHA-256, and writes `clearway/data/models/live-detector.json` with the explicit AGPL choice. Restart the operator after changing profile. The user approved this selection on November 7, 2026. Full AGPL text is included in the repository and built app; the UI links to license and corresponding source. Third-party notices remain separate. Model weights are restored separately, not committed.

Model source: [RISEF/yolov11s-visdrone, pinned revision](https://huggingface.co/RISEF/yolov11s-visdrone/tree/16d8d1709ae6fd7a9920398fbed5612e6208e0f0). Artifact: `weights/best.onnx`. SHA-256: `5abd18e5b630c330e68fe56b2bdc3875b10fbea07fe6912bde3cb9e68b58ca23`. Runtime: ONNX Runtime CPU, without the Ultralytics Python package.

`make live-detect-apache` explicitly selects official YOLOX-M instead (Apache-2.0 weights, SHA-256 `21ff6cfdeb53b013bac2249599e55f00bff3cfdfdab37ed7a4620818c1d15b3f`). This does not change the Clearway source license. With no selector, the service expects that M profile; it never downloads or silently substitutes a model. Missing weights or invalid configuration yield an unavailable detector without breaking the operator/replay workflow.
