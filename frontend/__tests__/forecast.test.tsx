import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import ForecastPage from "../app/(dashboard)/metrics/[id]/forecast/page";
import * as api from "../app/api";
import { useApi } from "@/hooks/useApi";

// Mock the API client functions
vi.mock("../app/api", () => {
  return {
    fetchMetrics: vi.fn(),
    fetchTimeseries: vi.fn(),
    fetchForecast: vi.fn(),
    fetchAccuracy: vi.fn(),
  };
});

// Mock SWR hook
vi.mock("@/hooks/useApi", () => ({
  useApi: vi.fn()
}));

// Mock next/dynamic to render Plotly components synchronously in tests
vi.mock("next/dynamic", () => {
  return {
    default: (componentPromise: any) => {
      return function DynamicMock(props: any) {
        return (
          <div data-testid="mock-plotly-chart">
            Plotly Component Rendered
            {props.forecastPoints && (
              <div data-testid="mock-forecast-points-count">
                {props.forecastPoints.length}
              </div>
            )}
            {props.points && (
              <div data-testid="mock-accuracy-points-count">
                {props.points.length}
              </div>
            )}
          </div>
        );
      };
    },
  };
});

// Mock react-plotly.js to prevent jsdom canvas rendering crashes
vi.mock("react-plotly.js", () => {
  return {
    default: () => <div data-testid="mock-plotly-chart">Plotly Chart Rendered</div>,
  };
});

// Mock CountUp to render final value synchronously
vi.mock("@/components/CountUp", () => {
  return {
    default: ({ to, decimals = 0, suffix = "" }: any) => {
      return <span>{(Number(to)).toFixed(decimals)}{suffix}</span>;
    },
  };
});

describe("Forecast Page & Model Track Record Rendering Suite", () => {
  const mockMetric: api.Metric = {
    id: 1,
    workspace_id: 1,
    name: "Revenue Metric",
    unit: "USD",
    direction_good: "up_is_good",
    sensitivity: "medium",
    grain: "daily",
    z_score_weight: 1.0,
    structural_importance: [],
    created_at: "2026-07-01T00:00:00Z",
  };

  const mockTimeseries: api.TimeseriesResponse = {
    metric_id: 1,
    mad: 10.0,
    points: [
      {
        date: "2026-07-01",
        value_total: 100,
        trend: 100,
        seasonal: 0,
        residual: 0,
        dimension_values: {},
      },
    ],
  };

  beforeEach(() => {
    vi.resetAllMocks();
  });

  test("renders forecast page with mock forecast & accuracy stats (MAPE and coverage)", async () => {
    vi.mocked(api.fetchMetrics).mockResolvedValue([mockMetric]);
    vi.mocked(api.fetchTimeseries).mockResolvedValue(mockTimeseries);

    const mockForecast: api.ForecastResult = {
      metric_id: 1,
      horizon_days: 30,
      as_of_date: "2026-07-01",
      model_version: "lightgbm-v1",
      low_confidence: false,
      forecasts: [
        {
          metric_id: 1,
          forecast_date: "2026-07-02",
          horizon_days: 1,
          p10: 95,
          p50: 105,
          p90: 115,
          dimension_values: {},
          model_version: "lightgbm-v1",
        },
      ],
    };
    vi.mocked(api.fetchForecast).mockResolvedValue(mockForecast);

    const mockAccuracy: api.AccuracyResponse = {
      metric_id: 1,
      horizon_days: 30,
      model_backend: "lightgbm",
      mape: 0.0276, // 2.76%
      mae: 2.5,
      coverage_pct: 0.8, // 80.0%
      total_evaluations: 12,
      ml_evaluations: 12,
      points: [
        {
          date: "2026-06-24",
          predicted_p50: 102,
          actual: 100,
          abs_error: 2,
          abs_pct_error: 0.02,
          in_bounds: true,
          predicted_p10: 90,
          predicted_p90: 110,
          used_ml_model: true,
        },
      ],
    };
    vi.mocked(api.fetchAccuracy).mockResolvedValue(mockAccuracy);

    vi.mocked(useApi).mockImplementation((url: string | null) => {
      if (!url) return { data: null, isLoading: false, error: null, mutate: vi.fn() };
      if (url.endsWith("/metrics")) return { data: [mockMetric], isLoading: false, error: null, mutate: vi.fn() };
      if (url.includes("/timeseries")) return { data: mockTimeseries, isLoading: false, error: null, mutate: vi.fn() };
      if (url.includes("/forecast")) return { data: mockForecast, isLoading: false, error: null, mutate: vi.fn() };
      if (url.includes("/accuracy")) return { data: mockAccuracy, isLoading: false, error: null, mutate: vi.fn() };
      return { data: null, isLoading: false, error: null, mutate: vi.fn() };
    });

    render(<ForecastPage params={{ id: "1" }} />);

    // Wait for page to render
    await waitFor(() => {
      expect(screen.getByText("Revenue Metric Forecast")).toBeInTheDocument();
    });

    // Verify stats panel values
    expect(screen.getByText("2.76%")).toBeInTheDocument(); // MAPE
    expect(screen.getByText("80.0%")).toBeInTheDocument(); // Coverage %
    expect(screen.getByText("Evaluated Folds")).toBeInTheDocument(); // Evaluated folds card header
    expect(screen.getByText("lightgbm-v1")).toBeInTheDocument(); // Model version



    // Verify low_confidence banner is NOT present
    expect(screen.queryByText(/Seasonal Estimate Active/i)).not.toBeInTheDocument();

    // Verify mock plotly charts render
    const charts = screen.getAllByTestId("mock-plotly-chart");
    expect(charts.length).toBeGreaterThanOrEqual(2);
  });

  test("displays LowConfidenceBanner when low_confidence=true", async () => {
    vi.mocked(api.fetchMetrics).mockResolvedValue([mockMetric]);
    vi.mocked(api.fetchTimeseries).mockResolvedValue(mockTimeseries);

    const mockForecast: api.ForecastResult = {
      metric_id: 1,
      horizon_days: 30,
      as_of_date: "2026-07-01",
      model_version: "naive-seasonal-v1",
      low_confidence: true,
      forecasts: [],
    };
    vi.mocked(api.fetchForecast).mockResolvedValue(mockForecast);

    const mockAccuracy: api.AccuracyResponse = {
      metric_id: 1,
      horizon_days: 30,
      model_backend: "lightgbm",
      mape: null,
      mae: null,
      coverage_pct: null,
      total_evaluations: 0,
      ml_evaluations: 0,
      points: [],
    };
    vi.mocked(api.fetchAccuracy).mockResolvedValue(mockAccuracy);

    vi.mocked(useApi).mockImplementation((url: string | null) => {
      if (!url) return { data: null, isLoading: false, error: null, mutate: vi.fn() };
      if (url.endsWith("/metrics")) return { data: [mockMetric], isLoading: false, error: null, mutate: vi.fn() };
      if (url.includes("/timeseries")) return { data: mockTimeseries, isLoading: false, error: null, mutate: vi.fn() };
      if (url.includes("/forecast")) return { data: mockForecast, isLoading: false, error: null, mutate: vi.fn() };
      if (url.includes("/accuracy")) return { data: mockAccuracy, isLoading: false, error: null, mutate: vi.fn() };
      return { data: null, isLoading: false, error: null, mutate: vi.fn() };
    });

    render(<ForecastPage params={{ id: "1" }} />);

    await waitFor(() => {
      expect(screen.getByText(/Seasonal Estimate Active \(Cold-Start Mode\)/i)).toBeInTheDocument();
    });

    // Check fallback text for null stats
    expect(screen.getByText("N/A (Cold start)")).toBeInTheDocument();
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });
});
