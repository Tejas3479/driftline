import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import GlobalAnomalyLogPage from "../app/(dashboard)/anomalies/page";
import * as api from "../app/api";

// Mock API module
vi.mock("../app/api", () => {
  return {
    fetchGlobalAnomalies: vi.fn(),
  };
});

// Mock SWR hook
vi.mock("@/hooks/useApi", () => ({
  useApi: vi.fn()
}));

import { useApi } from "@/hooks/useApi";

describe("Global Anomaly Log Page Component Test Suite", () => {
  const mockAnomalies: api.GlobalAnomaly[] = [
    {
      id: 1,
      metric_id: 1,
      metric_name: "MRR",
      date: "2026-07-20",
      severity_score: 95.0,
      anomaly_type: "drop",
      status: "new",
      explanation_excerpt: "Organic channel drop drove -65% shift",
    },
    {
      id: 2,
      metric_id: 1,
      metric_name: "MRR",
      date: "2026-07-15",
      severity_score: 50.0,
      anomaly_type: "spike",
      status: "reviewed",
      explanation_excerpt: "Paid marketing campaign surge",
    },
    {
      id: 3,
      metric_id: 2,
      metric_name: "Active Users",
      date: "2026-07-10",
      severity_score: 80.0,
      anomaly_type: "level_shift",
      status: "false_positive",
      explanation_excerpt: "Scheduled system migration event",
    },
    {
      id: 4,
      metric_id: 2,
      metric_name: "Active Users",
      date: "2026-07-05",
      severity_score: 30.0,
      anomaly_type: "volatility",
      status: "resolved",
      explanation_excerpt: "API gateway timeout spike resolved",
    },
  ];

  beforeEach(() => {
    vi.resetAllMocks();

    vi.mocked(useApi).mockImplementation((url: string | null) => {
      if (!url) return { data: [], isLoading: false, error: null, mutate: vi.fn() };
      if (url.includes("status=new")) {
        return { data: mockAnomalies.filter((a) => a.status === "new"), isLoading: false, error: null, mutate: vi.fn() };
      }
      return { data: mockAnomalies, isLoading: false, error: null, mutate: vi.fn() };
    });
  });

  test("status filter tab 'New' excludes reviewed, resolved, and false_positive anomalies", async () => {
    // handled by useApi mock above

    render(<GlobalAnomalyLogPage />);

    // Initially loads all
    await waitFor(() => {
      expect(screen.getByText("Organic channel drop drove -65% shift")).toBeInTheDocument();
    });


    // Click 'New' tab
    const newTab = screen.getByRole("button", { name: "New" });
    fireEvent.click(newTab);

    await waitFor(() => {
      expect(useApi).toHaveBeenCalledWith(expect.stringContaining("status=new"));
    });

    // Should contain 'Organic channel drop drove -65% shift' and NOT reviewed or resolved excerpts
    expect(screen.getByText("Organic channel drop drove -65% shift")).toBeInTheDocument();
    expect(screen.queryByText("Paid marketing campaign surge")).not.toBeInTheDocument();
    expect(screen.queryByText("Scheduled system migration event")).not.toBeInTheDocument();
    expect(screen.queryByText("API gateway timeout spike resolved")).not.toBeInTheDocument();
  });

  test("sorting by severity orders rows in descending order (High to Low)", async () => {
    // handled by useApi mock above

    render(<GlobalAnomalyLogPage />);

    await waitFor(() => {
      expect(screen.getByText("Organic channel drop drove -65% shift")).toBeInTheDocument();
    });

    // Select Severity (High to Low)
    const sortSelect = screen.getByRole("combobox");
    fireEvent.change(sortSelect, { target: { value: "severity_desc" } });

    // Verify first row in table body corresponds to severity 95 (MRR)
    const rows = screen.getAllByRole("row");
    // Row 0 is header, Row 1 should be MRR (severity 95)
    expect(rows[1]).toHaveTextContent("MRR");
    expect(rows[1]).toHaveTextContent("High (95)");
  });

  test("text search input filters rows matching query", async () => {
    // handled by useApi mock above

    render(<GlobalAnomalyLogPage />);

    await waitFor(() => {
      expect(screen.getByText("Organic channel drop drove -65% shift")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search by metric or explanation/i);
    fireEvent.change(searchInput, { target: { value: "gateway" } });

    expect(screen.getByText("API gateway timeout spike resolved")).toBeInTheDocument();
    expect(screen.queryByText("Organic channel drop drove -65% shift")).not.toBeInTheDocument();
  });
});
