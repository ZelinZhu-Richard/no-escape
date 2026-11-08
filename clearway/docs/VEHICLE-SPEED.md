# Vehicle confidence and approximate speed

Open **Public CCTV → Open speed example** to play **TVA43 — I-580 at Grand Lakeshore** (`caltrans-d4-285`). Live vehicle labels show detector confidence beside each box. On this example camera, a stable track inside the outlined near-right roadway can also show **est N mph**. A dash means unavailable, not zero. Hide labels or hide the speed area without restarting the video.

The mph feature is experimental. The user accepted an approximate scale; there are no surveyed road distances or known vehicle speeds for validation. Detector confidence is the model's detection score, not a calibrated probability of correctness or confidence in the mph value. Speeds are display-only and do not trigger or change incident alerts, evidence, or responder briefs.

## Scale and view assumptions

`web/src/trafficSpeedCalibration.ts` contains a hand-aligned road quadrilateral for the inspected 720×480, square-pixel view. It assumes a 36 ft width (three 12 ft lanes) and a 120 ft length (about three 40 ft dash-plus-gap cycles), mapped to a plane using a homography. The [2026 California MUTCD marking guidance](https://dot.ca.gov/-/media/dot-media/programs/safety-programs/documents/ca-mutcd/2026/camutcd-2026-3a.pdf) describes usual 10 ft lines and 30 ft gaps, with alternatives allowed. It does **not** establish TVA43's actual dimensions. Road curvature, slope, imperfect anchors and the box's bottom-center approximation can bias the result.

Only this polygon and camera are enabled. Opposite-carriageway and distant vehicles, snapshots, other cameras, and unreliable tracks have no mph estimate. Do not transfer the preset to another camera view. To make this a measurement, obtain surveyed reference points, recalibrate the image plane, and compare against independently measured vehicle speeds over representative clips.

Four small static-background signatures in `trafficSpeedReference.json` help detect a different camera view. At least three must match, with aspect, correlation, brightness and contrast checks. Missing/mismatched signatures hide all speeds. This is a conservative heuristic, not guaranteed PTZ-motion detection; a small undetected camera movement can still bias speeds. Inspect and replace the preset/reference if the provider changes the view. Source imagery and downloaded video are not committed.

## Tracking and timing

The estimator uses actual high-confidence, confirmed ByteTrack observations and exact video timestamps. It fits metric motion over one to two seconds, requires at least four observations, and rejects missing/low/tentative tracks, duplicate frames, invalid input, implausible jumps and unstable fits. Source, run, stream, model configuration, dimensions, pause, seek, stale frames and view mismatch clear continuity. Display prediction between observations never feeds speed calculation. Existing overlay freshness limits still apply.

TVA43 alone adds a bounded geometric recovery after ordinary high-score ByteTrack matching. It considers only recent active/tentative vehicle tracks and current high-score observations of the same class. Size, overlap, distance, and media/wall-time gates plus two-way ambiguity margins reject uncertain pairings. Lost tracks and low-score boxes cannot enter this recovery. The response reports the camera-specific `association_policy`, recovery count, and each recovered observation's association. Other cameras retain ordinary ByteTrack behavior.

This improves availability but does not establish identity accuracy. IDs remain short-lived and mph appears intermittently as vehicles build adequate histories. TVA43's burned-in top-left timestamp is excluded by detection center at `[0,0,0.50,0.08]`; this explicit graphics policy affects detector counts and is recorded in cache provenance. The road is not masked.

## Development verification

A bounded 12-second genuine TVA43 segment supplied 72 browser-equivalent frames at 6 fps (640×427, JPEG quality 80). A fair comparison gives both association policies the exact same 1,872 high observations and full low-confidence candidate pool after the timestamp exclusion:

| Development diagnostic | Ordinary association | TVA43 recovery |
| --- | ---: | ---: |
| High observations inside the assumed road area | 136 | 136 |
| Track IDs represented by those observations | 135 | 70 |
| Confirmed high observations inside the area | 2 | 72 |
| Numeric speed observations | 0 | 2 |
| IDs with a numeric speed | 0 | 1 |

Those two estimates were approximately 49 mph under the assumed scale. These are availability/continuity counts on development footage, **not speed accuracy, recall, unique-vehicle counts or verified identities**. Fragmentation and sparse estimates remain real limitations. The built-in browser also displayed a numeric estimated speed on genuine playing TVA43 video, with detector confidence and unavailable values for other tracks.

Synthetic tests exercise known metric trajectories and failure cases; separate scene-signature and hook tests verify view matching, resets, exact-frame binding and display behavior. No cloud inference, training, new model download or natural-incident evaluation is involved. See the latest root [MORNING_REPORT.md](../../MORNING_REPORT.md) for full check results and startup instructions.

The local diagnostic accepts an already permitted short clip and installed weights, never downloads media or creates alerts:

```sh
clearway/.venv/bin/python clearway/scripts/compare_live_speed.py \
  --video .local/speed-tva43/dev-sample.mp4 \
  --output .local/speed-tva43/speed-diagnostic --fps 6 --compare-baseline
```

The clip and diagnostic outputs are ignored local development artifacts and are not restored by this command. Add `--replay-observations .local/speed-tva43/speed-diagnostic/observations.json` with a different output directory to compare the saved full high/low pool without running inference again.
