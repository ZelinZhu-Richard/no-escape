# Map setup and provenance

The basic Cesium/OpenStreetMap view works without a token. Google photorealistic 3D is prepared but **not validated on this machine while the token is pending**. Repeated replay/reset keeps one viewer, one selected-source entity, and one tileset initialization per mounted map. A page reload creates a new session.

## Enable Google 3D when the token arrives

1. In the intended Cesium ion account, ensure **Google Photorealistic 3D Tiles** is available in **My Assets**. The installed Cesium 1.147 helper uses asset `2275207`. Check the account's applicable plan, usage and provider terms before enabling it. [Cesium's Google tiles guide](https://cesium.com/learn/unreal/unreal-photorealistic-3d-tiles/) describes adding the asset and retaining credits.
2. Use an application token limited to the needed read-only asset and intended browser origins; do not use an account administration token. [Cesium access-token documentation](https://cesium.com/learn/ion/cesium-ion-access-tokens/) explains permissions and restrictions. This token is browser-visible by design; a frontend build cannot conceal it.
3. Add the following to ignored `clearway/web/.env.local` locally. Never paste the real token into chat or commit it:

   ```dotenv
   VITE_CESIUM_ION_TOKEN=YOUR_BROWSER_SCOPED_TOKEN
   VITE_PHOTOREALISTIC_TILES=true
   VITE_MAP_OFFLINE=false
   ```

4. Run `make build`, then refresh the local operator page. These values are build-time settings. The production server does not auto-reload while files change.
5. Confirm the map badge changes from **Loading Google 3D** to **Photorealistic 3D**, visible buildings are present, and native Google/Cesium credits remain readable. The badge waits for an actual tile-load event, not just successful root metadata. A failure or timeout falls back to the basic map with an explicit status. No silent switch to a paid direct Google API occurs.

Map context shows observed root and child resource counts. These browser observations are not billing receipts and may omit requests hidden by browser cache or provider behavior. The account usage dashboard is authoritative. Routine fixture tests should use the offline map.

## Context data and label behavior

**View map context** explains the current clip's placement, coordinates, duration, evidence count, and map loads. Unknown-location footage stays **simulated placement** regardless of how realistic the city looks. The map is not lane projection.

Public camera pins use official Caltrans coordinates across the nine Bay Area counties. **Fit public camera network** fits all current search/county matches, not just the first list page. Select a pin to open its video/snapshot preview; the public layer can be hidden independently of replay/incident markers. The North Carolina inventory has been removed. Recorded footage keeps its original unknown-location/simulated-placement disclosure and does not become Bay Area incident evidence simply because public cameras are nearby.

The selected replay label is ordinary HTML positioned using [Cesium SceneTransforms](https://cesium.com/learn/cesiumjs/ref-doc/SceneTransforms.html). It no longer recreates Cesium glyph labels during polling or incident state changes. It is hidden when it would overlap fixed map controls; the fixed evidence callout remains available.

## Reference checkout

God's Eye View was shallow-cloned into ignored `.local/references/gods-eye-view` at commit `ca6eace79e60f29770597ea26871d5427b504b2b`. No setup script was run, application code copied, or bundled dataset imported. Its MIT source license does not cover its separately licensed data/model assets.

Inspected patterns: [Google map setup](https://github.com/bilawalsidhu/gods-eye-view/blob/ca6eace79e60f29770597ea26871d5427b504b2b/src/maps/google3d.js), [map availability labels](https://github.com/bilawalsidhu/gods-eye-view/blob/ca6eace79e60f29770597ea26871d5427b504b2b/src/mapStackChips.js), [voice cancellation](https://github.com/bilawalsidhu/gods-eye-view/blob/ca6eace79e60f29770597ea26871d5427b504b2b/src/voice/narration.js), and [source/data license separation](https://github.com/bilawalsidhu/gods-eye-view/blob/ca6eace79e60f29770597ea26871d5427b504b2b/LICENSE).
