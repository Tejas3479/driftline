"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { fetchMetrics, Metric } from "../app/api";

interface MetricContextType {
  selectedMetricId: number | null;
  setSelectedMetricId: (id: number) => void;
  metrics: Metric[];
  loading: boolean;
  refetchMetrics: () => Promise<void>;
}

const MetricContext = createContext<MetricContextType>({
  selectedMetricId: null,
  setSelectedMetricId: () => {},
  metrics: [],
  loading: true,
  refetchMetrics: async () => {},
});

export const MetricProvider = ({ children }: { children: React.ReactNode }) => {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [selectedMetricId, setSelectedMetricIdState] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMetrics = async () => {
    try {
      setLoading(true);
      const data = await fetchMetrics();
      const sorted = [...data].sort((a, b) => a.id - b.id);
      setMetrics(sorted);

      // Restore from localStorage or default to first metric
      const savedId = typeof window !== "undefined" ? localStorage.getItem("driftline_selected_metric_id") : null;
      if (savedId) {
        const parsed = parseInt(savedId, 10);
        if (sorted.some((m) => m.id === parsed)) {
          setSelectedMetricIdState(parsed);
          return;
        }
      }

      if (sorted.length > 0) {
        setSelectedMetricIdState(sorted[0].id);
      } else {
        setSelectedMetricIdState(null);
      }
    } catch (err) {
      console.error("Failed to load metrics into MetricContext:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMetrics();
  }, []);

  const setSelectedMetricId = (id: number) => {
    setSelectedMetricIdState(id);
    if (typeof window !== "undefined") {
      localStorage.setItem("driftline_selected_metric_id", id.toString());
    }
  };

  return (
    <MetricContext.Provider
      value={{
        selectedMetricId,
        setSelectedMetricId,
        metrics,
        loading,
        refetchMetrics: loadMetrics,
      }}
    >
      {children}
    </MetricContext.Provider>
  );
};

export const useMetricContext = () => useContext(MetricContext);
