export interface User {
  id: number;
  email: string;
  workspace_id: number;
  role: string;
  is_active: boolean;
}

export interface Metric {
  id: number;
  workspace_id: number;
  name: string;
  unit: string | null;
  direction_good: 'up_is_good' | 'down_is_good';
  sensitivity: 'low' | 'medium' | 'high';
  grain: 'daily' | 'weekly';
  z_score_weight: number;
  structural_importance: StructuralImportance[];
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

export interface VegaLiteSpec {
  $schema?: string;
  data?: Record<string, unknown>;
  facet?: Record<string, unknown>;
  spec?: Record<string, unknown>;
  title?: string | Record<string, unknown>;
  [key: string]: unknown;
}

async function parseErrorDetail(res: Response, fallbackPrefix: string): Promise<Error> {
  let detail = res.statusText;
  try {
    const errJson = await res.json();
    if (errJson.detail) {
      detail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
    }
  } catch {}
  return new Error(`${fallbackPrefix}: ${detail}`);
}

async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const token = typeof window !== 'undefined' ? localStorage.getItem("driftline_token") : null;
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  
  const res = await fetch(input, {
    ...init,
    headers,
  });
  
  if (res.status === 401 && typeof window !== 'undefined') {
    localStorage.removeItem("driftline_token");
    if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
      window.location.href = '/login';
    }
  }
  return res;
}

export async function fetchMetrics(): Promise<Metric[]> {
  const res = await apiFetch(`${API_BASE_URL}/metrics`, { cache: 'no-store' });
  if (!res.ok) {
    throw await parseErrorDetail(res, 'Failed to fetch metrics');
  }
  return res.json();
}

export async function fetchTimeseries(metricId: number, segment?: string): Promise<TimeseriesResponse> {
  const url = segment
    ? `${API_BASE_URL}/metrics/${metricId}/timeseries?segment=${encodeURIComponent(segment)}`
    : `${API_BASE_URL}/metrics/${metricId}/timeseries`;
  const res = await apiFetch(url, { cache: 'no-store' });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to fetch timeseries for metric ${metricId}`);
  }
  return res.json();
}

export async function fetchAnomalies(metricId: number): Promise<Anomaly[]> {
  const res = await apiFetch(`${API_BASE_URL}/metrics/${metricId}/anomalies`, { cache: 'no-store' });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to fetch anomalies for metric ${metricId}`);
  }
  return res.json();
}

export async function fetchAnomalyDetail(anomalyId: number): Promise<Anomaly> {
  const res = await apiFetch(`${API_BASE_URL}/anomalies/${anomalyId}`, { cache: 'no-store' });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to fetch anomaly detail for anomaly ${anomalyId}`);
  }
  return res.json();
}

export async function fetchAnomalyDrivers(anomalyId: number): Promise<AnomalyDriversResponse> {
  const res = await apiFetch(`${API_BASE_URL}/anomalies/${anomalyId}/drivers`, { cache: 'no-store' });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to fetch drivers for anomaly ${anomalyId}`);
  }
  return res.json();
}

export async function submitAnomalyFeedback(
  anomalyId: number,
  status: 'new' | 'reviewed' | 'resolved' | 'false_positive'
): Promise<Anomaly> {
  const res = await apiFetch(`${API_BASE_URL}/anomalies/${anomalyId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to submit feedback for anomaly ${anomalyId}`);
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
  const res = await apiFetch(url, { cache: 'no-store', signal });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to fetch forecast for metric ${metricId}`);
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
  const res = await apiFetch(url, { cache: 'no-store', signal });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to fetch forecast accuracy for metric ${metricId}`);
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
): Promise<VegaLiteSpec> {
  const params = new URLSearchParams();
  if (dimension) params.set('dimension', dimension);
  if (range) params.set('range', range);
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);

  const url = `${API_BASE_URL}/metrics/${metricId}/segment-comparison?${params.toString()}`;
  const res = await apiFetch(url, { cache: 'no-store', signal });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to fetch segment comparison for metric ${metricId}`);
  }
  return res.json();
}

export interface GlobalAnomaly {
  id: number;
  metric_id: number;
  metric_name: string;
  date: string;
  severity_score: number;
  anomaly_type: string;
  status: string;
  explanation_excerpt: string | null;
}

export async function fetchGlobalAnomalies(
  status?: string,
  metricId?: number,
  signal?: AbortSignal
): Promise<GlobalAnomaly[]> {
  const params = new URLSearchParams();
  if (status && status.toLowerCase() !== 'all') params.set('status', status.toLowerCase());
  if (metricId) params.set('metric_id', metricId.toString());

  const url = `${API_BASE_URL}/anomalies?${params.toString()}`;
  const res = await apiFetch(url, { cache: 'no-store', signal });
  if (!res.ok) {
    throw await parseErrorDetail(res, 'Failed to fetch global anomalies log');
  }
  return res.json();
}

export interface MetricCreateSchema {
  workspace_id?: number;
  name: string;
  unit: string | null;
  direction_good: 'up_is_good' | 'down_is_good';
  sensitivity: 'low' | 'medium' | 'high';
  grain: 'daily' | 'weekly';
}

export interface ValidationErrorSchema {
  row_number: number;
  column: string;
  issue: string;
  invalid_value: string | null;
}

export interface ColumnMappingSchema {
  date_col: string;
  value_col: string;
  dimension_cols: string[];
}

export interface ValidationReportSchema {
  is_valid: boolean;
  total_rows: number;
  errors: ValidationErrorSchema[];
  date_gaps: string[];
  inferred_mapping: ColumnMappingSchema;
}

export interface InspectionResponseSchema {
  metric_id: number;
  inferred_mapping: ColumnMappingSchema;
  validation_report: ValidationReportSchema;
  rows: Record<string, any>[];
}

export interface DataConfirmSchema {
  date_col: string;
  value_col: string;
  dimension_cols: string[];
  rows: Record<string, any>[];
  replace?: boolean;
}

export interface DataConfirmResponseSchema {
  metric_id: number;
  inserted_count: number;
  updated_count: number;
  total_observations: number;
}

export async function createMetric(payload: MetricCreateSchema): Promise<Metric> {
  const res = await apiFetch(`${API_BASE_URL}/metrics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw await parseErrorDetail(res, 'Failed to create metric');
  }
  return res.json();
}

export interface MetricUpdateSchema {
  sensitivity?: 'low' | 'medium' | 'high';
  direction_good?: 'up_is_good' | 'down_is_good';
  z_score_weight?: number;
}

export async function updateMetric(metricId: number, payload: MetricUpdateSchema): Promise<Metric> {
  const res = await apiFetch(`${API_BASE_URL}/metrics/${metricId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to update metric ${metricId}`);
  }
  return res.json();
}

export async function deleteMetric(metricId: number): Promise<void> {
  const res = await apiFetch(`${API_BASE_URL}/metrics/${metricId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to delete metric ${metricId}`);
  }
}

export async function inspectCsvData(metricId: number, file: File): Promise<InspectionResponseSchema> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await apiFetch(`${API_BASE_URL}/metrics/${metricId}/data`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to inspect CSV data for metric ${metricId}`);
  }
  return res.json();
}

export async function confirmCsvData(metricId: number, payload: DataConfirmSchema): Promise<DataConfirmResponseSchema> {
  const res = await apiFetch(`${API_BASE_URL}/metrics/${metricId}/data/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to confirm CSV data for metric ${metricId}`);
  }
  return res.json();
}

export interface AppNotification {
  id: number;
  workspace_id: number;
  metric_id: number;
  anomaly_id: number;
  title: string;
  message: string;
  severity_score: number;
  is_read: boolean;
  created_at: string;
}

export async function fetchNotifications(limit: number = 50): Promise<AppNotification[]> {
  const url = `${API_BASE_URL}/notifications?limit=${limit}`;
  const res = await apiFetch(url, { cache: 'no-store' });
  if (!res.ok) {
    throw await parseErrorDetail(res, 'Failed to fetch notifications');
  }
  return res.json();
}

export async function markNotificationRead(id: number): Promise<AppNotification> {
  const url = `${API_BASE_URL}/notifications/${id}/read`;
  const res = await apiFetch(url, { method: 'PATCH', cache: 'no-store' });
  if (!res.ok) {
    throw await parseErrorDetail(res, `Failed to mark notification ${id} as read`);
  }
  return res.json();
}

export interface WorkspaceUserCreate {
  email: string;
  password?: string;
  role: string;
}

export interface WorkspaceUserUpdate {
  role: string;
}

export async function fetchTeamMembers(workspaceId: number): Promise<User[]> {
  const url = `${API_BASE_URL}/workspaces/${workspaceId}/users`;
  const res = await apiFetch(url, { cache: 'no-store' });
  if (!res.ok) {
    throw await parseErrorDetail(res, 'Failed to fetch team members');
  }
  return res.json();
}

export async function addTeamMember(workspaceId: number, payload: WorkspaceUserCreate): Promise<User> {
  const url = `${API_BASE_URL}/workspaces/${workspaceId}/users`;
  const res = await apiFetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw await parseErrorDetail(res, 'Failed to add team member');
  }
  return res.json();
}

export async function updateTeamMemberRole(userId: number, payload: WorkspaceUserUpdate): Promise<User> {
  const url = `${API_BASE_URL}/workspaces/users/${userId}`;
  const res = await apiFetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw await parseErrorDetail(res, 'Failed to update team member role');
  }
  return res.json();
}

export async function removeTeamMember(userId: number): Promise<void> {
  const url = `${API_BASE_URL}/workspaces/users/${userId}`;
  const res = await apiFetch(url, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw await parseErrorDetail(res, 'Failed to remove team member');
  }
}
