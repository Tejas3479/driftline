"use client";

import React from "react";
import Plot from "react-plotly.js";
import { AccuracyPoint } from "../app/api";

interface ForecastVsActualChartProps {
  points: AccuracyPoint[];
  metricName: string;
  unit: string | null;
}

export default function ForecastVsActualChart({
  points,
  metricName,
  unit,
}: ForecastVsActualChartProps) {
  if (!points || points.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400 text-sm">
        No historical backtest evaluation data available.
      </div>
    );
  }

  // Sort points chronologically
  const sortedPoints = [...points].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  const dates = sortedPoints.map((p) => p.date);
  const actuals = sortedPoints.map((p) => p.actual);

  // ML points vs Naive points
  const mlPoints = sortedPoints.filter((p) => p.used_ml_model);
  const naivePoints = sortedPoints.filter((p) => !p.used_ml_model);

  const data: any[] = [];

  // 1. Shaded historical prediction band (p10–p90) if available
  const hasP10P90 = sortedPoints.some((p) => p.predicted_p10 !== null && p.predicted_p90 !== null);
  if (hasP10P90) {
    const p10Vals = sortedPoints.map((p) => p.predicted_p10);
    const p90Vals = sortedPoints.map((p) => p.predicted_p90);

    // p10 lower bound (hidden line)
    data.push({
      x: dates,
      y: p10Vals,
      type: "scatter",
      mode: "lines",
      line: { width: 0 },
      showlegend: false,
      hoverinfo: "skip",
    });

    // p90 upper bound with fill to p10
    data.push({
      x: dates,
      y: p90Vals,
      type: "scatter",
      mode: "lines",
      fill: "tonexty",
      fillcolor: "rgba(168, 85, 247, 0.12)",
      line: { width: 0 },
      name: "Historical p10–p90 Band",
      showlegend: true,
      hoverinfo: "skip",
    });
  }

  // 2. Actual values trace (solid cyan line)
  data.push({
    x: dates,
    y: actuals,
    type: "scatter",
    mode: "lines+markers",
    name: `Actual ${metricName}`,
    line: {
      color: "#06b6d4", // cyan
      width: 2,
    },
    marker: {
      size: 5,
      color: "#06b6d4",
    },
  });

  // 3. Historical ML predicted p50 trace (dashed purple line)
  if (mlPoints.length > 0) {
    data.push({
      x: mlPoints.map((p) => p.date),
      y: mlPoints.map((p) => p.predicted_p50),
      type: "scatter",
      mode: "lines+markers",
      name: "Historical ML Predicted (p50)",
      line: {
        color: "#a855f7", // purple
        width: 2,
        dash: "dash",
      },
      marker: {
        size: 6,
        color: "#a855f7",
      },
    });
  }

  // 4. Seasonal Naive Fallback points (distinct gray diamond markers)
  if (naivePoints.length > 0) {
    data.push({
      x: naivePoints.map((p) => p.date),
      y: naivePoints.map((p) => p.predicted_p50),
      type: "scatter",
      mode: "markers",
      name: "Seasonal Naive Fallback",
      marker: {
        symbol: "diamond",
        size: 8,
        color: "#94a3b8", // slate-400 gray
        line: {
          color: "#475569",
          width: 1.5,
        },
      },
    });
  }

  return (
    <div className="w-full glass-card-lg rounded-xl p-4 shadow-xl">
      <div className="mb-3 flex items-center justify-between border-b border-slate-800 pb-2 px-2">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
          Forecast vs. Actual Track Record (Walk-Forward Backtest)
        </h3>
        <span className="text-xs text-slate-500 font-medium">
          {sortedPoints.length} evaluated fold dates
        </span>
      </div>
      <Plot
        data={data}
        layout={{
          autosize: true,
          height: 340,
          margin: { l: 50, r: 20, t: 20, b: 50 },
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          xaxis: {
            gridcolor: "#1e293b",
            zerolinecolor: "#334155",
            tickcolor: "#334155",
            tickfont: { color: "#94a3b8", size: 11 },
            type: "date",
          },
          yaxis: {
            gridcolor: "#1e293b",
            zerolinecolor: "#334155",
            tickcolor: "#334155",
            tickfont: { color: "#94a3b8", size: 11 },
            title: unit ? { text: unit, font: { color: "#94a3b8", size: 11 } } : undefined,
          },
          legend: {
            font: { color: "#cbd5e1", size: 10 },
            orientation: "h",
            yanchor: "bottom",
            y: 1.02,
            xanchor: "right",
            x: 1,
          },
          hoverlabel: {
            bgcolor: "#0f172a",
            bordercolor: "#334155",
            font: { color: "#f8fafc", size: 12 },
          },
        }}
        config={{
          responsive: true,
          displayModeBar: false,
        }}
        className="w-full"
      />
    </div>
  );
}
