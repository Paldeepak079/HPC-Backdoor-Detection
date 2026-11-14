export interface RunMeta {
  timestamp: string;
  n_rows: number;
  n_flagged: number;
  threshold: number;
  alpha: number;
  detectors: string[];
  config_hash: string;
}

export interface TopFeature {
  name: string;
  z_score: number;
  direction: 'high' | 'low';
}

export interface TraceRow {
  row_id: number;
  score: number;
  label: 0 | 1;
  top_features: TopFeature[];
  stage_scores: Record<string, number>; // detector name -> score
}

export interface Calibration {
  oof_scores: number[];
  oof_fpr_at_alpha: number;
  alpha: number;
  tau: number;
}

export interface RunData {
  meta: RunMeta;
  rows: TraceRow[];
  calibration: Calibration;
}
