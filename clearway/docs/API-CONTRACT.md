# Overnight integration contract

Agreed API, relative to the project. JSON uses snake_case. Times are UTC ISO strings; IDs are UUIDs. All writes are local operator-only. Responder service is read-only and only serves a selected run's incident/evidence.

## Data

`Source`: `{id, title, source_mode: "recorded_replay", video_url, poster_url, duration_seconds, media_available, control_status, attribution: {creator, title, source_url, license, license_url}, location: {latitude, longitude, quality, label}}`.

Source IDs: `road-obstruction`, `street-traffic`, `traffic-jam`. For selected primary, location is simulated at 35.9940,-78.8986; label “Demo placement · Durham”. Real source coordinates remain null. Poster/video URLs are allowlisted local media routes. Fixture analysis must not require media to be committed, but missing media must be visible. All footage stays ignored.

`Incident`: `{id, run_id, source_id, title, category, source_mode, analysis_mode, review_status, created_at, confirmed_at, evidence: [{timestamp_seconds, observation}], unknowns: string[], context_status: "not_applicable", location, provenance: {provider, model, prompt_version, fixture, cache_key}, responder_path}`.

`State`: `{run: {id, created_at, status}, incidents: Incident[], analysis: {mode, status, message}, telemetry: {network_inference_calls, cache_hits, fixture_runs, estimated_spend_usd}}`.

Analysis modes `fixture | cached | fresh | unavailable`; source modes independent. Review `candidate | confirmed | dismissed | resolved`. Primary fixture gives one candidate, never a model result. Control fixture gives no candidate with explicit fixture/no human-label status. Default mode fixture. Cached mode is strictly network-disabled and shows unavailable on missing genuine cache.

## Operator endpoints

- `GET /api/health` → `{status:"ok"}`.
- `GET /api/config` → `{public_base_url: string|null, default_analysis_mode:"fixture", map_mode:"basic", budgets:{gemini:0,claude:10,openai:0}, model_configured:bool}`. No secret values.
- `GET /api/sources` → `{sources: Source[]}`.
- `GET /api/state` → State.
- `POST /api/reset` body `{}` → new State, invalidates old run and cancels/ignores old jobs.
- `POST /api/runs/{run_id}/replay` body `{source_id, analysis_mode:"fixture"|"cached"|"fresh"}` → State. Idempotent per run/source; repeated replay doesn't duplicate candidate. Returns 409 for old run. Async model completion must check run is still current. Fixture result can be immediate; UI owns the video playback/progress.
- `POST /api/runs/{run_id}/incidents/{id}/confirm` body `{}` → Incident; idempotent, 409 old run.
- `POST /api/runs/{run_id}/incidents/{id}/dismiss` body `{}` → Incident.
- `GET /api/labels` → `{labels: Label[]}`.
- `POST /api/labels` body `{source_id, start_seconds, end_seconds, label:"road_obstruction"|"normal"|"queue"|"uncertain", reviewer, note}` → saved Label with ID/time. Human submission only; starts empty. Validate intervals against clip duration.
- `GET /api/evaluation` → basic labels/status result; root/eval implementer may refine additive fields. No labels → `{status:"awaiting_labels", label_count:0,...}`.

## Responder endpoints (available on both apps)

- UI `/respond/{run_id}/{id}`: a phone layout, polls below every 2 s. Frontend can be one SPA with route parsing.
- `GET /api/respond/{run_id}/{id}` → `{incident: Incident, source: Source, run_id, status:"active"}`. Old/reset run returns HTTP 410 with explicit expired detail; unknown incident 404. Candidate vs confirmed shown accurately, with no operator controls.
- Responder media should be served only for an active selected run/incident at `/api/respond/{run_id}/{id}/media/{kind}` where kind `video|poster`; reject expired/unknown. Returned Source on responder uses these URLs.

Operator video `/api/media/{source_id}/{kind}`; allowlist only video/poster, never arbitrary filesystem paths. Support video Range requests via framework FileResponse. Browser frontend dev proxy `/api` to 127.0.0.1:8000. Built frontend served by backend. Main operator app 127.0.0.1:8000, separate read-only responder app 127.0.0.1:8001; only the latter can be exposed manually in morning instructions.

## Python analysis module contract

`clearway/api/analysis.py` exports `AnalysisService(data_dir: Path)` with `analyze(source_id: str, mode: str) -> dict` (synchronous, backend may call in threadpool), `telemetry() -> dict`. Result `{mode, status:"complete"|"unavailable", message, observations:[{timestamp_seconds,observation}], candidate: bool, title, category, unknowns:[], provenance:{provider,model,prompt_version,fixture,cache_key}}`. Default zero billing; fixtures explicit; cached only loads genuine stored responses. Unknown source fails safely. Tests use temp data; no live API calls. Module standalone; backend creates incident/state from it.

Backend owns API/storage/config/source metadata and tests. Analysis agent owns analysis.py and analysis tests. Frontend owns web/. Root owns integration/evaluation/scripts and final docs. Propose contract changes to root rather than making incompatible assumptions.
