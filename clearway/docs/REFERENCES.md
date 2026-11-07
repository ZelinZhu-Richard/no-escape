# Reference projects and design lessons

Reviewed November 7, 2026. These are references for Clearway's new implementation, not application code incorporated into it. The source observations below do not establish that those projects' complete deployments or model claims were independently tested.

## God's Eye View

Repository: [bilawalsidhu/gods-eye-view](https://github.com/bilawalsidhu/gods-eye-view). Reviewed tree: `c0a5d4141d4fa6f7648910cedd98654f2381989d`.

- **Map selection should identify one stable source.** The [CCTV selection module](https://github.com/bilawalsidhu/gods-eye-view/blob/c0a5d4141d4fa6f7648910cedd98654f2381989d/src/layers/cctv/selection.js) keeps an active camera ID, avoids repeating an already-completed activation, and separates scene picking from camera activation. Clearway adopts the interaction principle: selecting a marker/card opens that incident's evidence without creating another incident or rebuilding the viewer.
- **Show source and fetch state beside imagery.** The [CCTV panel](https://github.com/bilawalsidhu/gods-eye-view/blob/c0a5d4141d4fa6f7648910cedd98654f2381989d/src/ui/views/panels/CctvPanel.vue) exposes source badges and loading/error state alongside a frame/video surface and controls. Clearway uses its own independent source, analysis, and review labels so recorded footage and fixtures remain visible.
- **Calibration is a separate capability.** That same panel includes camera pose and calibration controls. Clearway's overnight marker is simulated; we do not equate a map pin with calibrated lane projection or copy GEV's projection subsystem into this build.

The reviewed [license](https://github.com/bilawalsidhu/gods-eye-view/blob/c0a5d4141d4fa6f7648910cedd98654f2381989d/LICENSE) grants MIT rights to source code while separately identifying third-party data and assets. It does not grant blanket rights to imagery, datasets, models, or provider services. Event eligibility is a different question from that software license.

## HawkWatch / Treehacks2025

Repository: [Grace-Shao/Treehacks2025](https://github.com/Grace-Shao/Treehacks2025). Reviewed tree: `de00cc10eb577bd1d1e56c8d4b78f5a77827201e`.

- **Connect observations to source frames.** The [real-time analysis action](https://github.com/Grace-Shao/Treehacks2025/blob/de00cc10eb577bd1d1e56c8d4b78f5a77827201e/app/pages/realtimeStreamPage/actions.ts) sends an image to Gemini and parses event descriptions/timestamps. Clearway uses its own constrained road-obstruction schema, actual sample timestamps, and explicit unknowns. The referenced model ID and prompt are historical implementation details, not a recommendation for current access or pricing.
- **Make evidence navigable.** The [saved-video detail page](https://github.com/Grace-Shao/Treehacks2025/blob/de00cc10eb577bd1d1e56c8d4b78f5a77827201e/app/pages/video/%5Bid%5D/page.tsx) links timestamp entries to video playback and a timeline. Clearway's evidence panel follows the useful interaction: an observation should let an operator inspect the corresponding moment.
- **Keep mocks unmistakable.** The [generic analysis API route](https://github.com/Grace-Shao/Treehacks2025/blob/de00cc10eb577bd1d1e56c8d4b78f5a77827201e/app/api/analyze/route.ts) returns hard-coded mock timestamps. That route is not evidence of genuine video inference. Clearway preserves fixture provenance end to end, including saved results and the phone brief.

No repository license file was found in the reviewed tree. Clearway uses conceptual/UI references and does not assume permission to copy HawkWatch's code or bundled videos. Media for Clearway comes from the separately documented sources in `ATTRIBUTION.md`.

## Clearway's own scope

The new work combines a road-obstruction replay, explicit provenance, an incident/run lifecycle, operator review, and a run-specific read-only phone handoff. It does not claim the broad idea of AI video analysis is new. Current implementation and verification status belongs in `MORNING_REPORT.md`; ideas in these references are not automatically completed Clearway features.
