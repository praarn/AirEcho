export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserOut {
  id: number;
  email: string;
  created_at: string;
}

export interface LocationOut {
  id: number;
  label: string;
  lat: number;
  lng: number;
  nearest_station_id: number | null;
  distance_km: number | null;
  resolved_at: string | null;
}

export interface ExposureWindowOut {
  id: number;
  location_id: number;
  window_type: "6h" | "24h" | "72h";
  window_start: string;
  window_end: string;
  avg_pm25: number | null;
  avg_pm10: number | null;
  avg_no2: number | null;
  avg_o3: number | null;
  avg_temp: number | null;
  avg_humidity: number | null;
  data_coverage_pct: number;
  expected_slots: number;
  observed_slots: number;
  computed_at: string;
}

export interface CoverageSummary {
  overall_coverage_pct: number;
  by_window_type: Record<string, number>;
  n_windows: number;
  worst_window: ExposureWindowOut | null;
}

export interface SymptomOut {
  id: number;
  severity: number;
  notes: string | null;
  peak_flow_value: number | null;
  peak_flow_photo_url: string | null;
  ocr_confidence: number | null;
  manually_confirmed: boolean;
  logged_at: string;
  needs_confirmation: boolean;
}

export interface OcrResult {
  raw_text: string;
  extracted_value: number | null;
  confidence: number;
  needs_confirmation: boolean;
  engine: string;
}

export interface ExplanationItem {
  feature: string;
  importance: number;
  current_value: number;
  reads_as: string;
}

export interface RiskPredictionOut {
  risk_score: number;
  model_type: "personal" | "population_fallback" | "heuristic";
  algorithm: string;
  model_version: number;
  is_personalized: boolean;
  disclaimer: string;
  lag_features: Record<string, number>;
  explanation: ExplanationItem[];
  data_coverage_pct: number | null;
  predicted_at: string;
}

export interface RiskModelOut {
  id: number;
  user_id: number | null;
  model_type: string;
  algorithm: string;
  model_version: number;
  trained_at: string;
  n_train: number;
  n_test: number;
  mae: number | null;
  baseline_mae: number | null;
  feature_importance_json: Record<string, unknown>;
}

export interface Citation {
  marker: string;
  section_ref: string;
  document_title: string;
  score: number;
  snippet: string;
}

export interface AdvisoryOut {
  response_text: string;
  citations: Citation[];
  refused: boolean;
  context_used: Record<string, unknown>;
  created_at: string;
}

export interface StationOut {
  id: number;
  source: string;
  location_name: string;
  lat: number;
  lng: number;
  nominal_cadence_minutes: number;
  last_seen_at: string | null;
}

export interface IngestionEvent {
  id: number;
  station_id: number | null;
  source: string;
  status: string;
  detail: string | null;
  rows_ingested: number;
  created_at: string;
}
