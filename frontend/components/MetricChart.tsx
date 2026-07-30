"use client";

import React from "react";
import Plot from "react-plotly.js";
import { TimeseriesPoint, Anomaly, ForecastPoint } from "../app/api";

interface MetricChartProps {
  points: TimeseriesPoint[];
  anomalies: Anomaly[];
  mad: number | null;
  metricName: string;
  unit: string | null;
  forecastPoints?: ForecastPoint[];
}

const TYPE_COLORS = {
  level_shift: "#F59E0B", // Amber
  volatility: "#EC4899",  // Pink/Fuchsia
  spike: "#EF4444",       // Red/Rose
  dip: "#3B82F6",         // Blue
};

const TYPE_SYMBOLS = {
  level_shift: "diamond",
  volatility: "cross",
  spike: "triangle-up",
  dip: "triangle-down",
};

export default function MetricChart({
  points,
  anomalies,
  mad,
  metricName,
  unit,
  forecastPoints,
}: MetricChartProps) {

  if (!points || points.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400">
        No timeseries data available.
      </div>
    );
  }

  // Sort points chronologically
  const sortedPoints = [...points].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  const dates = sortedPoints.map((p) => p.date);
  const values = sortedPoints.map((p) => p.value_total);
  const trends = sortedPoints.map((p) => p.trend);

  const data: any[] = [];

  // 1. Shaded baseline band: trend ± MAD (only if mad is not null/undefined and we have trend values)
  if (mad !== null && mad !== undefined && mad > 0) {
    const lowerBand = sortedPoints.map((p) =>
      p.trend !== null ? p.trend - mad : null
    );
    const upperBand = sortedPoints.map((p) =>
      p.trend !== null ? p.trend + mad : null
    );

    // Lower bound trace (hidden line)
    data.push({
      x: dates,
      y: lowerBand,
      type: "scatter",
      mode: "lines",
      line: { width: 0 },
      showlegend: false,
      hoverinfo: "skip",
    });

    // Upper bound trace with fill
    data.push({
      x: dates,
      y: upperBand,
      type: "scatter",
      mode: "lines",
      fill: "tonexty",
      fillcolor: "rgba(59, 130, 246, 0.08)", // subtle blue shading
      line: { width: 0 },
      name: "Normal Range (Trend ± MAD)",
      showlegend: true,
      hoverinfo: "skip",
    });
  }

  // 2. Trend line
  if (trends.some((t) => t !== null)) {
    data.push({
      x: dates,
      y: trends,
      type: "scatter",
      mode: "lines",
      name: "Trend",
      line: {
        color: "#64748b",
        width: 1.5,
        dash: "dash",
      },
      connectgaps: true,
    });
  }

  // 3. Actual values line
  data.push({
    x: dates,
    y: values,
    type: "scatter",
    mode: "lines",
    name: `Actual ${metricName}`,
    line: {
      color: "#06b6d4", // vibrant cyan
      width: 2.5,
    },
  });

  // 4. Interactive scatter markers for anomalies
  anomalies.forEach((anom) => {
    // Find value on this date
    const pt = sortedPoints.find((p) => p.date === anom.date);
    if (!pt) return;

    const color = TYPE_COLORS[anom.type] || "#ef4444";
    const symbol = TYPE_SYMBOLS[anom.type] || "circle";
    const cleanExplanation = anom.explanation_text || "No explanation provided.";

    data.push({
      x: [anom.date],
      y: [pt.value_total],
      type: "scatter",
      mode: "markers",
      name: `Anomaly: ${anom.type.replace("_", " ")}`,
      showlegend: false,
      marker: {
        symbol: symbol,
        size: 12,
        color: color,
        line: {
          color: "#0f172a",
          width: 2,
        },
      },
      text: [
        `<b>Anomaly Type:</b> ${anom.type.toUpperCase()}<br>` +
          `<b>Date:</b> ${anom.date}<br>` +
          `<b>Actual Value:</b> ${pt.value_total.toLocaleString()} ${unit || ""}<br>` +
          `<b>Z-score:</b> ${anom.z_score.toFixed(2)}<br>` +
          `<b>Explanation:</b> ${cleanExplanation}`,
      ],
      hoverinfo: "text",
    });
  });

  // 5. Forecast region: p10/p90 band + p50 dashed line
  if (forecastPoints && forecastPoints.length > 0) {
    const sortedForecasts = [...forecastPoints].sort(
      (a, b) => new Date(a.forecast_date).getTime() - new Date(b.forecast_date).getTime()
    );
    const forecastDates = sortedForecasts.map((f) => f.forecast_date);
    const p10Values = sortedForecasts.map((f) => f.p10);
    const p50Values = sortedForecasts.map((f) => f.p50);
    const p90Values = sortedForecasts.map((f) => f.p90);

    // p10 lower bound (hidden line)
    data.push({
      x: forecastDates,
      y: p10Values,
      type: "scatter",
      mode: "lines",
      line: { width: 0 },
      showlegend: false,
      hoverinfo: "skip",
    });

    // p90 upper bound with fill to p10
    data.push({
      x: forecastDates,
      y: p90Values,
      type: "scatter",
      mode: "lines",
      fill: "tonexty",
      fillcolor: "rgba(168, 85, 247, 0.15)", // subtle purple shading
      line: { width: 0 },
      name: "80% Prediction Band (p10–p90)",
      showlegend: true,
      hoverinfo: "skip",
    });

    // Connect p50 line from last actual point if available
    const p50Dates = sortedPoints.length > 0
      ? [sortedPoints[sortedPoints.length - 1].date, ...forecastDates]
      : forecastDates;
    const p50Y = sortedPoints.length > 0
      ? [sortedPoints[sortedPoints.length - 1].value_total, ...p50Values]
      : p50Values;

    // Dashed p50 median forecast line
    data.push({
      x: p50Dates,
      y: p50Y,
      type: "scatter",
      mode: "lines",
      name: "Forecast (p50)",
      line: {
        color: "#a855f7", // vibrant purple
        width: 2.5,
        dash: "dash",
      },
    });
  }


  // 5. Layout shapes: Vertical dashed lines colored by anomaly type
  const shapes = anomalies.map((anom) => {
    const color = TYPE_COLORS[anom.type] || "#ef4444";
    const zAbs = Math.abs(anom.z_score);
    // opacity scaled by z-score magnitude: max(0.3, min(1.0, zAbs / 6.0))
    const opacity = Math.max(0.3, Math.min(1.0, zAbs / 6.0));

    // Convert hex color to rgba for opacity control
    // Helper to convert hex to rgba
    const hexToRgba = (hex: string, alpha: number) => {
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    };

    return {
      type: "line" as const,
      xref: "x" as const,
      yref: "paper" as const,
      x0: anom.date,
      y0: 0,
      x1: anom.date,
      y1: 1,
      line: {
        color: hexToRgba(color, opacity),
        width: 1.5,
        dash: "dash" as const,
      },
    };
  });

  return (
    <div className="w-full glass-card-lg rounded-xl p-4 shadow-2xl">
      <Plot
        data={data}
        layout={{
          autosize: true,
          height: 500,
          margin: { l: 60, r: 20, t: 30, b: 60 },
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          xaxis: {
            gridcolor: "#1e293b",
            zerolinecolor: "#334155",
            tickcolor: "#334155",
            tickfont: { color: "#94a3b8" },
            type: "date",
          },
          yaxis: {
            gridcolor: "#1e293b",
            zerolinecolor: "#334155",
            tickcolor: "#334155",
            tickfont: { color: "#94a3b8" },
            title: unit ? { text: unit, font: { color: "#94a3b8", size: 12 } } : undefined,
          },
          legend: {
            font: { color: "#cbd5e1", size: 11 },
            orientation: "h",
            yanchor: "bottom",
            y: 1.02,
            xanchor: "right",
            x: 1,
          },
          shapes: shapes,
          hoverlabel: {
            bgcolor: "#0f172a",
            bordercolor: "#334155",
            font: { color: "#f8fafc", size: 13 },
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
