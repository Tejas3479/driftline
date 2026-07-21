export interface Metric {
  id: number;
  workspace_id: number;
  name: str;
  unit: string | null;
  direction_good: 'up_is_good' | 'down_is_good';
  sensitivity: 'low' | 'medium' | 'high';
  grain: 'daily' | 'weekly';
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
  status: 'new' | 'reviewed' | 'snoozed' | 'dismissed';
  explanation_text: string | null;
  created_at: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchMetrics(): Promise<Metric[]> {
  const res = await fetch(`${API_BASE_URL}/metrics`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Failed to fetch metrics: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchTimeseries(metricId: number): Promise<TimeseriesResponse> {
  const res = await fetch(`${API_BASE_URL}/metrics/${metricId}/timeseries`, { cache: 'no-store' });
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
