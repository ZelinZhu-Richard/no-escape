# Visible computer vision

Clearway runs source-specific pinned local models: the approved AGPL-3.0 YOLO11s VisDrone model for Dense traffic, and official Apache-2.0 YOLOX-Tiny for the other recorded sources. It saves timestamped boxes with the source hash, weights hash, preprocessing version, threshold, sampling rate, and generation time. The browser overlays normalized boxes at the matching playback time, accounting for portrait-video letterboxing and seeking. It labels this **YOLO · saved detections** and names the actual model. No fake boxes or fixture results can satisfy the detector cache.

From the project root:

```sh
make detection-setup
make live-detect
make detect
```

Explicit setup prepares the checksum-pinned models. Inference runs on CPU at four samples per second; serving/replay requires no detector network call. The command skips missing optional clips; explicit selection of a missing source fails. Run a single source with `clearway/.venv/bin/python clearway/scripts/run_detection.py --source person-roadway`. To rebuild Dense traffic after installing its weights, use `clearway/.venv/bin/python clearway/scripts/run_detection.py --source traffic-jam --force`. This replay command does not change live-camera settings or substitute Tiny when traffic weights are missing. Caches and weights remain ignored under `clearway/data/`.

The November 7 Dense traffic correction followed a playback check: the video decoded normally but Tiny missed most visible cars (only six boxes across 45 samples). Regenerating the same 45 samples with VisDrone produced 69/41/51 vehicle boxes at 1.007/4.007/8.007 seconds, versus zero at those times with Tiny. Across all samples the range was 39–76, with median 51. These are development counts, not unique vehicles or measured accuracy. Visual inspection found improved vehicle coverage but also false boxes on striped lane markings and overlapping boxes. The full 336-frame video decoded; model inference median was 55.207 ms and maximum 303.013 ms (n=45). Other recorded-source caches remain unchanged.

Replay labels have their own toggle. Dense traffic starts with boxes visible and labels hidden to keep the crowded roadway readable; other scenes retain labeled boxes by default. Browser verification confirmed advancing playback with real saved boxes, working label toggles and the completed fixture message. Local proof: `clearway/data/verification/dense-traffic-fixed.jpg`.

## Dense traffic tiled detection — November 7, 2026

Dense traffic now prepares saved boxes from original 1920×1080 pixels using **768px crops with nominal 25% overlap plus a full-frame pass** (six crops plus one full pass per sample). Edge crops can overlap more to cover the complete image. Boxes clipped by internal crop edges are rejected, coordinates are mapped back to the original frame, and conservative IoU/containment checks suppress duplicates. A 0.50 output cutoff reduces weaker hypotheses before merging. Person/vehicle hypotheses are kept separate. These settings and their digest enter cache provenance; stale or mismatched reports are rejected. Other sources keep their existing Tiny caches.

Same-frame development comparison after one warmup:

| Mode | Boxes at 1.007 / 4.007 / 8.007s | Median processing time, n=3 |
| --- | --- | ---: |
| Previous full frame, 0.40 | 69 / 41 / 51 | 45.6ms |
| Full frame, 0.50 control | 55 / 30 / 41 | 45.7ms |
| Selected tiled, 0.50 | 88 / 60 / 68 | 324.2ms |

Visual inspection found additional visible vehicles on both carriageways and the lower road. Roof/background false positives, ambiguous striped patterns, overlaps and occluded misses remain. More boxes alone do not establish better accuracy. These three frames informed development settings; they are not a holdout, human labels, or precision/recall evaluation. The latency tradeoff is paid once during local cache preparation; recorded playback reads saved results.

All 336 decoded frames yielded 45 samples at 4fps. Preparing the final cache took 17.074s, with sample processing median 353.848ms and maximum 695.750ms (n=45), 315 total model passes. Vehicle counts ranged 55–91, median 66. These are per-frame predictions, not unique vehicles.

```sh
clearway/.venv/bin/python clearway/scripts/run_detection.py --source traffic-jam --force
clearway/.venv/bin/python clearway/scripts/compare_dense_tiling.py --tile-sizes 768 --output .local/cctv-quality/dense-tiling/check
```

Use `--dense-strategy full-frame --force` for an explicit full-frame cache fallback. Tiling is a spatial crop/inference/merge implementation, following the [slice-detect-merge approach](https://obss.github.io/sahi/guides/sliced-inference/); no SAHI package or model training is added. There is no upscaling or synthetic detail enhancement.

## What the counter means

The gate divides the clip into two-second windows. It passes the first window, a ten-second heartbeat, any window with a detected person, or a vehicle-count change of at least two. Otherwise it marks the window suppressed. The comparison baseline is **one VLM call per two-second window**. It runs in shadow mode: the operator's Gemini command remains independent, and no actual paid call is silently suppressed.

Measured preparation results on November 7, 2026:

| Clip | Genuine sampled frames | Hypothetical requests avoided / baseline windows |
| --- | ---: | ---: |
| Road obstruction | 45 | 4 / 6 |
| Person in roadway | 43 | 0 / 6 |
| Street traffic | 140 | 0 / 18 |
| Dense traffic (VisDrone correction) | 45 | 1 / 6 |

These are deterministic gate decisions on development footage, not human-labeled accuracy or proven fleet savings. Person detections conservatively pass all windows in the person/street clips. No road ROI, calibrated lane geometry, motion baseline, natural-event recall, or congestion diagnosis is implied. Actual Gemini request counts and estimated spend appear separately in the console.

## Scene limits

At four seconds in the person clip, the central pedestrian is detected at 0.82 confidence. This is a model confidence score, not the probability of danger. Some vehicles are misclassified (an SUV is labeled truck), and occlusion causes detections to vary. The scene shows an upright person among road vehicles; it does not establish injury or an emergency.

YOLO boxes are genuine inference; the default incident narrative remains a visibly labeled fixture. Dense traffic's fixture produces no candidate, and the evidence panel now says so after completion instead of continuing to ask the operator to start. Dense traffic alone does not establish an incident. Gemini has its own genuine cache and the unchanged $5/five-attempt budget. The expanded person schema and source-specific frame sampling are prepared, but no Gemini success is claimed without a real response. Human confirmation changes the review status, not the provenance or measured accuracy.

Voice reads the selected brief, source/provenance, review status, and unknowns on demand using browser speech synthesis. Stop it with the same control; changing/resetting the incident cancels speech. It does not dispatch anyone or add facts. Browser support/audio output must be checked on the expo machine.
