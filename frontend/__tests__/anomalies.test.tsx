import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import AnomalyDetailPage from "../app/anomalies/[id]/page";
import * as api from "../app/api";

// Mock API client functions
vi.mock("../app/api", () => {
  return {
    fetchAnomalyDetail: vi.fn(),
    fetchMetrics: vi.fn(),
    fetchAnomalyDrivers: vi.fn(),
    fetchTimeseries: vi.fn(),
    fetchAnomalies: vi.fn(),
    submitAnomalyFeedback: vi.fn(),
  };
});

// Mock react-plotly.js to prevent jsdom canvas rendering crashes
vi.mock("react-plotly.js", () => {
  return {
    default: (props: any) => (
      <div data-testid="mock-plotly-chart" onClick={props.onClick ? () => props.onClick({ points: [{ pointIndex: 0 }] }) : undefined}>
        Plotly Chart Rendered
        <div data-testid="mock-plotly-data-count">
          {props.data?.length || 0}
        </div>
      </div>
    ),
  };
});

describe("Anomaly Detail Page & Driver Component Test Suite", () => {
  const mockMetric: api.Metric = {
    id: 10,
    workspace_id: 1,
    name: "Revenue Metric",
    unit: "USD",
    direction_good: "up_is_good",
    sensitivity: "medium",
    grain: "daily",
    created_at: "2026-07-21T00:00:00Z",
  };

  const mockAnomaly: api.Anomaly = {
    id: 99,
    metric_id: 10,
    date: "2026-02-05",
    severity_score: 8.5,
    type: "dip",
    z_score: -3.8,
    isolation_score: 0.9,
    status: "new",
    explanation_text: "Declined 150 (30%) vs baseline. channel: paid accounted for 80% of the change.",
    created_at: "2026-07-21T00:00:00Z",
  };

  const mockDrivers: api.AnomalyDriversResponse = {
    anomaly_id: 99,
    metric_id: 10,
    explanation_text: "Declined 150 (30%) vs baseline. channel: paid accounted for 80% of the change.",
    primary_dimension: "channel",
    ranked_segments: [
      {
        dimension: "channel",
        segment_value: "paid",
        actual_value: 20,
        expected_value: 100,
        delta: -80,
        contribution_pct: -0.8,
      },
      {
        dimension: "channel",
        segment_value: "organic",
        actual_value: 90,
        expected_value: 100,
        delta: -10,
        contribution_pct: -0.1,
      },
    ],
    structural_importance: [
      { feature: "channel", importance: 42.5 },
      { feature: "day_of_week", importance: 20.0 },
    ],
  };

  const mockTimeseries: api.TimeseriesResponse = {
    metric_id: 10,
    mad: 5.2,
    points: [
      {
        date: "2026-02-05",
        value_total: 110,
        trend: 140,
        seasonal: 0,
        residual: -30,
        dimension_values: {},
      },
    ],
  };

  beforeEach(() => {
    vi.resetAllMocks();
  });

  test("renders anomaly detail layout, explanation text, and structural importance callout", async () => {
    vi.mocked(api.fetchAnomalyDetail).mockResolvedValue(mockAnomaly);
    vi.mocked(api.fetchMetrics).mockResolvedValue([mockMetric]);
    vi.mocked(api.fetchAnomalyDrivers).mockResolvedValue(mockDrivers);
    vi.mocked(api.fetchTimeseries).mockResolvedValue(mockTimeseries);

    render(<AnomalyDetailPage params={{ id: "99" }} />);

    // Wait for page to finish loading
    await waitFor(() => {
      expect(screen.getByText("ANOMALY #99")).toBeInTheDocument();
    });

    // Check explanation text is prominently displayed
    expect(
      screen.getByText(
        `"${mockDrivers.explanation_text}"`
      )
    ).toBeInTheDocument();

    // Check primary dimension badge
    expect(screen.getByText("Primary")).toBeInTheDocument();

    // Check structural importance callout
    expect(screen.getByText(/Historically,/)).toBeInTheDocument();
    expect(screen.getByText("channel")).toBeInTheDocument();
  });

  test("submits false_positive status cleanly to feedback endpoint when False Positive is clicked", async () => {
    vi.mocked(api.fetchAnomalyDetail).mockResolvedValue(mockAnomaly);
    vi.mocked(api.fetchMetrics).mockResolvedValue([mockMetric]);
    vi.mocked(api.fetchAnomalyDrivers).mockResolvedValue(mockDrivers);
    vi.mocked(api.fetchTimeseries).mockResolvedValue(mockTimeseries);

    const updatedAnomaly: api.Anomaly = {
      ...mockAnomaly,
      status: "false_positive",
      severity_score: 4.2, // rescaled
    };
    vi.mocked(api.submitAnomalyFeedback).mockResolvedValue(updatedAnomaly);

    render(<AnomalyDetailPage params={{ id: "99" }} />);

    await waitFor(() => {
      expect(screen.getByText("ANOMALY #99")).toBeInTheDocument();
    });

    // Click False Positive button
    const fpBtn = screen.getByText("False Positive");
    fireEvent.click(fpBtn);

    await waitFor(() => {
      expect(api.submitAnomalyFeedback).toHaveBeenCalledWith(99, "false_positive");
      expect(screen.getByText("FALSE POSITIVE")).toBeInTheDocument();
    });
  });

  test("submits reviewed status cleanly when Confirm Anomaly is clicked", async () => {
    vi.mocked(api.fetchAnomalyDetail).mockResolvedValue(mockAnomaly);
    vi.mocked(api.fetchMetrics).mockResolvedValue([mockMetric]);
    vi.mocked(api.fetchAnomalyDrivers).mockResolvedValue(mockDrivers);
    vi.mocked(api.fetchTimeseries).mockResolvedValue(mockTimeseries);

    const updatedAnomaly: api.Anomaly = {
      ...mockAnomaly,
      status: "reviewed",
    };
    vi.mocked(api.submitAnomalyFeedback).mockResolvedValue(updatedAnomaly);

    render(<AnomalyDetailPage params={{ id: "99" }} />);

    await waitFor(() => {
      expect(screen.getByText("ANOMALY #99")).toBeInTheDocument();
    });

    const confirmBtn = screen.getByText("Confirm Anomaly");
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(api.submitAnomalyFeedback).toHaveBeenCalledWith(99, "reviewed");
      expect(screen.getByText("REVIEWED")).toBeInTheDocument();
    });
  });

  test("triggers segment-filtered timeseries fetch when bar chart is clicked", async () => {
    vi.mocked(api.fetchAnomalyDetail).mockResolvedValue(mockAnomaly);
    vi.mocked(api.fetchMetrics).mockResolvedValue([mockMetric]);
    vi.mocked(api.fetchAnomalyDrivers).mockResolvedValue(mockDrivers);
    vi.mocked(api.fetchTimeseries).mockResolvedValue(mockTimeseries);

    render(<AnomalyDetailPage params={{ id: "99" }} />);

    await waitFor(() => {
      expect(screen.getByText("ANOMALY #99")).toBeInTheDocument();
    });

    // Find Plotly mock chart for SegmentBarChart and click it
    const charts = screen.getAllByTestId("mock-plotly-chart");
    const barChartMock = charts[0];
    fireEvent.click(barChartMock);

    // Expect fetchTimeseries to be called with metric ID and segment filter "channel:organic"
    await waitFor(() => {
      expect(api.fetchTimeseries).toHaveBeenCalledWith(10, "channel:organic");
      expect(screen.getByText("Filtered: channel:organic")).toBeInTheDocument();
    });
  });
});
