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
    prompt_version: string;
    fixture: boolean;
    cache_key: string | null;
  };
  responder_path: string;
}
export interface State {
  run: { id: string; created_at: string; status: string };
  incidents: Incident[];
  analysis: { mode: AnalysisMode; status: string; message: string };
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
