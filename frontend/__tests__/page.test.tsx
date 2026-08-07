import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import Home from "../app/(dashboard)/dashboard/page";
import * as api from "../app/api";

// Mock the API client functions
vi.mock("../app/api", () => {
  return {
    fetchMetrics: vi.fn(),
    fetchTimeseries: vi.fn(),
    fetchAnomalies: vi.fn(),
  };
});

// Mock SWR hook
vi.mock("@/hooks/useApi", () => ({
  useApi: vi.fn()
}));

import { useApi } from "@/hooks/useApi";

describe("Overview Page Rendering", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test("renders list of metrics and displays the active anomaly warning banner", async () => {
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
      created_at: "2026-07-21T00:00:00Z",
    };

    const mockTimeseries: api.TimeseriesResponse = {
      metric_id: 1,
      mad: 5.0,
      points: [
        {
          date: "2026-07-20",
          value_total: 100.0,
          trend: 100.0,
          seasonal: 0.0,
          residual: 0.0,
          dimension_values: {},
        },
        {
          date: "2026-07-21",
          value_total: 80.0,
          trend: 100.0,
          seasonal: 0.0,
          residual: -20.0,
          dimension_values: {},
        },
      ],
    };

    const mockAnomalies: api.Anomaly[] = [
      {
        id: 10,
        metric_id: 1,
        date: "2026-07-21",
        severity_score: 4.0,
        type: "dip",
        z_score: -4.0,
        isolation_score: 0.0,
        status: "new",
        explanation_text: "Revenue is 20% below normal",
        created_at: "2026-07-21T00:00:00Z",
      },
    ];
    
    vi.mocked(useApi).mockImplementation((url: string | null) => {
      if (!url) return { data: null, isLoading: false, error: null, mutate: vi.fn() };
      if (url.endsWith("/metrics")) return { data: [mockMetric], isLoading: false, error: null, mutate: vi.fn() };
      if (url.includes("/timeseries")) return { data: mockTimeseries, isLoading: false, error: null, mutate: vi.fn() };
      if (url.includes("/anomalies")) return { data: mockAnomalies, isLoading: false, error: null, mutate: vi.fn() };
      return { data: null, isLoading: false, error: null, mutate: vi.fn() };
    });

    render(<Home />);

    // Expect loading state first, then card to render
    await waitFor(() => {
      expect(screen.getByText("Revenue Metric")).toBeInTheDocument();
    });

    // Check latest value is displayed
    expect(screen.getByText("80")).toBeInTheDocument();

    // Check that the unreviewed recent anomaly banner renders with calculated percent
    // pct_change = (80 - 100) / 100 * 100 = -20%
    expect(
      screen.getByText("⚠ Revenue Metric is 20% below its normal range")
    ).toBeInTheDocument();
  });

  test("does not display anomaly warning banner if anomaly is reviewed", async () => {
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
      created_at: "2026-07-21T00:00:00Z",
    };

    const mockTimeseries: api.TimeseriesResponse = {
      metric_id: 1,
      mad: 5.0,
      points: [
        {
          date: "2026-07-20",
          value_total: 100.0,
          trend: 100.0,
          seasonal: 0.0,
          residual: 0.0,
          dimension_values: {},
        },
        {
          date: "2026-07-21",
          value_total: 80.0,
          trend: 100.0,
          seasonal: 0.0,
          residual: -20.0,
          dimension_values: {},
        },
      ],
    };

    const mockAnomalies: api.Anomaly[] = [
      {
        id: 10,
        metric_id: 1,
        date: "2026-07-21",
        severity_score: 4.0,
        type: "dip",
        z_score: -4.0,
        isolation_score: 0.0,
        status: "reviewed",
        explanation_text: "Revenue is 20% below normal",
        created_at: "2026-07-21T00:00:00Z",
      },
    ];

    vi.mocked(useApi).mockImplementation((url: string | null) => {
      if (!url) return { data: null, isLoading: false, error: null, mutate: vi.fn() };
      if (url.endsWith("/metrics")) return { data: [mockMetric], isLoading: false, error: null, mutate: vi.fn() };
      if (url.includes("/timeseries")) return { data: mockTimeseries, isLoading: false, error: null, mutate: vi.fn() };
      if (url.includes("/anomalies")) return { data: mockAnomalies, isLoading: false, error: null, mutate: vi.fn() };
      return { data: null, isLoading: false, error: null, mutate: vi.fn() };
    });

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Revenue Metric")).toBeInTheDocument();
    });

    // Overview banner should not appear
    expect(
      screen.queryByText(/below its normal range/)
    ).not.toBeInTheDocument();
    
    // Shows regular dynamic timeseries action link
    expect(screen.getByText("View Timeseries Dashboard")).toBeInTheDocument();
  });
});
