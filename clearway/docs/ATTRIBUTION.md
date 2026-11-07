# Clearway attribution

## Project inspirations

- [God's Eye View](https://github.com/bilawalsidhu/gods-eye-view), bilawalsidhu: inspiration for a spatial interface using Cesium and 3D city imagery. Its reviewed [license](https://github.com/bilawalsidhu/gods-eye-view/blob/c0a5d4141d4fa6f7648910cedd98654f2381989d/LICENSE) distinguishes source-code rights from third-party assets. No application code has been copied into Clearway in this planning work.
- [HawkWatch / Treehacks2025](https://github.com/Grace-Shao/Treehacks2025), Grace-Shao and contributors: inspiration for visual observations and incident review. A license file was not found in the earlier review; do not assume permission to copy its code. No application code has been copied into Clearway in this planning work.

Hackathon eligibility is separate from software licensing. Record any future copied code, pinned revision, and applicable notices before submission. Add actual dependencies and versions after implementation; planned libraries are not yet installed Clearway dependencies.

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

## Mapping attribution during implementation

Preserve the on-screen Cesium and imagery-provider credits required by the actual configured services. Do not replace or obscure them with Clearway branding. Verify service access and terms independently of the source-project code license.
