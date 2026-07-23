export interface Metric {
  id: number;
  workspace_id: number;
  name: string;
  unit: string | null;
  direction_good: 'up_is_good' | 'down_is_good';
  sensitivity: 'low' | 'medium' | 'high';
  grain: 'daily' | 'weekly';
  z_score_weight?: number;
  created_at: string;
}

export interface TimeseriesPoint {
  date: string;
  value_total: number;
  trend: number | null;
  seasonal: number | null;
  residual: number | null;
  dimension_values: Record<string, string>;
}

export interface TimeseriesResponse {
  metric_id: number;
  mad: number | null;
  points: TimeseriesPoint[];
}

export interface Anomaly {
  id: number;
  metric_id: number;
  date: string;
  severity_score: number;
  type: 'spike' | 'dip' | 'level_shift' | 'volatility';
  z_score: number;
  isolation_score: number;
  status: 'new' | 'reviewed' | 'resolved' | 'false_positive';
  explanation_text: string | null;
  created_at: string;
}

export interface SegmentContribution {
  dimension: string;
  segment_value: string;
  actual_value: number;
  expected_value: number;
  delta: number;
  contribution_pct: number;
}

export interface StructuralImportance {
  feature: string;
  importance: number;
}

export interface AnomalyDriversResponse {
  anomaly_id: number;
  metric_id: number;
  explanation_text: string;
  primary_dimension: string | null;
  ranked_segments: SegmentContribution[];
  structural_importance: StructuralImportance[];
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchMetrics(): Promise<Metric[]> {
  const res = await fetch(`${API_BASE_URL}/metrics`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Failed to fetch metrics: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchTimeseries(metricId: number, segment?: string): Promise<TimeseriesResponse> {
  const url = segment
    ? `${API_BASE_URL}/metrics/${metricId}/timeseries?segment=${encodeURIComponent(segment)}`
    : `${API_BASE_URL}/metrics/${metricId}/timeseries`;
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Failed to fetch timeseries for metric ${metricId}: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchAnomalies(metricId: number): Promise<Anomaly[]> {
  const res = await fetch(`${API_BASE_URL}/metrics/${metricId}/anomalies`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Failed to fetch anomalies for metric ${metricId}: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchAnomalyDetail(anomalyId: number): Promise<Anomaly> {
  const res = await fetch(`${API_BASE_URL}/anomalies/${anomalyId}`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Failed to fetch anomaly detail for anomaly ${anomalyId}: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchAnomalyDrivers(anomalyId: number): Promise<AnomalyDriversResponse> {
  const res = await fetch(`${API_BASE_URL}/anomalies/${anomalyId}/drivers`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Failed to fetch drivers for anomaly ${anomalyId}: ${res.statusText}`);
  }
  return res.json();
}

export async function submitAnomalyFeedback(
  anomalyId: number,
  status: 'new' | 'reviewed' | 'resolved' | 'false_positive'
): Promise<Anomaly> {
  const res = await fetch(`${API_BASE_URL}/anomalies/${anomalyId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) {
    throw new Error(`Failed to submit feedback for anomaly ${anomalyId}: ${res.statusText}`);
  }
  return res.json();
}

export interface ForecastPoint {
  metric_id: number;
  forecast_date: string;
  horizon_days: number;
  p10: number;
  p50: number;
  p90: number;
  dimension_values: Record<string, string>;
  model_version: string;
}

export interface ForecastResult {
  metric_id: number;
  horizon_days: number;
  as_of_date: string;
  model_version: string;
  low_confidence: boolean;
  forecasts: ForecastPoint[];
}

export interface AccuracyPoint {
  date: string;
  predicted_p50: number;
  actual: number;
  abs_error: number;
  abs_pct_error: number | null;
  in_bounds: boolean | null;
  predicted_p10: number | null;
  predicted_p90: number | null;
  used_ml_model: boolean;
}

export interface AccuracyResponse {
  metric_id: number;
  horizon_days: number;
  model_backend: string;
  mape: number | null;
  mae: number | null;
  coverage_pct: number | null;
  total_evaluations: number;
  ml_evaluations: number;
  points: AccuracyPoint[];
}

export async function fetchForecast(
  metricId: number,
  horizon: number = 30,
  backend: string = 'lightgbm',
  signal?: AbortSignal
): Promise<ForecastResult> {
  const url = `${API_BASE_URL}/metrics/${metricId}/forecast?horizon=${horizon}&backend=${backend}`;
  const res = await fetch(url, { cache: 'no-store', signal });
  if (!res.ok) {
    throw new Error(`Failed to fetch forecast for metric ${metricId}: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchAccuracy(
  metricId: number,
  horizon: number = 30,
  backend: string = 'lightgbm',
  signal?: AbortSignal
): Promise<AccuracyResponse> {
  const url = `${API_BASE_URL}/metrics/${metricId}/accuracy?horizon=${horizon}&backend=${backend}`;
  const res = await fetch(url, { cache: 'no-store', signal });
  if (!res.ok) {
    throw new Error(`Failed to fetch forecast accuracy for metric ${metricId}: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchSegmentComparison(
  metricId: number,
  dimension?: string,
  range: string = 'all',
  startDate?: string,
  endDate?: string,
  signal?: AbortSignal
): Promise<any> {
  const params = new URLSearchParams();
  if (dimension) params.set('dimension', dimension);
  if (range) params.set('range', range);
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);

  const url = `${API_BASE_URL}/metrics/${metricId}/segment-comparison?${params.toString()}`;
  const res = await fetch(url, { cache: 'no-store', signal });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const errJson = await res.json();
      if (errJson.detail) detail = errJson.detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}


