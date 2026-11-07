"""Run locally with ``uvicorn api.app:app --host 127.0.0.1 --port 8000``.

Expose only ``api.app:responder_app`` (port 8001) through an intentionally
started morning tunnel. It has no operator routes, docs, labels, or archive.
"""

from pathlib import Path
from datetime import datetime, timezone
import json
import os
import threading
import time
import re
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from .configuration import load_local_environment
from .models import AnalysisResult, LabelRequest, ReplayRequest
from .sources import SOURCES, media_path, source_record
from .store import StateError, Store


ROOT = Path(__file__).resolve().parent.parent
load_local_environment()


def _public_origin(data_dir: Path | None = None) -> tuple[str | None, str | None]:
    configured = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not configured and data_dir is not None:
        # The foreground tunnel wrapper owns this short-lived runtime record.
        # Reading it per request avoids restarting the operator to change QR URLs.
        runtime = data_dir / "runtime" / "tunnel.json"
        try:
            if runtime.is_file() and not runtime.is_symlink() and runtime.stat().st_size <= 8192:
                record = json.loads(runtime.read_text())
                pid = record.get("pid")
                updated = datetime.fromisoformat(record.get("updated_at", ""))
                age = (datetime.now(timezone.utc) - updated).total_seconds()
                if record.get("active") is True and 0 <= age <= 15 and isinstance(pid, int) and not isinstance(pid, bool) and pid > 1:
                    try:
                        os.kill(pid, 0)
                    except PermissionError:
                        # Sandboxed sibling services may not signal each other.
                        # The wrapper's active state and <=15s heartbeat remain
                        # mandatory; a dead/missing PID still fails below.
                        pass
                    configured = str(record.get("public_base_url", "")).strip().rstrip("/")
        except (OSError, ValueError, TypeError, AttributeError):
            configured = ""
    if not configured:
        return None, None
    try:
        url = urlsplit(configured)
        if (
            url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path not in ("", "/")
        ):
            raise ValueError()
        _ = url.port
    except ValueError:
        return None, "PUBLIC_BASE_URL must be an HTTPS origin without credentials, path, query, or fragment."
    return configured, None


def _unavailable() -> dict:
    return {
        "mode": "unavailable", "status": "unavailable",
        "message": "Analysis unavailable. Check local model configuration and the spend ledger; no result was substituted.",
        "candidate": False, "title": "", "category": "",
        "observations": [], "unknowns": ["No validated analysis result is available."],
        "provenance": {"provider": None, "model": None, "fixture": False, "cache_key": None},
    }


def create_app(
    *, data_dir: Path | str | None = None, analysis_service=None,
    detection_service=None, live_camera_service=None, live_detection_service=None,
    live_monitor_service=None, live_tracking_service=None,
    read_only: bool = False, web_dist: Path | str | None = None,
) -> FastAPI:
    data = Path(data_dir or os.environ.get("CLEARWAY_DATA_DIR", ROOT / "data")).resolve()
    dist = Path(web_dist or ROOT / "web" / "dist").resolve()
    store = Store(data)
    if analysis_service is None and not read_only:
        from .analysis import AnalysisService
        analysis_service = AnalysisService(data)
    if detection_service is None and not read_only:
        from .detection import DetectionService
        detection_service = DetectionService(data)
    if live_camera_service is None and not read_only:
        from .live_cameras import LiveCameraService
        if live_detection_service is None:
            from .live_detection import LiveDetectionService
            live_detection_service = LiveDetectionService(data)
        live_camera_service = LiveCameraService(detector=live_detection_service)
    if live_monitor_service is None and not read_only:
        from .live_monitor import LiveAlertMonitor
        live_monitor_service = LiveAlertMonitor(store)
    if live_tracking_service is None and not read_only:
        from .live_tracking import LiveTrackingService
        live_tracking_service = LiveTrackingService()
    frame_request_lock = threading.Lock()
    last_frame_attempt = float("-inf")
    application = FastAPI(
        title="Clearway responder" if read_only else "Clearway local operator",
        docs_url=None, redoc_url=None, openapi_url=None,
    )
    application.state.store = store
    application.state.analysis_service = analysis_service
    application.state.data_dir = data
    application.state.live_monitor_service = live_monitor_service
    application.state.live_tracking_service = live_tracking_service

    @application.middleware("http")
    async def boundaries(request: Request, call_next):
        if read_only and request.method not in ("GET", "HEAD"):
            return JSONResponse({"detail": "Responder service is read-only."}, status_code=405)
        if not read_only:
            # Binding loopback is the primary boundary. Host/origin checks also
            # prevent a remote web page from driving the local operator API.
            host = request.url.hostname
            if host not in ("127.0.0.1", "localhost", "::1", "testserver"):
                return JSONResponse({"detail": "Use the local operator origin."}, status_code=403)
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                origin = request.headers.get("origin")
                if origin:
                    try:
                        parsed = urlsplit(origin)
                        allowed = parsed.scheme in ("http", "https") and parsed.hostname in ("localhost", "127.0.0.1", "::1", "testserver")
                    except ValueError:
                        allowed = False
                    if not allowed:
                        return JSONResponse({"detail": "Cross-origin operator writes are not allowed."}, status_code=403)
                content_type = request.headers.get("content-type", "").split(";")[0].lower()
                camera_frame = bool(re.fullmatch(r"/api/live-cameras/[A-Za-z0-9_-]{1,120}/detect-frame", request.url.path))
                if content_type != "application/json" and not (camera_frame and content_type == "image/jpeg"):
                    return JSONResponse({"detail": "Operator writes require application/json."}, status_code=415)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer" if read_only else "strict-origin-when-cross-origin"
        return response

    @application.exception_handler(StateError)
    async def state_error(_request, error: StateError):
        return JSONResponse({"detail": error.detail}, status_code=error.status)

    def snapshot(*, expected_run_id=None, analysis_source_id=None):
        state = store.snapshot(expected_run_id=expected_run_id, analysis_source_id=analysis_source_id)
        state["telemetry"] = analysis_service.telemetry() if analysis_service else {
            "network_inference_calls": 0, "cache_hits": 0, "fixture_runs": 0,
            "estimated_spend_usd": 0,
        }
        return state

    def file_response(source_id: str, kind: str):
        path = media_path(data, source_id, kind)
        if path is None:
            raise HTTPException(404, "Selected demo media is unavailable. Use the documented media setup.")
        media_type = "image/jpeg" if kind == "poster" else ("video/webm" if path.suffix == ".webm" else "video/mp4")
        return FileResponse(path, media_type=media_type)

    def spa_response():
        index = dist / "index.html"
        if not index.is_file() or index.is_symlink():
            raise HTTPException(503, "Frontend not built. Run npm ci and npm run build in clearway/web.")
        return FileResponse(index, media_type="text/html")

    @application.get("/api/respond/{run_id}/{incident_id}")
    def responder(run_id: UUID, incident_id: UUID):
        run, incident_key = str(run_id), str(incident_id)
        incident = store.responder(run, incident_key)
        prefix = f"/api/respond/{run}/{incident_key}/media"
        if incident.get("source_mode") == "live":
            source = {**incident["live_source"], "poster_url": f"{prefix}/evidence"}
            incident["live_source"] = source
            incident["live_evidence"] = {**incident["live_evidence"], "image_url": f"{prefix}/evidence"}
        else:
            source = source_record(data, incident["source_id"], prefix)
        return {"incident": incident, "source": source, "run_id": run, "status": "active"}

    @application.get("/api/respond/{run_id}/{incident_id}/media/{kind}")
    def responder_media(run_id: UUID, incident_id: UUID, kind: str):
        incident = store.responder(str(run_id), str(incident_id))
        if incident.get("source_mode") == "live":
            if kind != "evidence":
                raise HTTPException(404, "Live candidates retain only their scoped evidence image.")
            return Response(store.evidence(str(run_id), str(incident_id), public=True), media_type="image/jpeg")
        return file_response(incident["source_id"], kind)

    @application.get("/respond/{run_id}/{incident_id}")
    def responder_page(run_id: UUID, incident_id: UUID):
        # The page must load for expired IDs so it can explain the 410 status.
        return spa_response()

    def asset_response(path: str, base: str):
        folder = dist / base
        asset = folder / path
        if (
            not asset.is_file() or asset.is_symlink()
            or not asset.resolve().is_relative_to(folder.resolve())
            or any(part.startswith(".") for part in Path(path).parts)
        ):
            raise HTTPException(404, "Asset not found.")
        return FileResponse(asset)

    @application.get("/assets/{path:path}")
    def asset(path: str):
        return asset_response(path, "assets")

    @application.get("/cesium/{path:path}")
    def cesium_asset(path: str):
        return asset_response(path, "cesium")

    if not read_only:
        @application.get("/api/health")
        def health():
            return {"status": "ok"}

        @application.get("/api/config")
        def config():
            public_url, public_error = _public_origin(data)
            readiness = analysis_service.readiness() if hasattr(analysis_service, "readiness") else {
                "ready": False, "message": "Provider readiness is unavailable.", "max_billable_usd": 0,
            }
            return {
                "public_base_url": public_url, "public_base_url_error": public_error,
                "default_analysis_mode": "fixture", "map_mode": "basic",
                "budgets": {"gemini": readiness.get("max_billable_usd", 0), "claude": 10, "openai": 0},
                "model_configured": readiness["ready"],
                "model_readiness": readiness,
            }

        @application.get("/api/sources")
        def sources():
            return {"sources": [source_record(data, sid) for sid in SOURCES]}

        @application.get("/api/sources/{source_id}/detections")
        def detections(source_id: str):
            if source_id not in SOURCES:
                raise HTTPException(404, "Source not found.")
            return detection_service.get(source_id)

        @application.get("/api/live-cameras")
        def live_cameras():
            return live_camera_service.catalog()

        @application.get("/api/live-cameras/{camera_id}/snapshot")
        def live_camera_snapshot(camera_id: str):
            return live_camera_service.snapshot(camera_id)

        @application.post("/api/live-cameras/{camera_id}/detect-frame")
        async def live_camera_frame(camera_id: str, request: Request):
            nonlocal last_frame_attempt
            camera = next((camera for camera in live_camera_service.catalog().get("cameras", []) if camera["id"] == camera_id), None)
            if camera is None:
                raise HTTPException(404, "Public camera not found.")
            if request.headers.get("content-type", "").split(";")[0].lower() != "image/jpeg":
                raise HTTPException(415, "A single JPEG frame is required.")
            length = request.headers.get("content-length")
            if length is not None and (not length.isdigit() or int(length) > 1_000_000):
                raise HTTPException(413, "Frame exceeds the one-megabyte limit.")
            with frame_request_lock:
                now = time.monotonic()
                if now - last_frame_attempt < 0.125:
                    raise HTTPException(429, "Local frame detection is limited to eight requests per second.")
                last_frame_attempt = now
            raw = bytearray()
            async for chunk in request.stream():
                if len(raw) + len(chunk) > 1_000_000:
                    raise HTTPException(413, "Frame exceeds the one-megabyte limit.")
                raw.extend(chunk)
            if live_detection_service is None:
                raise HTTPException(503, "Local camera detection is unavailable.")
            from .live_monitor import monitor_status, parse_monitor_headers
            context, context_error = None, None
            try:
                context = parse_monitor_headers(request.headers)
            except ValueError as error:
                context_error = str(error)
            kwargs = {"camera_id": camera_id}
            if context is not None:
                kwargs["tracking"] = True
            result = await run_in_threadpool(live_detection_service.analyze_jpeg, bytes(raw), **kwargs)
            # The candidate pool is internal to tracking, never the public
            # raw-detection/evidence contract or the alert monitor input.
            response = {key: value for key, value in result.items() if key != "tracking_candidates"}
            if context_error:
                return {**response, "alert_monitor": monitor_status("unavailable", context_error)}
            if context is not None:
                run, stream, media_time = context
                try:
                    if store.snapshot()["run"]["id"] != run:
                        raise ValueError("Expired tracking run")
                    response["tracking"] = await run_in_threadpool(live_tracking_service.process, {
                        "run_id": run, "camera_id": camera_id,
                        "stream_id": stream, "media_time_seconds": media_time,
                    }, result)
                except Exception:
                    response["tracking"] = {"status": "unavailable", "algorithm": "ByteTrack"}
                if request.headers.get("x-clearway-alert-monitor") == "paused":
                    await run_in_threadpool(live_monitor_service.pause, run, camera_id, stream)
                    return {**response, "alert_monitor": monitor_status("paused", "Live alerts are paused; display tracking remains active.")}
                try:
                    status = await run_in_threadpool(live_monitor_service.observe, run, camera, stream, media_time, bytes(raw),
                                                    {key: value for key, value in response.items() if key != "tracking"})
                except Exception:
                    status = monitor_status("unavailable", "Live review monitoring is unavailable; detection boxes remain separate.")
                return {**response, "alert_monitor": status}
            return response

        @application.get("/api/runs/{run_id}/incidents/{incident_id}/evidence")
        def live_evidence(run_id: UUID, incident_id: UUID):
            return Response(store.evidence(str(run_id), str(incident_id)), media_type="image/jpeg")

        @application.get("/api/state")
        def state():
            return snapshot()

        @application.post("/api/reset")
        def reset():
            store.reset()
            live_monitor_service.reset()
            live_tracking_service.reset()
            return snapshot()

        @application.post("/api/runs/{run_id}/replay")
        def replay(run_id: UUID, body: ReplayRequest):
            run = str(run_id)
            token = store.reserve_replay(run, body.source_id, body.analysis_mode)
            if token is None:
                return snapshot(expected_run_id=run, analysis_source_id=body.source_id)
            try:
                result = AnalysisResult.model_validate(analysis_service.analyze(body.source_id, body.analysis_mode)).model_dump()
                if any(o["timestamp_seconds"] > SOURCES[body.source_id]["duration_seconds"] for o in result["observations"]):
                    raise ValueError("Evidence is outside the clip.")
                if body.analysis_mode == "cached" and result["mode"] not in ("cached", "unavailable"):
                    raise ValueError("Cached mode cannot return another analysis mode.")
                if body.analysis_mode == "fixture" and result["mode"] not in ("fixture", "unavailable"):
                    raise ValueError("Fixture mode cannot return another analysis mode.")
            except Exception:
                # Provider errors may contain auth material; never reflect or log them.
                result = _unavailable()
            store.finish_replay(run, body.source_id, token, result, source_record(data, body.source_id))
            return snapshot(expected_run_id=run, analysis_source_id=body.source_id)

        @application.post("/api/runs/{run_id}/incidents/{incident_id}/confirm")
        def confirm(run_id: UUID, incident_id: UUID):
            return store.review(str(run_id), str(incident_id), "confirm")

        @application.post("/api/runs/{run_id}/incidents/{incident_id}/dismiss")
        def dismiss(run_id: UUID, incident_id: UUID):
            return store.review(str(run_id), str(incident_id), "dismiss")

        @application.get("/api/media/{source_id}/{kind}")
        def media(source_id: str, kind: str):
            return file_response(source_id, kind)

        @application.get("/api/labels")
        def labels():
            return {"labels": store.labels()}

        @application.post("/api/labels", status_code=201)
        def label(body: LabelRequest):
            if body.end_seconds > SOURCES[body.source_id]["duration_seconds"]:
                raise HTTPException(422, "Label interval extends beyond the source duration.")
            return store.add_label(body.model_dump())

        @application.get("/api/evaluation")
        def evaluation():
            entries = store.labels()
            return {
                "status": "awaiting_labels" if not entries else "labels_available",
                "label_count": len(entries),
                "scene_count": len({x["source_id"] for x in entries}),
                "metrics": None,
                "message": "Awaiting human labels." if not entries else "Labels saved. Run the frozen evaluation separately; no accuracy is inferred from labels alone.",
                "natural_recall": "recall not measurable on natural data",
            }

        @application.get("/")
        @application.get("/labels")
        def operator_page():
            return spa_response()

    return application


# Importing the read-only ASGI app does not create an additional analysis service.
app = create_app()
responder_app = create_app(read_only=True)
