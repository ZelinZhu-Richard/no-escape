import { useEffect, useRef, useState } from "react";
import {
  Cartesian2,
  Cartesian3,
  Color,
  ConstantPositionProperty,
  ConstantProperty,
  Credit,
  EllipsoidTerrainProvider,
  Ion,
  Math as CesiumMath,
  OpenStreetMapImageryProvider,
  Rectangle,
  SceneTransforms,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Viewer,
  createGooglePhotorealistic3DTileset,
} from "cesium";
import type { Incident, Source } from "./types";
import { Icon } from "./Icon";
import { request } from "./api";
import { readCameraContext, type CameraContext, type CameraContextPoint } from "./mapContext";
import "./MapView.css";

type MapState = "basic" | "loading" | "photorealistic" | "unavailable";

const metrics = () =>
  (window.__clearwayMapMetrics ??= {
    viewer_initializations: 0,
    tileset_initializations: 0,
    root_tile_requests: 0,
    tile_content_requests: 0,
  });

function Diagram({
  incident,
  onSelect,
}: {
  incident?: Incident;
  onSelect: () => void;
}) {
  return (
    <div className="map-diagram" data-testid="map-fallback">
      <svg
        viewBox="0 0 800 600"
        preserveAspectRatio="xMidYMid slice"
        aria-label="Illustrative road layout; not measured geography"
        role="img"
      >
        <defs>
          <pattern
            id="grid"
            width="36"
            height="36"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M36 0H0V36"
              fill="none"
              stroke="#273740"
              strokeWidth=".6"
            />
          </pattern>
        </defs>
        <rect width="800" height="600" fill="#17262e" />
        <rect width="800" height="600" fill="url(#grid)" />
        <g fill="#203139" stroke="#2c4148" strokeWidth="1">
          <path d="M90 92h150v93H90zM285 92h105v93H285zM435 92h180v93H435zM90 228h150v116H90zM285 228h105v116H285zM435 228h180v116H435zM90 388h150v120H90zM285 388h105v120H285zM435 388h180v120H435z" />
        </g>
        <g fill="none" stroke="#43565d" strokeWidth="18">
          <path d="M-40 204h890M-40 365h890M264-30v700M414-30v700M650-30v700" />
          <path d="M-50 540 850 110" strokeWidth="28" />
        </g>
        <g fill="none" stroke="#809196" strokeWidth="1" strokeDasharray="8 12">
          <path d="M-40 204h890M-40 365h890M264-30v700M414-30v700M650-30v700" />
          <path d="M-50 540 850 110" />
        </g>
        <path
          d="m-50 540 850-430"
          fill="none"
          stroke="#b6c6b4"
          strokeWidth="4"
          opacity=".3"
        />
        <circle cx="414" cy="318" r="65" fill="#f1b951" opacity=".07" />
        <circle
          cx="414"
          cy="318"
          r="65"
          stroke="#f1b951"
          fill="none"
          strokeDasharray="3 7"
          opacity=".5"
        />
        <text
          x="75"
          y="565"
          fill="#9aafb1"
          fontSize="13"
          fontFamily="monospace"
        >
          ILLUSTRATIVE LAYOUT / NOT MEASURED GEOGRAPHY
        </text>
      </svg>
      <button
        className={`diagram-marker ${incident ? "has-incident" : ""}`}
        onClick={onSelect}
        aria-label={
          incident ? "Open incident evidence on map" : "Selected demo camera"
        }
      >
        <Icon name={incident ? "alert" : "camera"} size={21} />
      </button>
    </div>
  );
}

export function MapView({
  source,
  incident,
  onSelect,
}: {
  source?: Source;
  incident?: Incident;
  onSelect: () => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const markerLabel = useRef<HTMLButtonElement>(null);
  const markerPosition = useRef<Cartesian3 | null>(null);
  const viewer = useRef<Viewer | null>(null);
  const selection = useRef(onSelect);
  selection.current = onSelect;
  const [fallback, setFallback] = useState(
    import.meta.env.VITE_MAP_OFFLINE === "true",
  );
  const [mapState, setMapState] = useState<MapState>("basic");
  const [tiles, setTiles] = useState(0);
  const [roots, setRoots] = useState(0);
  const [ready, setReady] = useState(false);
  const currentSource = useRef(source);
  currentSource.current = source;
  const initialSourceId = useRef("");
  const [cameraContext, setCameraContext] = useState<CameraContext | null>(null);
  const [showCameras, setShowCameras] = useState(true);
  const [selectedCamera, setSelectedCamera] = useState<CameraContextPoint | null>(null);
  const contextPoints = useRef<CameraContextPoint[]>([]);
  contextPoints.current = cameraContext?.points ?? [];

  useEffect(() => {
    const abort = new AbortController();
    request<unknown>("/api/camera-context", { signal: abort.signal })
      .then((value) => { if (!abort.signal.aborted) setCameraContext(readCameraContext(value)); })
      .catch(() => { if (!abort.signal.aborted) setCameraContext(null); });
    return () => abort.abort();
  }, []);

  useEffect(() => {
    if (!container.current || import.meta.env.VITE_MAP_OFFLINE === "true")
      return;
    let disposed = false;
    let observer: PerformanceObserver | undefined;
    let handler: ScreenSpaceEventHandler | undefined;
    let instance: Viewer | undefined;
    let removeLabelPosition: (() => void) | undefined;
    let loadingTimeout: ReturnType<typeof setTimeout> | undefined;
    let basicAdded = false;
    let abandonedTiles = false;
    try {
      Ion.defaultAccessToken = "";
      instance = new Viewer(container.current, {
        baseLayer: false,
        terrainProvider: new EllipsoidTerrainProvider(),
        animation: false,
        timeline: false,
        baseLayerPicker: false,
        fullscreenButton: false,
        homeButton: false,
        geocoder: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        infoBox: false,
        selectionIndicator: false,
        shouldAnimate: false,
        requestRenderMode: true,
        skyBox: false,
        skyAtmosphere: false,
      });
      viewer.current = instance;
      metrics().viewer_initializations++;
      instance.scene.backgroundColor = Color.fromCssColorString("#17262e");
      instance.scene.globe.baseColor = Color.fromCssColorString("#23353d");
      instance.scene.globe.enableLighting = false;
      instance.scene.screenSpaceCameraController.minimumZoomDistance = 70;
      instance.scene.screenSpaceCameraController.maximumZoomDistance = 22000000;
      instance.resolutionScale = Math.min(window.devicePixelRatio || 1, 1.5);
      instance.scene.renderError.addEventListener(() => {
        if (!disposed) setFallback(true);
      });
      handler = new ScreenSpaceEventHandler(instance.scene.canvas);
      handler.setInputAction((event: { position: Cartesian2 }) => {
        const picked = instance?.scene.pick(event.position);
        if (picked?.id?.id === "selected-source") selection.current();
        else if (typeof picked?.id?.id === "string" && picked.id.id.startsWith("context-camera:")) {
          const id = picked.id.id.slice("context-camera:".length);
          setSelectedCamera(contextPoints.current.find((point) => point.id === id) ?? null);
        }
      }, ScreenSpaceEventType.LEFT_CLICK);
      // Use one ordinary DOM label rather than rebuilding Cesium's glyph atlas
      // on every status poll. Its text stays readable as review status changes.
      removeLabelPosition = instance.scene.postRender.addEventListener(() => {
        const label = markerLabel.current;
        const position = markerPosition.current;
        if (!label || !position || !instance || disposed) return;
        const screen = SceneTransforms.worldToWindowCoordinates(instance.scene, position);
        const width = instance.scene.canvas.clientWidth;
        const height = instance.scene.canvas.clientHeight;
        const visible = screen && screen.x >= 16 && screen.x <= width - 16
          && screen.y >= 155 && screen.y <= height - 145;
        label.hidden = !visible;
        if (screen && visible) {
          label.style.left = `${Math.max(110, Math.min(width - 110, screen.x))}px`;
          label.style.top = `${screen.y - 20}px`;
        }
      });
      const addBasicMap = () => {
        if (!instance || disposed) return;
        instance.scene.globe.show = true;
        if (basicAdded) return;
        basicAdded = true;
        const imagery = new OpenStreetMapImageryProvider({
          url: "https://tile.openstreetmap.org/",
          maximumLevel: 19,
          credit: new Credit(
            '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
            true,
          ),
        });
        let errors = 0;
        imagery.errorEvent.addEventListener(() => {
          if (!disposed && ++errors >= 4) setFallback(true);
        });
        const layer = instance.imageryLayers.addImageryProvider(imagery);
        layer.brightness = 0.48;
        layer.saturation = 0.2;
        layer.contrast = 1.25;
        instance.scene.requestRender();
      };
      const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN;
      if (ionToken && import.meta.env.VITE_PHOTOREALISTIC_TILES === "true") {
        Ion.defaultAccessToken = ionToken;
        metrics().tileset_initializations++;
        setMapState("loading");
        loadingTimeout = setTimeout(() => {
          if (disposed) return;
          abandonedTiles = true;
          setMapState("unavailable");
          addBasicMap();
        }, 20000);
        // There is no geocoder in this app. Never combine Google tiles with
        // another provider's geocoding, and retain the tileset's native credits.
        createGooglePhotorealistic3DTileset(
          { onlyUsingWithGoogleGeocoder: true },
          { maximumScreenSpaceError: 20, cacheBytes: 256 * 1024 * 1024,
            maximumCacheOverflowBytes: 128 * 1024 * 1024, enableCollision: true },
        )
          .then((tileset) => {
            if (loadingTimeout) clearTimeout(loadingTimeout);
            if (disposed || !instance || abandonedTiles) {
              tileset.destroy();
              return;
            }
            instance.scene.primitives.add(tileset);
            // Root metadata is not evidence that visible city tiles loaded.
            // Switch the badge only when at least one tile is actually loaded.
            let visibleTilesLoaded = false;
            let failures = 0;
            const readyTiles = () => {
              if (disposed || abandonedTiles || !instance) return;
              visibleTilesLoaded = true;
              instance.scene.globe.show = false;
              setMapState("photorealistic");
              if (loadingTimeout) clearTimeout(loadingTimeout);
              instance.scene.requestRender();
            };
            const removeFirstLoad = tileset.tileLoad.addEventListener(() => {
              removeFirstLoad();
              readyTiles();
            });
            tileset.tileFailed.addEventListener(() => {
              if (!disposed && !visibleTilesLoaded && ++failures >= 3) {
                setMapState("unavailable");
                addBasicMap();
              }
            });
            loadingTimeout = setTimeout(() => {
              if (disposed) return;
              abandonedTiles = true;
              instance?.scene.primitives.remove(tileset);
              setMapState("unavailable");
              addBasicMap();
            }, 20000);
            instance.scene.requestRender();
          })
          .catch(() => {
            if (loadingTimeout) clearTimeout(loadingTimeout);
            if (!disposed) {
              setMapState("unavailable");
              addBasicMap();
            }
          });
      } else addBasicMap();
      observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (/\/root\.json(?:\?|$)|\/tileset\.json(?:\?|$)/.test(entry.name))
            metrics().root_tile_requests++;
          else if (/tile\.openstreetmap\.org|\/3dtiles\//.test(entry.name))
            metrics().tile_content_requests++;
        }
        if (!disposed) {
          setTiles(metrics().tile_content_requests);
          setRoots(metrics().root_tile_requests);
        }
      });
      observer.observe({ type: "resource", buffered: false });
      setReady(true);
      console.info("Clearway map initialized", {
        viewer_initializations: metrics().viewer_initializations,
        photorealistic_enabled: Boolean(
          ionToken && import.meta.env.VITE_PHOTOREALISTIC_TILES === "true",
        ),
      });
    } catch {
      setFallback(true);
    }
    return () => {
      disposed = true;
      if (loadingTimeout) clearTimeout(loadingTimeout);
      removeLabelPosition?.();
      observer?.disconnect();
      handler?.destroy();
      if (instance && !instance.isDestroyed()) instance.destroy();
      viewer.current = null;
    };
  }, []);

  useEffect(() => {
    const v = viewer.current;
    if (!v || v.isDestroyed() || !source) return;
    const longitude = source.location.longitude ?? -78.8986;
    const latitude = source.location.latitude ?? 35.994;
    const accent = Color.fromCssColorString(
      incident?.review_status === "confirmed" ? "#9cd8ba" : "#f2bd59",
    );
    const position = Cartesian3.fromDegrees(longitude, latitude, 3);
    markerPosition.current = position;
    const entity = v.entities.getById("selected-source") ?? v.entities.add({
      id: "selected-source", point: { outlineWidth: 4,
        outlineColor: Color.fromCssColorString("#17262e"),
        disableDepthTestDistance: Number.POSITIVE_INFINITY },
    });
    entity.position = new ConstantPositionProperty(position);
    if (entity.point) {
      entity.point.pixelSize = new ConstantProperty(incident ? 18 : 12);
      entity.point.color = new ConstantProperty(accent);
    }
    if (initialSourceId.current !== source.id) {
      v.camera.flyTo({
        destination: Cartesian3.fromDegrees(longitude, latitude - 0.005, 1450),
        orientation: { heading: 0, pitch: CesiumMath.toRadians(-62), roll: 0 },
        duration:
          initialSourceId.current &&
          !window.matchMedia("(prefers-reduced-motion: reduce)").matches
            ? 0.8
            : 0,
      });
      initialSourceId.current = source.id;
    }
    v.scene.requestRender();
  }, [ready, source, incident]);

  useEffect(() => {
    const v = viewer.current;
    if (!v || v.isDestroyed()) return;
    const points = cameraContext?.points ?? [];
    for (const point of points) {
      const entity = v.entities.getById(`context-camera:${point.id}`) ?? v.entities.add({
        id: `context-camera:${point.id}`,
        position: Cartesian3.fromDegrees(point.longitude, point.latitude, 3),
        point: { pixelSize: 7, color: Color.fromCssColorString("#6ed6df"),
          outlineWidth: 2, outlineColor: Color.fromCssColorString("#102e37"),
          disableDepthTestDistance: Number.POSITIVE_INFINITY },
      });
      entity.show = showCameras;
    }
    v.scene.requestRender();
  }, [ready, cameraContext, showCameras]);

  const focus = () => {
    const v = viewer.current;
    const loc = currentSource.current?.location;
    if (v && !v.isDestroyed())
      v.camera.flyTo({
        destination: Cartesian3.fromDegrees(
          loc?.longitude ?? -78.8986,
          (loc?.latitude ?? 35.994) - 0.005,
          1450,
        ),
        orientation: { heading: 0, pitch: CesiumMath.toRadians(-62), roll: 0 },
        duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? 0
          : 0.7,
      });
  };
  const mapName = mapState === "photorealistic" ? "Photorealistic 3D"
    : mapState === "loading" ? "Loading Google 3D"
      : mapState === "unavailable" ? "Basic map · 3D unavailable" : "Basic map";
  const hasCoordinates = Number.isFinite(source?.location.latitude)
    && Number.isFinite(source?.location.longitude);
  const locationKind = source?.location.quality === "known_camera"
    ? "Source camera" : source?.location.quality === "simulated" ? "Simulated placement" : "Approximate context";
  const focusNetwork = () => {
    const v = viewer.current;
    const points = cameraContext?.points ?? [];
    if (!v || v.isDestroyed() || !points.length) return;
    setShowCameras(true);
    v.camera.flyTo({
      destination: Rectangle.fromDegrees(
        Math.min(...points.map((point) => point.longitude)) - .01,
        Math.min(...points.map((point) => point.latitude)) - .01,
        Math.max(...points.map((point) => point.longitude)) + .01,
        Math.max(...points.map((point) => point.latitude)) + .01,
      ),
      duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : .7,
    });
  };
  return (
    <section className="map-shell" aria-label="Incident map">
      <div
        className="map-canvas"
        ref={container}
        style={fallback ? { visibility: "hidden" } : undefined}
      />
      {fallback && <Diagram incident={incident} onSelect={onSelect} />}
      {!fallback && <button ref={markerLabel} hidden
        className={`map-world-label ${incident?.review_status === "confirmed" ? "is-confirmed" : ""}`}
        onClick={onSelect} data-testid="map-world-label">
        {incident ? incident.review_status === "confirmed" ? "CONFIRMED DEMO" : "REVIEW CANDIDATE" : "DEMO CAMERA"}
      </button>}
      <div className="map-topline">
        <div>
          <span className="eyebrow">SPATIAL CONTEXT</span>
          <h2>
            {source?.location.label?.includes("Durham")
              ? "Durham, North Carolina"
              : source?.location.quality === "known_camera"
                ? "Source camera context"
                : "Demo corridor"}
          </h2>
        </div>
        <span className="map-pill">
          <Icon name="layers" size={14} />
          {fallback ? "Illustrative fallback" : mapName}
        </span>
      </div>
      <div className="map-location-note">
        <Icon name="pin" size={14} />
        <span>
          {source?.location.quality === "known_camera"
            ? "Camera position · not object coordinates"
            : "Simulated placement · footage location unknown"}
        </span>
      </div>
      <details className="map-context" data-testid="map-context">
        <summary>View map context</summary>
        <dl>
          <div><dt>Placement</dt><dd>{locationKind}</dd></div>
          <div><dt>Coordinates</dt><dd>{hasCoordinates
            ? `${source!.location.latitude!.toFixed(5)}, ${source!.location.longitude!.toFixed(5)}`
            : "Unknown"}</dd></div>
          <div><dt>Clip length</dt><dd>{source ? `${source.duration_seconds.toFixed(1)} seconds` : "Not selected"}</dd></div>
          <div><dt>Evidence</dt><dd>{incident?.evidence.length ?? 0} timestamped observations</dd></div>
          <div><dt>Capture time</dt><dd>Unknown</dd></div>
          <div><dt>Map loads</dt><dd>{roots} root · {tiles} tile requests observed</dd></div>
          <div><dt>Camera layer</dt><dd>{cameraContext?.points.length ?? 0} inventory locations</dd></div>
        </dl>
        <p>{source?.location.quality === "known_camera"
          ? "Camera metadata does not locate an object within a lane."
          : "The marker demonstrates the handoff. It is not the footage's measured location."}</p>
        {mapState !== "photorealistic" && <p>{mapState === "loading"
          ? "Waiting for Google city tiles."
          : mapState === "unavailable"
            ? "Google 3D could not load. Check token access, account eligibility, and connection."
            : "Google 3D is not configured for this build."}</p>}
        {cameraContext?.status === "available" && <>
          <label className="map-context-toggle"><input type="checkbox" checked={showCameras}
            onChange={(event) => { setShowCameras(event.target.checked); setSelectedCamera(null); }} />
            Show Durham-area NCDOT locations</label>
          <button className="map-context-network" onClick={focusNetwork} disabled={fallback}>Fit camera network</button>
          <p>Inventory only · streams unverified · unrelated to this replay.
            {cameraContext.stale ? " Snapshot may be stale." : ""}</p>
          <p>{cameraContext.source_url && <a href={cameraContext.source_url} target="_blank" rel="noreferrer">{cameraContext.attribution}</a>}
            {cameraContext.fetched_at && <> · Retrieved {new Date(cameraContext.fetched_at).toLocaleString()}</>}
            {cameraContext.source_updated_at && <> · Source updated {new Date(cameraContext.source_updated_at).toLocaleDateString()}</>}</p>
        </>}
      </details>
      {selectedCamera && showCameras && !fallback && <aside className="map-camera-detail" aria-label="Camera inventory details">
        <button aria-label="Close camera inventory details" onClick={() => setSelectedCamera(null)}>×</button>
        <span className="eyebrow">NCDOT INVENTORY · NOT LIVE</span>
        <strong>{selectedCamera.description || selectedCamera.name}</strong>
        <span>{selectedCamera.latitude.toFixed(5)}, {selectedCamera.longitude.toFixed(5)}</span>
        <small>Camera location only. Not evidence for the replay incident.</small>
      </aside>}
      <div className="map-tools">
        <button
          className="map-tool"
          aria-label="Focus selected camera"
          title="Focus selected camera"
          onClick={focus}
        >
          <Icon name="target" />
        </button>
        <button
          className="map-tool"
          aria-label="Zoom in"
          onClick={() => {
            const v = viewer.current;
            if (v && !v.isDestroyed()) {
              v.camera.zoomIn(v.camera.positionCartographic.height * 0.3);
              v.scene.requestRender();
            }
          }}
          disabled={fallback}
        >
          <Icon name="plus" />
        </button>
        <button
          className="map-tool"
          aria-label="Zoom out"
          onClick={() => {
            const v = viewer.current;
            if (v && !v.isDestroyed()) {
              v.camera.zoomOut(v.camera.positionCartographic.height * 0.3);
              v.scene.requestRender();
            }
          }}
          disabled={fallback}
        >
          <Icon name="minus" />
        </button>
      </div>
      <button
        className={`map-incident-callout ${incident ? "is-active" : ""}`}
        onClick={onSelect}
        data-testid="map-marker"
        aria-label={
          incident ? "Open incident evidence on map" : "View selected source"
        }
      >
        <span className="map-marker-symbol">
          <Icon name={incident ? "alert" : "camera"} size={20} />
        </span>
        <span>
          <strong>
            {incident
              ? incident.review_status === "confirmed"
                ? "Incident confirmed"
                : "Review candidate"
              : "Selected replay source"}
          </strong>
          <small>
            {incident
              ? "Open visual evidence"
              : "Start replay to inspect this scene"}
          </small>
        </span>
        <Icon name="chevron" size={16} />
      </button>
      <div className="map-bottomline">
        <span>
          <i className="legend-dot" />
          {incident ? "Incident candidate" : "Replay camera"}
          {!fallback && showCameras && !!cameraContext?.points.length && <><i className="camera-legend-dot" />{cameraContext.points.length} NCDOT locations</>}
        </span>
        <span className="mono">
          {fallback
            ? "SCHEMATIC / NO TILE REQUESTS"
            : `${mapName === "Photorealistic 3D" ? "3D TILES" : "BASIC TERRAIN"} · ${tiles} OBSERVED TILE LOADS`}
        </span>
      </div>
    </section>
  );
}
