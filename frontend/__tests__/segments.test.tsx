import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import SegmentComparisonPage from "../app/(dashboard)/metrics/[id]/segments/page";
import SegmentComparisonChart from "../components/SegmentComparisonChart";
import * as api from "../app/api";

// Mock vega-embed
vi.mock("vega-embed", () => {
  return {
    default: vi.fn(() =>
      Promise.resolve({
        view: {
          finalize: vi.fn(),
        },
      })
    ),
  };
});


// Mock the API client functions
vi.mock("../app/api", () => {
  return {
    fetchMetrics: vi.fn(),
    fetchSegmentComparison: vi.fn(),
  };
});

// Mock SWR hook
vi.mock("@/hooks/useApi", () => ({
  useApi: vi.fn()
}));

import { useApi } from "@/hooks/useApi";

// Mock next/dynamic to render SegmentComparisonChart synchronously in tests
vi.mock("next/dynamic", () => {
  return {
    default: (componentPromise: any) => {
      return function DynamicMock(props: any) {
        return (
          <div data-testid="mock-dynamic-segment-chart">
            <SegmentComparisonChart spec={props.spec} />
          </div>
        );
      };
    },
  };
});

describe("Segment Comparison Page & Vega-Embed Component Test Suite", () => {
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

  const mockVegaSpec = {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    description: "Segment comparison chart",
    title: "Segment Comparison for Revenue Metric (channel)",
    data: {
      values: [
        { date: "2026-07-01", value: 100, segment_value: "organic" },
        { date: "2026-07-01", value: 50, segment_value: "paid" },
      ],
    },
    mark: "line",
    encoding: {
      x: { field: "date", type: "temporal" },
      y: { field: "value", type: "quantitative", scale: { domain: [0, 120] } },
    },
    facet: { field: "segment_value", type: "nominal" },
  };

  beforeEach(() => {
    vi.resetAllMocks();

    vi.mocked(useApi).mockImplementation((url: string | null) => {
      if (!url) return { data: null, isLoading: false, error: null, mutate: vi.fn() };
      if (url.endsWith("/metrics")) {
        return { data: [mockMetric], isLoading: false, error: null, mutate: vi.fn() };
      }
      if (url.includes("/segments")) {
        return { data: mockVegaSpec, isLoading: false, error: null, mutate: vi.fn() };
      }
      return { data: null, isLoading: false, error: null, mutate: vi.fn() };
    });
  });

  test("SegmentComparisonChart component mounts cleanly and invokes vega-embed with spec", async () => {
    const vegaEmbedMock = (await import("vega-embed")).default;

    render(<SegmentComparisonChart spec={mockVegaSpec} />);

    const container = screen.getByTestId("vega-embed-container");
    expect(container).toBeInTheDocument();
    expect(vegaEmbedMock).toHaveBeenCalledWith(container, mockVegaSpec, {
      actions: false,
      renderer: "svg",
      theme: "dark",
    });
  });

  test("SegmentComparisonPage renders metric header, callout banner, and chart spec", async () => {
    // Handled by useApi mock in beforeEach

    render(<SegmentComparisonPage params={{ id: "1" }} />);

    await waitFor(() => {
      expect(screen.getByText("Revenue Metric Segment Comparison")).toBeInTheDocument();
    });

    expect(screen.getByText(/Shared Vertical Scale Invariant/i)).toBeInTheDocument();
    expect(screen.getByTestId("mock-dynamic-segment-chart")).toBeInTheDocument();
  });
});
