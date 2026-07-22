"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { ArrowLeft, Calendar, AlertTriangle, Info, ShieldAlert } from "lucide-react";
import { fetchMetrics, fetchTimeseries, fetchAnomalies, Metric, TimeseriesPoint, Anomaly } from "../../api";

// Dynamically import Plotly chart component to prevent SSR window issues
const MetricChart = dynamic(() => import("@/components/MetricChart"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[500px] w-full items-center justify-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400">
      <div className="flex flex-col items-center gap-2">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
        <p className="text-sm font-semibold animate-pulse mt-2">Loading interactive chart canvas...</p>
      </div>
    </div>
  ),
});

type RangeFilter = "7d" | "30d" | "90d" | "1y" | "all";

export default function MetricDetail({ params }: { params: { id: string } }) {
  const metricId = parseInt(params.id);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metric, setMetric] = useState<Metric | null>(null);
  const [timeseriesData, setTimeseriesData] = useState<{
    points: TimeseriesPoint[];
    mad: number | null;
  } | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [range, setRange] = useState<RangeFilter>("all");

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);

        // Fetch all metrics to find current metric details
        const metrics = await fetchMetrics();
        const currentMetric = metrics.find((m) => m.id === metricId);
        
        if (!currentMetric) {
          throw new Error(`Metric #${metricId} not found in backend list.`);
        }
        setMetric(currentMetric);

        // Fetch timeseries and anomalies
        const ts = await fetchTimeseries(metricId);
        const anomList = await fetchAnomalies(metricId);

        setTimeseriesData(ts);
        setAnomalies(anomList);
      } catch (err: any) {
        console.error("Failed to load metric details:", err);
        setError(err.message || "Failed to load metric details");
      } finally {
        setLoading(false);
      }
    }

    if (metricId) {
      loadData();
    }
  }, [metricId]);

  if (loading) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-24 text-slate-100">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
          <p className="text-slate-400 font-medium">Loading timeseries analysis...</p>
        </div>
      </main>
    );
  }

  if (error || !metric || !timeseriesData) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-24 text-slate-100">
        <div className="max-w-md rounded-xl border border-red-900 bg-red-950/20 p-6 text-center text-red-200">
          <AlertTriangle className="mx-auto h-12 w-12 text-red-500 mb-4" />
          <h2 className="text-xl font-bold mb-2">Metric Not Found</h2>
          <p className="text-slate-400 text-sm mb-6">
            {error || `Unable to load timeseries for Metric #${metricId}`}
          </p>
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-lg bg-slate-800 px-4 py-2 text-white font-medium hover:bg-slate-700 transition"
          >
            <ArrowLeft className="h-4 w-4" /> Return to Overview
          </Link>
        </div>
      </main>
    );
  }

  // Filter timeseries and anomalies based on selected range (anchored to max date)
  const allPoints = timeseriesData.points;
  const sortedPoints = [...allPoints].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  let filteredPoints = sortedPoints;
  let filteredAnomalies = anomalies;

  if (sortedPoints.length > 0 && range !== "all") {
    const maxDate = new Date(sortedPoints[sortedPoints.length - 1].date);
    let cutoff = new Date(maxDate);

    if (range === "7d") {
      cutoff.setDate(maxDate.getDate() - 7);
    } else if (range === "30d") {
      cutoff.setDate(maxDate.getDate() - 30);
    } else if (range === "90d") {
      cutoff.setDate(maxDate.getDate() - 90);
    } else if (range === "1y") {
      cutoff.setFullYear(maxDate.getFullYear() - 1);
    }

    filteredPoints = sortedPoints.filter((p) => new Date(p.date) >= cutoff);
    filteredAnomalies = anomalies.filter((a) => new Date(a.date) >= cutoff);
  }

  // Compute key stats over filtered dataset
  const values = filteredPoints.map((p) => p.value_total);
  const maxVal = values.length > 0 ? Math.max(...values) : 0;
  const minVal = values.length > 0 ? Math.min(...values) : 0;
  const avgVal = values.length > 0 ? values.reduce((s, v) => s + v, 0) / values.length : 0;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8 md:p-16">
      <div className="mx-auto max-w-7xl">
        {/* Breadcrumb / Nav */}
        <div className="mb-8">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition text-sm font-semibold group"
          >
            <ArrowLeft className="h-4 w-4 group-hover:-translate-x-1 transition" />
            Back to Overview
          </Link>
        </div>

        {/* Metric Header Block */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 mb-12 border-b border-slate-800 pb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-slate-500 text-xs font-extrabold uppercase tracking-widest bg-slate-900 border border-slate-800 px-2 py-0.5 rounded">
                Metric #{metric.id}
              </span>
              <span className="rounded-full bg-slate-850 px-2.5 py-0.5 text-xs font-semibold text-cyan-400 border border-slate-800">
                {metric.grain} grain
              </span>
              {anomalies.filter(a => a.status === 'new').length > 0 && (
                <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-400 bg-amber-950/20 border border-amber-900/30 px-2 py-0.5 rounded">
                  <ShieldAlert className="h-3.5 w-3.5" /> Recent Anomalies
                </span>
              )}
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-white mb-2">
              {metric.name}
            </h1>
            <p className="text-slate-400 font-medium">
              Sensitivity: <span className="font-semibold text-slate-300 capitalize">{metric.sensitivity}</span> | Direction: <span className="font-semibold text-slate-300">{metric.direction_good.replace("_", " ")}</span>
            </p>
          </div>

          {/* Range Selector Controls */}
          <div className="flex items-center bg-slate-900 p-1.5 rounded-xl border border-slate-800 shadow-lg">
            {(["7d", "30d", "90d", "1y", "all"] as RangeFilter[]).map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all duration-200 ${
                  range === r
                    ? "bg-cyan-500 text-slate-950 shadow-md"
                    : "text-slate-400 hover:text-slate-100"
                }`}
              >
                {r.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Key Metrics Cards */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-8">
          <div className="rounded-xl border border-slate-800 bg-slate-900/10 p-5">
            <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-2">
              Highest Value
            </h4>
            <p className="text-2xl font-black text-white">
              {maxVal.toLocaleString()} <span className="text-slate-500 text-sm font-semibold">{metric.unit || ""}</span>
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/10 p-5">
            <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-2">
              Lowest Value
            </h4>
            <p className="text-2xl font-black text-white">
              {minVal.toLocaleString()} <span className="text-slate-500 text-sm font-semibold">{metric.unit || ""}</span>
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/10 p-5">
            <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-2">
              Average Value
            </h4>
            <p className="text-2xl font-black text-white">
              {avgVal.toLocaleString(undefined, { maximumFractionDigits: 1 })} <span className="text-slate-500 text-sm font-semibold">{metric.unit || ""}</span>
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/10 p-5">
            <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-2">
              Anomaly Count
            </h4>
            <p className="text-2xl font-black text-amber-500">
              {filteredAnomalies.length}{" "}
              <span className="text-slate-500 text-sm font-semibold">
                ({filteredAnomalies.filter((a) => a.status === "new").length} new)
              </span>
            </p>
          </div>
        </div>

        {/* Plotly Chart Visualization Container */}
        <div className="mb-12">
          <MetricChart
            points={filteredPoints}
            anomalies={filteredAnomalies}
            mad={timeseriesData.mad}
            metricName={metric.name}
            unit={metric.unit}
          />
        </div>

        {/* Anomalies Table / List in this range */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/20 p-6 shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-extrabold tracking-tight text-slate-100 flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-amber-500" />
              Flagged Anomalies in Range
            </h2>
            <span className="text-slate-400 text-xs font-semibold">
              Showing {filteredAnomalies.length} entries
            </span>
          </div>

          {filteredAnomalies.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-center border border-dashed border-slate-800 rounded-xl bg-slate-900/10">
              <Info className="h-10 w-10 text-slate-600 mb-2" />
              <p className="text-slate-400 font-medium">No anomalies flagged in selected range.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-bold">
                    <th className="pb-3 pr-4">Date</th>
                    <th className="pb-3 px-4">Type</th>
                    <th className="pb-3 px-4">Z-score</th>
                    <th className="pb-3 px-4">Status</th>
                    <th className="pb-3 px-4">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {[...filteredAnomalies]
                    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
                    .map((anom) => {
                      let typeLabelColor = "bg-red-500/10 text-red-400 border-red-500/20";
                      if (anom.type === "level_shift") {
                        typeLabelColor = "bg-amber-500/10 text-amber-400 border-amber-500/20";
                      } else if (anom.type === "volatility") {
                        typeLabelColor = "bg-pink-500/10 text-pink-400 border-pink-500/20";
                      } else if (anom.type === "dip") {
                        typeLabelColor = "bg-blue-500/10 text-blue-400 border-blue-500/20";
                      }

                      return (
                        <tr key={anom.id} className="text-slate-300 hover:bg-slate-900/40 transition">
                          <td className="py-4 pr-4 font-semibold">{anom.date}</td>
                          <td className="py-4 px-4">
                            <span className={`px-2 py-0.5 rounded text-xs font-bold border uppercase ${typeLabelColor}`}>
                              {anom.type.replace("_", " ")}
                            </span>
                          </td>
                          <td className="py-4 px-4 font-mono font-bold">
                            {anom.z_score > 0 ? "+" : ""}
                            {anom.z_score.toFixed(2)}
                          </td>
                          <td className="py-4 px-4 capitalize">
                            <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold ${
                              anom.status === 'new' 
                                ? 'bg-rose-500/10 text-rose-400' 
                                : 'bg-slate-800 text-slate-400'
                            }`}>
                              {anom.status === 'new' && <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />}
                              {anom.status}
                            </span>
                          </td>
                          <td className="py-4 px-4 text-xs font-medium text-slate-400 max-w-xs truncate">
                            {anom.explanation_text || "Spike or dip detected."}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
