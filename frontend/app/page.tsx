"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, TrendingUp, ArrowRight, BarChart2, Activity } from "lucide-react";
import { fetchMetrics, fetchTimeseries, fetchAnomalies, Metric, TimeseriesPoint, Anomaly } from "./api";

interface MetricOverviewData {
  metric: Metric;
  latestValue: number | null;
  points: TimeseriesPoint[];
  recentAnomaly: Anomaly | null;
  pctChange: number | null;
  absChange: number | null;
}

export default function Home() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metricOverviews, setMetricOverviews] = useState<MetricOverviewData[]>([]);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);
        
        // 1. Fetch metrics
        const metrics = await fetchMetrics();
        
        // 2. Fetch timeseries and anomalies for each metric
        const overviews: MetricOverviewData[] = [];
        
        for (const m of metrics) {
          try {
            const { points } = await fetchTimeseries(m.id);
            const anomalies = await fetchAnomalies(m.id);
            
            let latestValue: number | null = null;
            let recentAnomaly: Anomaly | null = null;
            let pctChange: number | null = null;
            let absChange: number | null = null;
            
            if (points.length > 0) {
              const sortedPoints = [...points].sort(
                (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
              );
              latestValue = sortedPoints[sortedPoints.length - 1].value_total;
              
              const maxDate = new Date(sortedPoints[sortedPoints.length - 1].date);
              const sevenDaysAgo = new Date(maxDate.getTime() - 7 * 24 * 60 * 60 * 1000);
              
              // Find new anomalies in the last 7 days of the dataset
              const newRecentAnoms = anomalies
                .filter((a) => {
                  const aDate = new Date(a.date);
                  return a.status === "new" && aDate >= sevenDaysAgo && aDate <= maxDate;
                })
                .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()); // latest first
              
              if (newRecentAnoms.length > 0) {
                recentAnomaly = newRecentAnoms[0];
                const pt = sortedPoints.find((p) => p.date === recentAnomaly!.date);
                if (pt && pt.trend !== null && pt.seasonal !== null) {
                  const expected = pt.trend + pt.seasonal;
                  const actual = pt.value_total;
                  
                  if (Math.abs(expected) >= 1e-3) {
                    pctChange = ((actual - expected) / expected) * 100;
                  } else {
                    absChange = actual - expected;
                  }
                }
              }
            }
            
            overviews.push({
              metric: m,
              latestValue,
              points,
              recentAnomaly,
              pctChange,
              absChange,
            });
          } catch (err) {
            console.error(`Error loading data for metric ${m.id}:`, err);
            // Append with empty data so the card still shows up
            overviews.push({
              metric: m,
              latestValue: null,
              points: [],
              recentAnomaly: null,
              pctChange: null,
              absChange: null,
            });
          }
        }
        
        setMetricOverviews(overviews);
      } catch (err: any) {
        console.error("Failed to load metrics:", err);
        setError(err.message || "Failed to load metrics");
      } finally {
        setLoading(false);
      }
    }
    
    loadData();
  }, []);

  if (loading) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-24 text-slate-100">
        <div className="flex flex-col items-center gap-4">
          <Activity className="h-12 w-12 animate-pulse text-cyan-400" />
          <p className="text-slate-400 font-medium animate-pulse">Loading overview dashboard...</p>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-24 text-slate-100">
        <div className="max-w-md rounded-xl border border-red-900 bg-red-950/20 p-6 text-center text-red-200">
          <AlertTriangle className="mx-auto h-12 w-12 text-red-500 mb-4" />
          <h2 className="text-xl font-bold mb-2">Error Loading Dashboard</h2>
          <p className="text-slate-400 text-sm mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="rounded-lg bg-red-600 px-4 py-2 text-white font-medium hover:bg-red-500 transition"
          >
            Retry
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8 md:p-16">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12 border-b border-slate-800 pb-8">
          <div>
            <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 via-teal-400 to-indigo-400 bg-clip-text text-transparent mb-2">
              Driftline Overview
            </h1>
            <p className="text-slate-400 font-medium">
              Anomaly detection, root-cause driver analysis, and short-horizon forecasting
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="flex h-3 w-3 rounded-full bg-emerald-500 animate-ping" />
            <span className="text-slate-400 text-sm font-semibold">Live System Operational</span>
          </div>
        </div>

        {/* Empty State */}
        {metricOverviews.length === 0 && (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 bg-slate-900/10 p-16 text-center">
            <BarChart2 className="h-16 w-16 text-slate-600 mb-4" />
            <h3 className="text-xl font-bold text-slate-300 mb-2">No Metrics Found</h3>
            <p className="text-slate-500 text-sm max-w-sm mb-6">
              Get started by uploading timeseries observations or registering a metric configuration.
            </p>
          </div>
        )}

        {/* Metrics Grid */}
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
          {metricOverviews.map(({ metric, latestValue, points, recentAnomaly, pctChange, absChange }) => {
            const hasAnomaly = recentAnomaly !== null;
            
            // 30 days sparkline SVG calculation
            const sparklinePoints = [...points]
              .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
              .slice(-30);
            
            let sparklineSvgPath = "";
            if (sparklinePoints.length > 1) {
              const vals = sparklinePoints.map((p) => p.value_total);
              const minVal = Math.min(...vals);
              const maxVal = Math.max(...vals);
              const valRange = maxVal - minVal || 1.0;
              
              const width = 120;
              const height = 40;
              
              const coordinates = sparklinePoints.map((p, idx) => {
                const x = (idx / (sparklinePoints.length - 1)) * width;
                const y = height - ((p.value_total - minVal) / valRange) * height;
                return `${x.toFixed(1)},${y.toFixed(1)}`;
              });
              
              sparklineSvgPath = `M ${coordinates.join(" L ")}`;
            }

            return (
              <div
                key={metric.id}
                className={`relative flex flex-col justify-between rounded-2xl border bg-slate-900/30 p-6 shadow-xl transition-all duration-300 hover:translate-y-[-4px] ${
                  hasAnomaly
                    ? "border-amber-900/50 hover:border-amber-700/50"
                    : "border-slate-800 hover:border-slate-700"
                }`}
              >
                {/* Metric Info */}
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-slate-500 text-xs font-bold uppercase tracking-wider">
                      Metric #{metric.id}
                    </span>
                    <span className="rounded-full bg-slate-800/80 px-2.5 py-0.5 text-xs font-semibold text-slate-300">
                      {metric.grain}
                    </span>
                  </div>

                  <h3 className="text-xl font-bold text-slate-100 mb-2 truncate">
                    {metric.name}
                  </h3>

                  {/* Value & Sparkline Row */}
                  <div className="flex items-end justify-between gap-4 mt-6 mb-6">
                    <div>
                      <p className="text-3xl font-extrabold tracking-tight text-white">
                        {latestValue !== null ? latestValue.toLocaleString() : "--"}
                      </p>
                      <p className="text-slate-500 text-xs font-semibold mt-1">
                        Latest Value ({metric.unit || "units"})
                      </p>
                    </div>

                    {/* Render sparkline SVG */}
                    {sparklineSvgPath && (
                      <div className="flex flex-col items-end">
                        <svg className="h-10 w-32 overflow-visible" viewBox="0 0 120 40">
                          <path
                            d={sparklineSvgPath}
                            fill="none"
                            stroke={hasAnomaly ? "#f59e0b" : "#22d3ee"}
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                        <span className="text-[10px] text-slate-500 font-semibold mt-1">
                          Last 30d
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Banner / Footer wrapper */}
                <div className="mt-4 pt-4 border-t border-slate-800/60">
                  {hasAnomaly ? (
                    <Link
                      href={`/anomalies/${recentAnomaly.id}`}
                      className="flex items-start gap-3 rounded-xl bg-amber-950/30 border border-amber-900/30 p-3 hover:bg-amber-950/40 transition duration-300 group"
                    >
                      <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-amber-200 font-bold group-hover:text-amber-100 transition">
                          {pctChange !== null ? (
                            `⚠ ${metric.name} is ${Math.abs(pctChange).toFixed(0)}% ${
                              pctChange < 0 ? "below" : "above"
                            } its normal range`
                          ) : absChange !== null ? (
                            `⚠ ${metric.name} is ${Math.abs(absChange).toFixed(2)} ${
                              metric.unit || ""
                            } ${absChange < 0 ? "below" : "above"} its normal range`
                          ) : (
                            `⚠ Active anomaly detected on ${recentAnomaly.date}`
                          )}
                        </p>
                        <span className="text-[10px] text-amber-500 font-bold tracking-wide mt-1 block">
                          TAP TO SEE WHY →
                        </span>
                      </div>
                    </Link>
                  ) : (
                    <Link
                      href={`/metrics/${metric.id}`}
                      className="flex items-center justify-between rounded-xl bg-slate-800/20 border border-slate-800 p-3 hover:bg-slate-800/40 transition duration-300 text-slate-300 hover:text-white"
                    >
                      <span className="text-xs font-bold">View Timeseries Dashboard</span>
                      <ArrowRight className="h-4 w-4 text-slate-400 group-hover:translate-x-1 transition" />
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
}
