import assert from "node:assert/strict";
import { readFile, readdir, stat } from "node:fs/promises";

// A successful bundle can still place Cesium's runtime assets at the wrong URL.
// Check the actual emitted layout used by CESIUM_BASE_URL and the API server.
for (const path of [
  "index.html",
  "cesium/Assets/Images/ion-credit.png",
  "cesium/Assets/approximateTerrainHeights.json",
  "assets/licenses/cesium-LICENSE.md",
  "assets/licenses/ThirdParty.json",
  "assets/licenses/manrope-OFL.txt",
  "assets/licenses/bundled-dependencies.md",
]) {
  const file = new URL(`../dist/${path}`, import.meta.url);
  assert((await stat(file)).size > 0, `Missing or empty build asset: ${path}`);
}
const workers = await readdir(
  new URL("../dist/cesium/Workers/", import.meta.url),
);
assert(
  workers.some((name) => name.endsWith(".js")),
  "Cesium workers were not copied",
);
JSON.parse(
  await readFile(
    new URL(
      "../dist/cesium/Assets/approximateTerrainHeights.json",
      import.meta.url,
    ),
    "utf8",
  ),
);
console.log(
  "Build assets verified: Cesium runtime files and dependency notices.",
);
