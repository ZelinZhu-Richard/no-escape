import type { ImageDetections } from "./liveCameras";

export type AnalysisMode = "fixture" | "cached" | "fresh" | "unavailable";
export type ReviewStatus = "candidate" | "confirmed" | "dismissed" | "resolved";
export interface Location {
  latitude: number | null;
  longitude: number | null;
  quality: string;
  label: string;
}
export interface Source {
  id: string;
  title: string;
  source_mode: string;
  video_url: string;
  poster_url: string;
  duration_seconds: number;
  media_available: boolean;
  poster_available?: boolean;
  control_status: string;
  attribution: {
    creator: string;
    title: string;
    source_url: string;
    license: string;
    license_url: string;
  };
  location: Location;
}
export interface Incident {
  id: string;
  run_id: string;
  source_id: string;
  title: string;
  category: string;
  source_mode: string;
  analysis_mode: AnalysisMode;
  review_status: ReviewStatus;
  created_at: string;
  confirmed_at: string | null;
  evidence: { timestamp_seconds: number; observation: string }[];
  unknowns: string[];
  context_status: string;
  location: Location;
  provenance: {
    provider: string | null;
    model: string | null;
    prompt_version?: string;
    rule_version?: string;
    rule_thresholds?: Record<string, unknown>;
    fixture: boolean;
    cache_key: string | null;
  };
  responder_path: string;
  live_source?: Source;
  live_evidence?: {
    image_url: string;
    observed_at: string;
    media_time_seconds: number;
    window_seconds: number;
    rule: string;
    summary: string;
    detections: ImageDetections;
  };
}
export interface State {
  run: { id: string; created_at: string; status: string };
  incidents: Incident[];
  analysis: { mode: AnalysisMode; status: string; message: string };
  source_analyses?: Record<string, State["analysis"]>;
  telemetry: {
    network_inference_calls: number | null;
    cache_hits: number | null;
    fixture_runs: number | null;
    estimated_spend_usd: number | null;
    unknown_cost_requests?: number;
    ledger_status?: string;
  };
}
export interface Config {
  public_base_url: string | null;
  default_analysis_mode: AnalysisMode;
  map_mode: string;
  budgets: { gemini: number; claude: number; openai: number };
  model_configured: boolean;
  model_readiness?: { ready: boolean; message: string };
}
export interface ResponderData {
  incident: Incident;
  source: Source;
  run_id: string;
  status: string;
}
export interface Label {
  id: string;
  source_id: string;
  start_seconds: number;
  end_seconds: number;
  label: string;
  reviewer: string;
  note: string;
}

export interface DetectionBox {
  class_name: string;
  confidence: number;
  xyxy: [number, number, number, number];
}
export interface DetectionFrame {
  time_seconds: number;
  boxes: DetectionBox[];
  vehicle_count: number;
  person_count: number;
}
export interface DetectionResult {
  status: "available";
  source_id: string;
  model: {
    name: string;
    version: string;
    weights_sha256: string;
    license: string;
  };
  provenance: {
    kind: "local_yolo_cached";
    fixture: false;
    generated_at: string;
    source_sha256: string;
    preprocessing_version: string;
  };
  sample_fps: number;
  duration_seconds: number;
  video_width: number;
  video_height: number;
  frames: DetectionFrame[];
  gate: {
    evaluated_windows: number;
    passed_windows: number;
    suppressed_windows: number;
    baseline: string;
    estimated_calls_avoided: number;
    actual_model_calls: number;
    mode: "shadow";
    policy: string;
    note: string;
  };
}
export interface DetectionUnavailable {
  status: "unavailable";
  source_id: string;
  message?: string;
}
