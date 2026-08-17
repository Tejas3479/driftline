"use client";

import React, { useState, useEffect } from "react";
import Plot from "react-plotly.js";
import { AnomalyDriversResponse, Metric, SegmentContribution } from "../app/api";

interface SegmentBarChartProps {
  driversData: AnomalyDriversResponse;
  metric: Metric;
  selectedSegment: string | null;
  onSelectSegment: (segmentKey: string | null) => void;
}

export default function SegmentBarChart({
  driversData,
  metric,
  selectedSegment,
  onSelectSegment,
}: SegmentBarChartProps) {
  const rankedSegments = driversData.ranked_segments || [];
  
  // Extract unique dimensions
  const availableDimensions = Array.from(
    new Set(rankedSegments.map((s) => s.dimension))
  ).filter(Boolean);

  // Set default active tab to primary_dimension if present in availableDimensions, else first dimension or "all"
  const defaultTab =
    driversData.primary_dimension && availableDimensions.includes(driversData.primary_dimension)
      ? driversData.primary_dimension
      : availableDimensions[0] || "all";

  const [activeTab, setActiveTab] = useState<string>(defaultTab);

  useEffect(() => {
    if (driversData.primary_dimension && availableDimensions.includes(driversData.primary_dimension)) {
      setActiveTab(driversData.primary_dimension);
    }
  }, [driversData.primary_dimension]);

  if (rankedSegments.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400 text-sm">
        No segment contribution drivers found for this anomaly.
      </div>
    );
  }

  // Filter segments according to active tab
  const isAll = activeTab === "all";
  const displayedSegments = isAll
    ? [...rankedSegments]
    : rankedSegments.filter((s) => s.dimension === activeTab);

  // Sort displayed segments chronologically/by magnitude
  // Plotly renders horizontal bar charts bottom-to-top, so we reverse the sorted array
  const sortedSegments = [...displayedSegments]
    .sort((a, b) => Math.abs(a.delta) - Math.abs(b.delta)); // smallest to largest so largest is at top of bar chart

  const barLabels = sortedSegments.map((s) =>
    isAll ? `${s.dimension}: ${s.segment_value}` : s.segment_value
  );

  const contribPcts = sortedSegments.map((s) => s.contribution_pct * 100);

  // Direction-aware bar colors
  const isUpIsGood = metric.direction_good === "up_is_good";
  const colors = sortedSegments.map((s) => {
    // If delta > 0 and up_is_good -> helped (green), hurt (red)
    // If delta < 0 and down_is_good -> helped (green), hurt (red)
    const isHelped = isUpIsGood ? s.delta > 0 : s.delta < 0;
    return isHelped ? "#10b981" : "#ef4444"; // emerald green vs rose red
  });

  const customText = sortedSegments.map((s) => {
    const isHelped = isUpIsGood ? s.delta > 0 : s.delta < 0;
    const impactWord = isHelped ? "Helped" : "Hurt";
    const deltaSign = s.delta > 0 ? "+" : "";
    return `${s.dimension}: ${s.segment_value}<br>${impactWord} performance<br>Delta: ${deltaSign}${s.delta.toFixed(2)} (${(s.contribution_pct * 100).toFixed(1)}%)`;
  });

  const handlePlotClick = (event: any) => {
    if (!event || !event.points || event.points.length === 0) return;
    const pointIndex = event.points[0].pointIndex;
    const seg = sortedSegments[pointIndex];
    if (!seg) return;

    const segKey = `${seg.dimension}:${seg.segment_value}`;
    if (selectedSegment === segKey) {
      onSelectSegment(null); // Toggle off if clicked again
    } else {
      onSelectSegment(segKey);
    }
  };

  return (
    <div className="w-full bg-slate-900/60 p-6 rounded-2xl border border-slate-800 shadow-xl">
      {/* Tab Selectors */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6 border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            Ranked Segment Contributions
          </h3>
          <p className="text-slate-400 text-xs mt-0.5">
            {"Click any bar to drill down into that segment's historical time series"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800">
          {availableDimensions.map((dim) => {
            const isPrimary = driversData.primary_dimension === dim;
            const isActive = activeTab === dim;
            return (
              <button
                key={dim}
                onClick={() => setActiveTab(dim)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition duration-200 ${
                  isActive
                    ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 shadow-xs"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                }`}
              >
                {dim.toUpperCase()}
                {isPrimary && (
                  <span className="ml-1.5 rounded-sm bg-cyan-500/30 px-1 py-0.2 text-[10px] text-cyan-300 font-bold">
                    Primary
                  </span>
                )}
              </button>
            );
          })}
          {availableDimensions.length > 1 && (
            <button
              onClick={() => setActiveTab("all")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition duration-200 ${
                activeTab === "all"
                  ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 shadow-xs"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              All Dimensions
            </button>
          )}
        </div>
      </div>

      {/* Plotly Horizontal Bar Chart */}
      <div className="w-full">
        <div aria-hidden="true">
          <Plot
            data={[
              {
                type: "bar",
                orientation: "h",
                x: contribPcts,
                y: barLabels,
                text: customText,
                hoverinfo: "text",
                marker: {
                  color: colors,
                  opacity: 0.9,
                  line: {
                    color: "#0f172a",
                    width: 1.5,
                  },
                },
              },
            ]}
            layout={{
              autosize: true,
              height: Math.max(260, sortedSegments.length * 45),
              margin: { l: 120, r: 40, t: 10, b: 40 },
              paper_bgcolor: "rgba(0,0,0,0)",
              plot_bgcolor: "rgba(0,0,0,0)",
              xaxis: {
                title: { text: "Contribution % of Total Delta", font: { color: "#94a3b8", size: 11 } },
                gridcolor: "#1e293b",
                zerolinecolor: "#334155",
                tickcolor: "#334155",
                tickfont: { color: "#94a3b8", size: 11 },
              },
              yaxis: {
                gridcolor: "transparent",
                tickcolor: "#334155",
                tickfont: { color: "#cbd5e1", size: 12 },
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
            onClick={handlePlotClick}
            className="w-full"
          />
        </div>

        {/* Screen Reader Only Data Table */}
        <table className="sr-only">
          <caption>Segment Contribution Drivers Data Table</caption>
          <thead>
            <tr>
              <th scope="col">Dimension</th>
              <th scope="col">Segment Value</th>
              <th scope="col">Contribution %</th>
              <th scope="col">Delta Value</th>
              <th scope="col">Impact</th>
            </tr>
          </thead>
          <tbody>
            {sortedSegments.map((s, idx) => {
              const isHelped = isUpIsGood ? s.delta > 0 : s.delta < 0;
              const impactWord = isHelped ? "Helped" : "Hurt";
              return (
                <tr key={idx}>
                  <th scope="row">{s.dimension}</th>
                  <td>{s.segment_value}</td>
                  <td>{(s.contribution_pct * 100).toFixed(1)}%</td>
                  <td>{s.delta > 0 ? `+${s.delta.toFixed(2)}` : s.delta.toFixed(2)}</td>
                  <td>{impactWord}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Legend / Color explanation */}
      <div className="mt-4 flex items-center justify-end gap-6 border-t border-slate-800/60 pt-3 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-sm bg-emerald-500 inline-block" />
          <span>Helped Metric Performance</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-sm bg-rose-500 inline-block" />
          <span>Hurt Metric Performance</span>
        </div>
      </div>
    </div>
  );
}
