# Clearway visual implementation

Reviewed UI/UX Pro Max with `internal monitoring dashboard --design-system --density 8 --motion 2` and `async request cleanup --stack react`. The first general traffic query returned a landing-page pattern and was rejected; the narrower operations result provided applicable status, contrast, and effect-cleanup guidance.

The app uses a dark slate operational console with amber for a candidate incident, mint for confirmation, an off-white evidence card, and Manrope loaded from a bundled font package. Dense information is split into a source rail, a spatial view, and evidence review. Timestamp observations seek the original video. Source, analysis, review, and location quality are separate labels. No service is described as live unless it is live.

Default map uses the Cesium ellipsoid plus the standard OpenStreetMap browser tile service, with attribution, normal browser cache/referrer behavior, no bulk downloading, and an offline schematic fallback. This is a basic map, not photorealistic imagery. A token and explicit `VITE_PHOTOREALISTIC_TILES=true` opt-in enable the separately configured Cesium ion Google tiles path. This setting is absent by default.

- [Cesium Viewer API](https://cesium.com/learn/cesiumjs/ref-doc/Viewer.html)
- [Cesium photorealistic integration](https://cesium.com/learn/cesiumjs-learn/cesiumjs-photorealistic-3d-tiles/)
- [OpenStreetMap tile policy](https://operations.osmfoundation.org/policies/tiles/)

Viewer ownership is per mounted map: replay/reset updates entities; teardown destroys the viewer. Responder polling aborts on navigation, expires old runs, and uses backoff after failure. Reduced-motion preferences disable animated camera transitions. Controls have text/accessibility names, and keyboard focus stays visible.
