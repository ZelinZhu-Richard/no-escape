import { useEffect, useRef, useState } from "react";
import {
  Cartesian2,
  Cartesian3,
  Color,
  Credit,
  EllipsoidTerrainProvider,
  HeightReference,
  Ion,
  LabelStyle,
  Math as CesiumMath,
  OpenStreetMapImageryProvider,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Viewer,
  createGooglePhotorealistic3DTileset,
} from "cesium";
import type { Incident, Source } from "./types";
import { Icon } from "./Icon";

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
  const viewer = useRef<Viewer | null>(null);
  const selection = useRef(onSelect);
  selection.current = onSelect;
  const [fallback, setFallback] = useState(
    import.meta.env.VITE_MAP_OFFLINE === "true",
  );
  const [mapName, setMapName] = useState("Basic map");
  const [tiles, setTiles] = useState(0);
  const [ready, setReady] = useState(false);
  const currentSource = useRef(source);
  currentSource.current = source;
  const initialSourceId = useRef("");

  useEffect(() => {
    if (!container.current || import.meta.env.VITE_MAP_OFFLINE === "true")
      return;
    let disposed = false;
    let observer: PerformanceObserver | undefined;
    let handler: ScreenSpaceEventHandler | undefined;
    let instance: Viewer | undefined;
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
      }, ScreenSpaceEventType.LEFT_CLICK);
      const addBasicMap = () => {
        if (!instance || disposed) return;
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
        createGooglePhotorealistic3DTileset()
          .then((tileset) => {
            if (disposed || !instance) {
              tileset.destroy();
              return;
            }
            instance.scene.primitives.add(tileset);
            instance.scene.globe.show = false;
            setMapName("Photorealistic 3D");
            instance.scene.requestRender();
          })
          .catch(() => {
            if (!disposed) {
              setMapName("Basic map · 3D unavailable");
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
        if (!disposed) setTiles(metrics().tile_content_requests);
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
      observer?.disconnect();
      handler?.destroy();
      if (instance && !instance.isDestroyed()) instance.destroy();
      viewer.current = null;
    };
  }, []);

  useEffect(() => {
    const v = viewer.current;
    if (!v || v.isDestroyed() || !source) return;
    v.entities.removeAll();
    const longitude = source.location.longitude ?? -78.8986;
    const latitude = source.location.latitude ?? 35.994;
    const accent = Color.fromCssColorString(
      incident?.review_status === "confirmed" ? "#9cd8ba" : "#f2bd59",
    );
    v.entities.add({
      id: "selected-source",
      position: Cartesian3.fromDegrees(longitude, latitude, 3),
      point: {
        pixelSize: incident ? 18 : 12,
        color: accent,
        outlineColor: Color.fromCssColorString("#17262e"),
        outlineWidth: 4,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      ellipse: {
        semiMinorAxis: 75,
        semiMajorAxis: 75,
        material: accent.withAlpha(0.13),
        height: 1,
      },
      label: {
        text: incident
          ? incident.review_status === "confirmed"
            ? "CONFIRMED DEMO"
            : "REVIEW CANDIDATE"
          : "DEMO CAMERA",
        font: "11px monospace",
        fillColor: accent,
        style: LabelStyle.FILL_AND_OUTLINE,
        outlineColor: Color.fromCssColorString("#15232c"),
        outlineWidth: 5,
        pixelOffset: new Cartesian2(0, -35),
        heightReference: HeightReference.NONE,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
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
  return (
    <section className="map-shell" aria-label="Incident map">
      <div
        className="map-canvas"
        ref={container}
        style={fallback ? { visibility: "hidden" } : undefined}
      />
      {fallback && <Diagram incident={incident} onSelect={onSelect} />}
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
