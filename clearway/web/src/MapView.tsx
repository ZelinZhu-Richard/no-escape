import { useEffect, useMemo, useRef, useState } from "react";
import {
  Cartesian2,
  Cartesian3,
  Color,
  ConstantPositionProperty,
  ConstantProperty,
  Credit,
  Ellipsoid,
  EllipsoidalOccluder,
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
import { isBayAreaCamera, MAX_LIVE_CAMERAS } from "./liveCameras";
import type { LiveCamera } from "./liveCameras";
import "./MapView.css";

type MapState = "basic" | "loading" | "photorealistic" | "unavailable";
type MapViewMode = "replay" | "public";
const EMPTY_LIVE_CAMERAS: LiveCamera[] = [];
const EMPTY_INCIDENTS: Incident[] = [];
const CAMERA_HIT_RADIUS = 24;
interface MapPickTarget {
  id: string;
  x: number;
  y: number;
}

function nearestMapTarget(
  position: Cartesian2,
  targets: MapPickTarget[],
): string | null {
  let nearest: string | null = null;
  let distance = CAMERA_HIT_RADIUS * CAMERA_HIT_RADIUS;
  for (const target of targets) {
    const squared = (target.x - position.x) ** 2 + (target.y - position.y) ** 2;
    if (squared <= distance) {
      nearest = target.id;
      distance = squared;
    }
  }
  return nearest;
}

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
              stroke="#dcd8ce"
              strokeWidth=".6"
            />
          </pattern>
        </defs>
        <rect width="800" height="600" fill="#f3f1ec" />
        <rect width="800" height="600" fill="url(#grid)" />
        <g fill="#e7e3da" stroke="#cfcbc0" strokeWidth="1">
          <path d="M90 92h150v93H90zM285 92h105v93H285zM435 92h180v93H435zM90 228h150v116H90zM285 228h105v116H285zM435 228h180v116H435zM90 388h150v120H90zM285 388h105v120H285zM435 388h180v120H435z" />
        </g>
        <g fill="none" stroke="#ffffff" strokeWidth="18">
          <path d="M-40 204h890M-40 365h890M264-30v700M414-30v700M650-30v700" />
          <path d="M-50 540 850 110" strokeWidth="28" />
        </g>
        <g fill="none" stroke="#0e0e0e" strokeWidth="1" strokeDasharray="8 12">
          <path d="M-40 204h890M-40 365h890M264-30v700M414-30v700M650-30v700" />
          <path d="M-50 540 850 110" />
        </g>
        <path
          d="m-50 540 850-430"
          fill="none"
          stroke="#0e0e0e"
          strokeWidth="4"
          opacity=".3"
        />
        <circle cx="414" cy="318" r="65" fill="#ff4f00" opacity=".07" />
        <circle
          cx="414"
          cy="318"
          r="65"
          stroke="#ff4f00"
          fill="none"
          strokeDasharray="3 7"
          opacity=".5"
        />
        <text
          x="75"
          y="565"
          fill="#5c5a54"
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
  liveCameras = EMPTY_LIVE_CAMERAS,
  liveSelectedId = null,
  onSelectLiveCamera,
  incidents = EMPTY_INCIDENTS,
  onSelectIncident,
}: {
  source?: Source;
  incident?: Incident;
  onSelect: () => void;
  liveCameras?: LiveCamera[];
  liveSelectedId?: string | null;
  onSelectLiveCamera?: (id: string) => void;
  incidents?: Incident[];
  onSelectIncident?: (id: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const markerLabel = useRef<HTMLButtonElement>(null);
  const markerPosition = useRef<Cartesian3 | null>(null);
  const liveMarkerLabel = useRef<HTMLButtonElement>(null);
  const liveMarkerPosition = useRef<Cartesian3 | null>(null);
  const viewer = useRef<Viewer | null>(null);
  const selection = useRef(onSelect);
  selection.current = onSelect;
  const liveSelection = useRef(onSelectLiveCamera);
  liveSelection.current = onSelectLiveCamera;
  const livePoints = useMemo(
    () => liveCameras.filter(isBayAreaCamera).slice(0, MAX_LIVE_CAMERAS),
    [liveCameras],
  );
  const currentLivePoints = useRef<LiveCamera[]>(livePoints);
  currentLivePoints.current = livePoints;
  const selectedLive = livePoints.find(
    (camera) => camera.id === liveSelectedId,
  );
  const liveEntityIds = useRef(new Set<string>());
  const incidentEntityIds = useRef(new Set<string>());
  const incidentSelection = useRef(onSelectIncident);
  incidentSelection.current = onSelectIncident;
  const positionedIncidents = incidents.filter(
    (item) =>
      item.source_mode === "live" &&
      item.location.quality === "known_camera" &&
      Number.isFinite(item.location.latitude) &&
      Number.isFinite(item.location.longitude) &&
      Math.abs(item.location.latitude!) <= 90 &&
      Math.abs(item.location.longitude!) <= 180,
  );
  const currentIncidents = useRef(positionedIncidents);
  currentIncidents.current = positionedIncidents;
  const pickTargets = useRef<MapPickTarget[]>([]);
  const [showPublicCameras, setShowPublicCameras] = useState(true);
  const [viewMode, setViewMode] = useState<MapViewMode>("replay");
  const currentViewMode = useRef(viewMode);
  currentViewMode.current = viewMode;
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
  const visibleLayers = useRef({ public: showPublicCameras });
  visibleLayers.current = { public: showPublicCameras };

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
      instance.scene.backgroundColor = Color.fromCssColorString("#f3f1ec");
      instance.scene.globe.baseColor = Color.fromCssColorString("#f3f1ec");
      instance.scene.globe.enableLighting = false;
      instance.scene.screenSpaceCameraController.minimumZoomDistance = 70;
      instance.scene.screenSpaceCameraController.maximumZoomDistance = 22000000;
      instance.resolutionScale = Math.min(window.devicePixelRatio || 1, 1.5);
      instance.scene.renderError.addEventListener(() => {
        if (!disposed) setFallback(true);
      });
      handler = new ScreenSpaceEventHandler(instance.scene.canvas);
      handler.setInputAction((event: { position: Cartesian2 }) => {
        // Dots stay visually compact, but selecting one does not require a
        // pixel-perfect hit. Screen projections are refreshed after map renders.
        // A click near a dot picks the nearest visible camera, not an arbitrary
        // point returned by a large rectangular GPU pick.
        const near = nearestMapTarget(event.position, pickTargets.current);
        const picked = near
          ? undefined
          : instance?.scene.pick(event.position, 15, 15);
        const nativeId =
          typeof picked?.id === "string" ? picked.id : picked?.id?.id;
        const selected = near ?? nativeId;
        if (selected === "selected-source") selection.current();
        else if (
          typeof selected === "string" &&
          selected.startsWith("live-incident:")
        ) {
          const id = selected.slice("live-incident:".length);
          if (currentIncidents.current.some((item) => item.id === id))
            incidentSelection.current?.(id);
        } else if (
          typeof selected === "string" &&
          selected.startsWith("public-camera:") &&
          visibleLayers.current.public
        ) {
          const id = selected.slice("public-camera:".length);
          if (currentLivePoints.current.some((camera) => camera.id === id)) {
            liveSelection.current?.(id);
          }
        }
      }, ScreenSpaceEventType.LEFT_CLICK);
      handler.setInputAction((event: { endPosition: Cartesian2 }) => {
        if (instance)
          instance.scene.canvas.style.cursor = nearestMapTarget(
            event.endPosition,
            pickTargets.current,
          )
            ? "pointer"
            : "";
      }, ScreenSpaceEventType.MOUSE_MOVE);
      // Use one ordinary DOM label rather than rebuilding Cesium's glyph atlas
      // on every status poll. Its text stays readable as review status changes.
      removeLabelPosition = instance.scene.postRender.addEventListener(() => {
        if (!instance || disposed) return;
        const width = instance.scene.canvas.clientWidth;
        const height = instance.scene.canvas.clientHeight;
        const occluder = instance.camera.positionWC
          ? new EllipsoidalOccluder(Ellipsoid.WGS84, instance.camera.positionWC)
          : null;
        const targets: MapPickTarget[] = [];
        const addTarget = (id: string, position: Cartesian3 | null) => {
          if (!position || (occluder && !occluder.isPointVisible(position)))
            return;
          const screen = SceneTransforms.worldToWindowCoordinates(
            instance!.scene,
            position,
          );
          if (
            screen &&
            Number.isFinite(screen.x) &&
            Number.isFinite(screen.y) &&
            screen.x >= 0 &&
            screen.x <= width &&
            screen.y >= 0 &&
            screen.y <= height
          ) {
            targets.push({ id, x: screen.x, y: screen.y });
          }
        };
        addTarget("selected-source", markerPosition.current);
        if (visibleLayers.current.public)
          for (const camera of currentLivePoints.current) {
            addTarget(
              `public-camera:${camera.id}`,
              Cartesian3.fromDegrees(camera.longitude, camera.latitude, 3),
            );
          }
        // Incident targets come last so a co-located camera opens its evidence.
        for (const item of currentIncidents.current) {
          addTarget(
            `live-incident:${item.id}`,
            Cartesian3.fromDegrees(
              item.location.longitude!,
              item.location.latitude!,
              6,
            ),
          );
        }
        pickTargets.current = targets;
        for (const [label, position, active] of [
          [
            markerLabel.current,
            markerPosition.current,
            currentViewMode.current !== "public",
          ],
          [
            liveMarkerLabel.current,
            liveMarkerPosition.current,
            currentViewMode.current === "public",
          ],
        ] as const) {
          if (!label) continue;
          const screen = position
            ? SceneTransforms.worldToWindowCoordinates(instance.scene, position)
            : undefined;
          const visible =
            active &&
            screen &&
            screen.x >= 16 &&
            screen.x <= width - 16 &&
            screen.y >= 155 &&
            screen.y <= height - 145;
          label.hidden = !visible;
          if (screen && visible) {
            label.style.left = `${Math.max(110, Math.min(width - 110, screen.x))}px`;
            label.style.top = `${screen.y - 20}px`;
          }
        }
      });
      const addBasicMap = () => {
        if (!instance || disposed) return;
        instance.scene.globe.show = true;
        if (basicAdded) return;
        basicAdded = true;
        // Print basemap first (Stadia-hosted Stamen Toner Lite needs no key on localhost).
        // If it fails, use darkened standard OpenStreetMap tiles; only when both
        // fail does the map switch to the illustrative fallback.
        const addLayer = (night: boolean) => {
          if (!instance || disposed) return;
          const imagery = new OpenStreetMapImageryProvider({
            url: night
              ? "https://tiles.stadiamaps.com/tiles/stamen_toner_lite/"
              : "https://tile.openstreetmap.org/",
            maximumLevel: night ? 20 : 19,
            credit: new Credit(
              night
                ? '© <a href="https://stadiamaps.com/">Stadia Maps</a> © <a href="https://stamen.com/">Stamen Design</a> © <a href="https://openmaptiles.org/">OpenMapTiles</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
                : '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
              true,
            ),
          });
          const layer = instance.imageryLayers.addImageryProvider(imagery);
          let errors = 0;
          imagery.errorEvent.addEventListener(() => {
            if (disposed || ++errors !== 4) return;
            if (night) {
              instance?.imageryLayers.remove(layer, true);
              addLayer(false);
            } else setFallback(true);
          });
          if (night) {
            layer.contrast = 1.08;
            layer.saturation = 0;
          } else {
            layer.saturation = 0;
            layer.contrast = 1.15;
          }
          instance.scene.requestRender();
        };
        addLayer(true);
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
          {
            maximumScreenSpaceError: 20,
            cacheBytes: 256 * 1024 * 1024,
            maximumCacheOverflowBytes: 128 * 1024 * 1024,
            enableCollision: true,
          },
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
      pickTargets.current = [];
    };
  }, []);

  useEffect(() => {
    const v = viewer.current;
    if (!v || v.isDestroyed() || !source) return;
    if (
      source.source_mode === "live" &&
      (!Number.isFinite(source.location.longitude) ||
        !Number.isFinite(source.location.latitude))
    ) {
      markerPosition.current = null;
      const previous = v.entities.getById("selected-source");
      if (previous) previous.show = false;
      return;
    }
    const longitude = source.location.longitude ?? -78.8986;
    const latitude = source.location.latitude ?? 35.994;
    const accent = Color.fromCssColorString(
      incident?.review_status === "confirmed"
        ? "#0e0e0e"
        : incident
          ? "#ff4f00"
          : "#0e0e0e",
    );
    const position = Cartesian3.fromDegrees(longitude, latitude, 3);
    markerPosition.current = position;
    const entity =
      v.entities.getById("selected-source") ??
      v.entities.add({
        id: "selected-source",
        point: {
          outlineWidth: 4,
          outlineColor: Color.fromCssColorString("#f3f1ec"),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
    entity.position = new ConstantPositionProperty(position);
    entity.show = source.source_mode !== "live";
    if (entity.point) {
      entity.point.pixelSize = new ConstantProperty(incident ? 18 : 12);
      entity.point.color = new ConstantProperty(accent);
    }
    if (initialSourceId.current !== source.id) {
      setViewMode("replay");
      v.camera.flyTo({
        destination: Cartesian3.fromDegrees(longitude, latitude - 0.0062, 1100),
        orientation: { heading: 0, pitch: CesiumMath.toRadians(-52), roll: 0 },
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
    const activeIds = new Set<string>();
    for (const camera of currentLivePoints.current) {
      const id = `public-camera:${camera.id}`;
      activeIds.add(id);
      const entity =
        v.entities.getById(id) ??
        v.entities.add({
          id,
          point: {
            outlineWidth: 2,
            outlineColor: Color.fromCssColorString("#f3f1ec"),
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
        });
      entity.position = new ConstantPositionProperty(
        Cartesian3.fromDegrees(camera.longitude, camera.latitude, 3),
      );
      entity.show = showPublicCameras;
      if (entity.point) {
        entity.point.pixelSize = new ConstantProperty(
          camera.id === liveSelectedId ? 18 : 12,
        );
        entity.point.color = new ConstantProperty(
          Color.fromCssColorString(
            camera.id === liveSelectedId ? "#0e0e0e" : "#1f3bff",
          ),
        );
      }
    }
    for (const id of liveEntityIds.current) {
      if (!activeIds.has(id)) v.entities.removeById(id);
    }
    liveEntityIds.current = activeIds;
    v.scene.requestRender();
  }, [ready, liveCameras, liveSelectedId, showPublicCameras]);

  useEffect(() => {
    const v = viewer.current;
    if (!v || v.isDestroyed()) return;
    const ids = new Set<string>();
    for (const item of currentIncidents.current) {
      const id = `live-incident:${item.id}`;
      ids.add(id);
      const entity =
        v.entities.getById(id) ??
        v.entities.add({
          id,
          point: {
            outlineWidth: 3,
            outlineColor: Color.fromCssColorString("#f3f1ec"),
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
        });
      entity.position = new ConstantPositionProperty(
        Cartesian3.fromDegrees(
          item.location.longitude!,
          item.location.latitude!,
          6,
        ),
      );
      if (entity.point) {
        entity.point.pixelSize = new ConstantProperty(
          item.id === incident?.id ? 21 : 16,
        );
        entity.point.color = new ConstantProperty(
          Color.fromCssColorString(
            item.review_status === "confirmed"
              ? "#0e0e0e"
              : item.review_status === "dismissed" ||
                  item.review_status === "resolved"
                ? "#b5b1a6"
                : "#ff4f00",
          ),
        );
      }
    }
    for (const id of incidentEntityIds.current)
      if (!ids.has(id)) v.entities.removeById(id);
    incidentEntityIds.current = ids;
    v.scene.requestRender();
  }, [ready, incidents, incident?.id]);

  useEffect(() => {
    const v = viewer.current;
    if (!v || v.isDestroyed() || !selectedLive) {
      liveMarkerPosition.current = null;
      return;
    }
    const { longitude, latitude } = selectedLive;
    liveMarkerPosition.current = Cartesian3.fromDegrees(longitude, latitude, 3);
    setShowPublicCameras(true);
    setViewMode("public");
    v.camera.flyTo({
      destination: Cartesian3.fromDegrees(longitude, latitude - 0.006, 1700),
      orientation: { heading: 0, pitch: CesiumMath.toRadians(-62), roll: 0 },
      duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? 0
        : 0.8,
    });
    v.scene.requestRender();
  }, [ready, liveSelectedId, selectedLive?.latitude, selectedLive?.longitude]);

  const focus = () => {
    const v = viewer.current;
    const loc = currentSource.current?.location;
    setViewMode("replay");
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
  const mapName =
    mapState === "photorealistic"
      ? "Photorealistic 3D"
      : mapState === "loading"
        ? "Loading Google 3D"
        : mapState === "unavailable"
          ? "Basic map · 3D unavailable"
          : "Basic map";
  const hasCoordinates =
    Number.isFinite(source?.location.latitude) &&
    Number.isFinite(source?.location.longitude);
  const locationKind =
    source?.location.quality === "known_camera"
      ? "Source camera"
      : source?.location.quality === "simulated"
        ? "Simulated placement"
        : "Approximate context";
  const focusPublicNetwork = () => {
    const v = viewer.current;
    const points = currentLivePoints.current;
    if (!v || v.isDestroyed() || !points.length) return;
    setShowPublicCameras(true);
    setViewMode("public");
    v.camera.flyTo({
      destination: Rectangle.fromDegrees(
        Math.min(...points.map((point) => point.longitude)) - 0.015,
        Math.min(...points.map((point) => point.latitude)) - 0.015,
        Math.max(...points.map((point) => point.longitude)) + 0.015,
        Math.max(...points.map((point) => point.latitude)) + 0.015,
      ),
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
      {!fallback && (
        <button
          ref={markerLabel}
          hidden
          className={`map-world-label ${incident?.review_status === "confirmed" ? "is-confirmed" : incident ? "is-candidate" : ""}`}
          onClick={onSelect}
          data-testid="map-world-label"
        >
          {incident
            ? incident.review_status === "confirmed"
              ? incident.source_mode === "live"
                ? "CONFIRMED · CAMERA LOCATION"
                : "CONFIRMED DEMO"
              : "REVIEW CANDIDATE"
            : "DEMO CAMERA"}
        </button>
      )}
      {!fallback && selectedLive && showPublicCameras && (
        <button
          ref={liveMarkerLabel}
          hidden
          className="map-world-label is-public"
          onClick={() => onSelectLiveCamera?.(selectedLive.id)}
          data-testid="map-public-label"
          title={selectedLive.name}
        >
          {selectedLive.name}
        </button>
      )}
      <div className="map-topline">
        <div>
          <span className="eyebrow">SPATIAL CONTEXT</span>
          <h2>
            {viewMode === "public" && !fallback
              ? "Public traffic cameras"
              : source?.location.label?.includes("Durham")
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
          {viewMode === "public" && !fallback
            ? "Provider camera coordinates · separate from replay evidence"
            : source?.location.quality === "known_camera"
                ? "Camera position · not object coordinates"
                : "Simulated placement · footage location unknown"}
        </span>
      </div>
      {!!livePoints.length && (
        <button
          className="map-public-shortcut"
          onClick={focusPublicNetwork}
          disabled={fallback}
        >
          <Icon name="camera" size={13} /> Public CCTV · {livePoints.length}
        </button>
      )}
      <details className="map-context" data-testid="map-context">
        <summary>View map context</summary>
        <dl>
          <div>
            <dt>
              {source?.source_mode === "live"
                ? "Incident location"
                : "Replay location"}
            </dt>
            <dd>{locationKind}</dd>
          </div>
          <div>
            <dt>
              {source?.source_mode === "live"
                ? "Camera coordinates"
                : "Replay coordinates"}
            </dt>
            <dd>
              {hasCoordinates
                ? `${source!.location.latitude!.toFixed(5)}, ${source!.location.longitude!.toFixed(5)}`
                : "Unknown"}
            </dd>
          </div>
          <div>
            <dt>
              {source?.source_mode === "live"
                ? "Observation window"
                : "Clip length"}
            </dt>
            <dd>
              {source?.source_mode === "live"
                ? `${incident?.live_evidence?.window_seconds ?? 0} seconds`
                : source
                  ? `${source.duration_seconds.toFixed(1)} seconds`
                  : "Not selected"}
            </dd>
          </div>
          <div>
            <dt>Evidence</dt>
            <dd>{incident?.evidence.length ?? 0} timestamped observations</dd>
          </div>
          <div>
            <dt>Capture time</dt>
            <dd>Unknown</dd>
          </div>
          <div>
            <dt>Map loads</dt>
            <dd>
              {roots} root · {tiles} tile requests observed
            </dd>
          </div>
          {!!livePoints.length && (
            <div>
              <dt>Public cameras</dt>
              <dd>{livePoints.length} locations · video where available</dd>
            </div>
          )}
        </dl>
        {!!positionedIncidents.length && (
          <div
            className="map-live-incidents"
            aria-label="Live incident map markers"
          >
            <strong>
              {positionedIncidents.length} live incident camera locations
            </strong>
            {positionedIncidents.map((item) => (
              <button key={item.id} onClick={() => onSelectIncident?.(item.id)}>
                {item.title} · {item.review_status}
              </button>
            ))}
          </div>
        )}
        <p>
          {source?.location.quality === "known_camera"
            ? "Camera metadata does not locate an object within a lane."
            : "The marker demonstrates the handoff. It is not the footage's measured location."}
        </p>
        {mapState !== "photorealistic" && (
          <p>
            {mapState === "loading"
              ? "Waiting for Google city tiles."
              : mapState === "unavailable"
                ? "Google 3D could not load. Check token access, account eligibility, and connection."
                : "Google 3D is not configured for this build."}
          </p>
        )}
        {!!livePoints.length && (
          <div className="map-public-layer">
            <label className="map-context-toggle">
              <input
                type="checkbox"
                checked={showPublicCameras}
                data-testid="map-public-toggle"
                onChange={(event) => setShowPublicCameras(event.target.checked)}
              />
              Show public CCTV cameras
            </label>
            <button
              className="map-context-network"
              data-testid="map-public-fit"
              onClick={focusPublicNetwork}
              disabled={fallback}
            >
              Fit public camera network
            </button>
            <p>
              Select a blue pin to open its video or snapshot preview. Pin
              presence does not prove the camera is online.
            </p>
          </div>
        )}
      </details>
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
        className={`map-incident-callout ${incident ? "is-active" : ""} ${incident?.review_status === "confirmed" ? "is-confirmed" : ""}`}
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
            {viewMode === "public" && !fallback
              ? incident?.source_mode === "live"
                ? "Selected live incident evidence"
                : "Separate replay evidence"
              : incident
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
          {viewMode === "public" && !fallback ? (
            <>
              <i className="public-camera-legend-dot" />
              {livePoints.length} public camera points
            </>
          ) : (
            <>
              {incident
                ? incident.review_status === "confirmed"
                  ? "Confirmed incident"
                  : "Incident candidate"
                : "Replay camera"}

            </>
          )}
        </span>
        <span className="mono">
          {positionedIncidents.length > 0 &&
            `${positionedIncidents.length} LIVE INCIDENTS · `}
          {fallback
            ? "SCHEMATIC / NO TILE REQUESTS"
            : `${mapName === "Photorealistic 3D" ? "3D TILES" : "BASIC TERRAIN"} · ${tiles} OBSERVED TILE LOADS`}
        </span>
      </div>
    </section>
  );
}
