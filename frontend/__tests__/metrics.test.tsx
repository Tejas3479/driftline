import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import MetricDetail from "../app/metrics/[id]/page";
import * as api from "../app/api";

// Mock the API client functions
vi.mock("../app/api", () => {
  return {
    fetchMetrics: vi.fn(),
    fetchTimeseries: vi.fn(),
    fetchAnomalies: vi.fn(),
  };
});

// Mock next/dynamic to render components synchronously in tests
vi.mock("next/dynamic", () => {
  return {
    default: (componentPromise: any) => {
      return function DynamicMock(props: any) {
        return (
          <div data-testid="mock-plotly-chart">
            Plotly Chart Rendered
            <div data-testid="mock-plotly-shapes-count">
              {props.anomalies?.length || 0}
            </div>
          </div>
        );
      };
    },
  };
});

// Mock react-plotly.js to prevent jsdom canvas rendering crashes
// and print the passed shapes list for inspection.
vi.mock("react-plotly.js", () => {
  return {
    default: (props: any) => (
      <div data-testid="mock-plotly-chart">
        Plotly Chart Rendered
        <div data-testid="mock-plotly-shapes-count">
          {props.layout?.shapes?.length || 0}
        </div>
      </div>
    ),
  };
});

describe("Metric Detail Page Rendering & Shading/Markers Checks", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test("renders metric detail layout, Plotly chart, and filters range", async () => {
    const mockMetric: api.Metric = {
      id: 58,
      workspace_id: 1,
      name: "Detail Test Metric",
      unit: "USD",
      direction_good: "up_is_good",
      sensitivity: "medium",
      grain: "daily",
      created_at: "2026-07-21T00:00:00Z",
    };
    vi.mocked(api.fetchMetrics).mockResolvedValue([mockMetric]);

    // Create 15 days of timeseries data
    const points: api.TimeseriesPoint[] = [];
    const baseDate = new Date("2026-07-01");
    for (let i = 0; i < 15; i++) {
      const d = new Date(baseDate);
      d.setDate(baseDate.getDate() + i);
      points.push({
        date: d.toISOString().split("T")[0],
        value_total: 100 + i,
        trend: 100.0,
        seasonal: 0.0,
        residual: i,
        dimension_values: {},
      });
    }

    const mockTimeseries: api.TimeseriesResponse = {
      metric_id: 58,
      mad: 8.5,
      points,
    };
    vi.mocked(api.fetchTimeseries).mockResolvedValue(mockTimeseries);

    // Mock 2 anomalies (on 2026-07-05 and 2026-07-15)
    const mockAnomalies: api.Anomaly[] = [
      {
        id: 1,
        metric_id: 58,
        date: "2026-07-05",
        severity_score: 3.5,
        type: "spike",
        z_score: 3.5,
        isolation_score: 0.0,
        status: "new",
        explanation_text: "High spike",
        created_at: "2026-07-21T00:00:00Z",
      },
      {
        id: 2,
        metric_id: 58,
        date: "2026-07-15",
        severity_score: 4.2,
        type: "volatility",
        z_score: 4.2,
        isolation_score: 0.0,
        status: "new",
        explanation_text: "High variance",
        created_at: "2026-07-21T00:00:00Z",
      },
    ];
    vi.mocked(api.fetchAnomalies).mockResolvedValue(mockAnomalies);

    render(<MetricDetail params={{ id: "58" }} />);

    // Expect loading state first, then page to render
    await waitFor(() => {
      expect(screen.getByText("Detail Test Metric")).toBeInTheDocument();
    });

    // Check that Plotly chart mock renders
    expect(screen.getByTestId("mock-plotly-chart")).toBeInTheDocument();

    // Verify all 2 anomalies are rendered as vertical dashed lines (shapes) in default 'ALL' view
    expect(screen.getByTestId("mock-plotly-shapes-count")).toHaveTextContent("2");
    const countHeader = screen.getByText("Anomaly Count");
    expect(countHeader).toBeInTheDocument();
    expect(countHeader.parentElement).toHaveTextContent("2 (2 new)");

    // Check table shows the anomalies
    expect(screen.getByText("2026-07-05")).toBeInTheDocument();
    expect(screen.getByText("2026-07-15")).toBeInTheDocument();

    // Click 7D filter button
    // This will filter to dates >= 2026-07-08 (since max date is 2026-07-15)
    const btn7d = screen.getByText("7D");
    fireEvent.click(btn7d);

    // After filtering to 7D, the anomaly on 2026-07-05 is excluded, and only 2026-07-15 remains (1 anomaly)
    await waitFor(() => {
      expect(screen.getByTestId("mock-plotly-shapes-count")).toHaveTextContent("1");
    });

    // Table should now exclude the 2026-07-05 anomaly
    expect(screen.queryByText("2026-07-05")).not.toBeInTheDocument();
    expect(screen.getByText("2026-07-15")).toBeInTheDocument();
  });
});
