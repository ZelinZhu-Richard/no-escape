# Selected demo footage

Use **road-obstruction-demo.mp4** for the positive replay. It shows utility trucks occupying a road, yellow tape spanning the roadway, and branches/debris on the pavement. This is a visible **road obstruction / utility work zone**. It does not establish an engine stall, crash, injuries, or a newly occurring incident.

| Item | Detail |
| --- | --- |
| Source | [Utility Workers Clearing Storm Debris on Road](https://www.pexels.com/video/utility-workers-clearing-storm-debris-on-road-30567549/) |
| Creator | [Ibrahim Bennett](https://www.pexels.com/@ibrahim-bennett-2187162/) |
| License | [Pexels License](https://www.pexels.com/license/), checked November 7, 2026 |
| Original | `data/footage/storm-obstruction-30567549-original.mp4`, 3840×2160 |
| Demo copy | `data/footage/road-obstruction-demo.mp4`, 1920×1080, H.264, 11.8 MB |
| Duration | 11.1111 seconds; 333 frames at approximately 29.97 fps |
| Changes | Resized and re-encoded; full length and original speed retained |
| Evidence poster | `data/footage/road-obstruction-poster.jpg`, extracted at 5 seconds |
| Review | Eleven sampled frames plus a full-size frame inspected; original transcoded and demo fully decoded without errors |
| Location / capture time | Unknown; the source page's date is not a verified capture timestamp |
| Model validation | Not run; the reference scenario is not a model result |

Paths above are relative to `clearway/`.

## Demo behavior

1. Play the clip with **LICENSED RECORDED REPLAY** visible.
2. Submit actual frames at, for example, 1, 4, and 8 seconds to the selected vision model. Retain timestamps and the returned observations.
3. The desired candidate is **Possible road obstruction / utility work zone**, supported by visible trucks, tape, and debris. Show uncertainty and require operator confirmation. Do not hardcode a successful model result.
4. Keep location unknown. If the expo needs a map marker, label its placement **simulated**; this clip cannot validate the same-site projection experiment.
5. Reset temporal state on replay restart. Repeated loops do not extend the observed duration or provide independent evaluation examples.

The obstruction is already present at the start. Use this to demonstrate evidence review and handoff, not incident onset detection, clearance, or population-level precision. A frame-to-result processing time can be measured separately.

The expected observations and acceptance checks are recorded in `demo-scenario.json`. Source details and SHA-256 checksums are in `footage-sources.json`.

## Credit and reuse

Suggested credit:

> Utility Workers Clearing Storm Debris on Road — Ibrahim Bennett / Pexels. Pexels License. Resized and re-encoded for this recorded demo.

The [license](https://www.pexels.com/license/) permits free use and modification; credit is appreciated. The [terms](https://www.pexels.com/terms-of-service/) restrict standalone redistribution, misleading endorsement, and commercial uses involving depicted brands. Keep downloads local/ignored and integrate footage into the app's evidence/review experience. This is not an unrestricted advertising clearance or permission to relicense the media as project code. Preserve the source and license links with the replay.

## Other reviewed clips

The three downloaded repair/tire scenes were not selected: one mostly hides the vehicle, one is a moving close-up under the hood, and one may be in a parking/rest area. Their titles alone do not establish a blocked travel lane. Provenance and rejection reasons are retained in the manifest.

The earlier `street-traffic.webm` remains a normal-traffic control candidate, pending complete labeling. `traffic-jam.webm` remains a congestion candidate. Their separate Creative Commons terms still apply.
