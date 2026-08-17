"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { ArrowLeft, AlertTriangle, Activity, CheckCircle, XCircle, Info } from "lucide-react";
import {
  fetchMetrics,
  fetchTimeseries,
  fetchForecast,
  fetchAccuracy,
  generateForecast,
  generateAccuracy,
  Metric,
  TimeseriesPoint,
  ForecastResult,
  AccuracyResponse,
  TimeseriesResponse,
} from "@/app/api";
import { useApi } from "@/hooks/useApi";
import { useSWRConfig } from "swr";
import LowConfidenceBanner from "@/components/LowConfidenceBanner";
import ForecastStatsPanel from "@/components/ForecastStatsPanel";
import ScrollReveal from "@/components/ScrollReveal";

// Dynamically import Plotly chart components to prevent SSR window issues
const MetricChart = dynamic(() => import("@/components/MetricChart"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[450px] w-full items-center justify-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400">
      <div className="flex flex-col items-center gap-2">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-purple-500 border-t-transparent" />
        <p className="text-sm font-semibold animate-pulse mt-2">Loading forecast chart...</p>
      </div>
    </div>
  ),
});

const ForecastVsActualChart = dynamic(() => import("@/components/ForecastVsActualChart"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[320px] w-full items-center justify-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400">
      <div className="flex flex-col items-center gap-2">
        <div className="h-6 w-6 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
        <p className="text-xs font-semibold animate-pulse mt-2">Loading track record chart...</p>
      </div>
    </div>
  ),
});

type HorizonOption = 7 | 14 | 30;
type BackendOption = "lightgbm" | "xgboost";

export default function ForecastPage({ params }: { params: { id: string } }) {
  const metricId = parseInt(params.id);

  const { data: metrics, error: metricsError, isLoading: metricsLoading } = useApi<Metric[]>("/api/v1/metrics");
  const { data: tsData, error: tsError, isLoading: tsLoading } = useApi<TimeseriesResponse>(
    !isNaN(metricId) ? `/api/v1/metrics/${metricId}/timeseries` : null
  );
  
  // Single unified state for controls
  const [horizon, setHorizon] = useState<HorizonOption>(30);
  const [backend, setBackend] = useState<BackendOption>("lightgbm");
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const { mutate } = useSWRConfig();
  
  const { data: forecastResult, error: fcError, isLoading: fcLoading } = useApi<ForecastResult>(
    !isNaN(metricId) ? `/api/v1/metrics/${metricId}/forecast?horizon=${horizon}&backend=${backend}` : null
  );
  
  const { data: accuracyResponse, error: accError, isLoading: accLoading } = useApi<AccuracyResponse>(
    !isNaN(metricId) ? `/api/v1/metrics/${metricId}/accuracy?horizon=${horizon}&backend=${backend}` : null
  );

  const handleGenerate = async () => {
    if (isNaN(metricId)) return;
    setGenerating(true);
    try {
      await Promise.all([
        generateForecast(metricId, horizon, backend),
        generateAccuracy(metricId, horizon, backend),
      ]);
      await Promise.all([
        mutate(`/api/v1/metrics/${metricId}/forecast?horizon=${horizon}&backend=${backend}`),
        mutate(`/api/v1/metrics/${metricId}/accuracy?horizon=${horizon}&backend=${backend}`),
      ]);
    } catch (e: unknown) {
      const err = e instanceof Error ? e : new Error(String(e));
      setGenerateError(err.message || "Failed to generate forecast & backtest.");
    } finally {
      setGenerating(false);
    }
  };

  const metric = metrics?.find((m) => m.id === metricId) || null;
  const timeseriesData = tsData || null;

  const fetchingControls = fcLoading || accLoading;
  const loading = (metricsLoading || tsLoading) && (!metric || !timeseriesData);
  const error = metricsError?.message || tsError?.message || fcError?.message || accError?.message || generateError || null;

  const sortedAccuracyPoints = useMemo(() => {
    if (!accuracyResponse?.points) return [];
    return [...accuracyResponse.points].sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
    );
  }, [accuracyResponse?.points]);

  if (loading) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-24 text-slate-100">
        <div className="flex flex-col items-center gap-4">
          <Activity className="h-10 w-10 animate-spin text-purple-400" />
          <p className="text-slate-400 font-medium animate-pulse">
            Generating quantile forecasts & backtest evaluations...
          </p>
        </div>
      </main>
    );
  }

  if (error || !metric || !timeseriesData) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-24 text-slate-100">
        <div className="max-w-md rounded-xl border border-red-900 bg-red-950/20 p-6 text-center text-red-200">
          <AlertTriangle className="mx-auto h-12 w-12 text-red-500 mb-4" />
          <h2 className="text-xl font-bold mb-2">Error Loading Forecast</h2>
          <p className="text-slate-400 text-sm mb-6">{error || "Metric data unavailable."}</p>
          <Link
            href={`/metrics/${metricId}`}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-800 px-4 py-2 text-white font-medium hover:bg-slate-700 transition"
          >
            <ArrowLeft className="h-4 w-4" /> Return to Metric Detail
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8 md:p-16">
      <div className="mx-auto max-w-7xl">
        {/* Navigation Breadcrumb */}
        <div className="mb-8">
          <Link
            href={`/metrics/${metricId}`}
            className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition text-sm font-semibold group"
          >
            <ArrowLeft className="h-4 w-4 group-hover:-translate-x-1 transition" />
            Back to Metric #{metricId} Detail
          </Link>
        </div>

        {/* Page Header */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 mb-10 border-b border-slate-800 pb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-slate-500 text-xs font-extrabold uppercase tracking-widest bg-slate-900 border border-slate-800 px-2 py-0.5 rounded-sm">
                Metric #{metric.id}
              </span>
              <span className="rounded-full bg-purple-950/40 px-2.5 py-0.5 text-xs font-semibold text-purple-300 border border-purple-800/40">
                Quantile Forecast & Track Record
              </span>
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-white mb-2">
              {metric.name} Forecast
            </h1>
            <p className="text-slate-400 font-medium text-sm">
              Model accuracy track record and multi-quantile ({horizon}-day) projections
            </p>
          </div>

          {/* Controls: Horizon & Model Backend Selectors */}
          <div className="flex flex-wrap items-center gap-4 bg-slate-900 p-2.5 rounded-xl border border-slate-800 shadow-lg">
            {/* Horizon Picker */}
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
              <span className="text-slate-500 text-[11px] font-bold uppercase px-2">
                Horizon:
              </span>
              {([7, 14, 30] as HorizonOption[]).map((h) => (
                <button
                  key={h}
                  onClick={() => setHorizon(h)}
                  className={`px-3 py-1 rounded text-xs font-bold transition-all ${
                    horizon === h
                      ? "bg-purple-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {h}D
                </button>
              ))}
            </div>

            {/* Backend Toggle */}
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
              <span className="text-slate-500 text-[11px] font-bold uppercase px-2">
                Model:
              </span>
              {(["lightgbm", "xgboost"] as BackendOption[]).map((b) => (
                <button
                  key={b}
                  onClick={() => setBackend(b)}
                  className={`px-3 py-1 rounded text-xs font-bold uppercase transition-all ${
                    backend === b
                      ? "bg-cyan-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {b}
                </button>
              ))}
            </div>

            {fetchingControls && (
              <div className="flex items-center gap-2 text-purple-400 text-xs font-semibold px-2 animate-pulse">
                <Activity className="h-3.5 w-3.5 animate-spin" /> Updating...
              </div>
            )}

            <button
              onClick={handleGenerate}
              disabled={generating || fcLoading || accLoading}
              className="inline-flex items-center gap-2 rounded-lg bg-linear-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 text-white text-xs font-bold px-4 py-2 transition-all shadow-lg disabled:opacity-50"
            >
              {generating ? <Activity className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle className="h-3.5 w-3.5" />}
              {generating ? "Generating..." : "Generate Forecast & Backtest"}
            </button>
          </div>
        </div>

        {/* Cold-Start Low Confidence Banner */}
        {forecastResult?.low_confidence && <LowConfidenceBanner />}

        {/* Model Accuracy Track Record Stats Panel */}
        <ScrollReveal direction="up">
          <ForecastStatsPanel
            accuracy={accuracyResponse || null}
            modelVersion={forecastResult?.model_version || null}
            backend={backend}
          />
        </ScrollReveal>

        {/* Main Extended Timeseries & Forecast Chart */}
        <ScrollReveal direction="up" delay={0.2}>
          <div className="mb-10 glass-card-lg p-4 rounded-xl bg-slate-900/40 backdrop-blur-sm border border-slate-800">
            <div className="flex items-center justify-between mb-3 px-1">
              <h2 className="text-lg font-bold text-slate-100">
                Historical Timeseries & {horizon}-Day Quantile Forecast
              </h2>
              <span className="text-xs text-slate-400 font-semibold">
                p10 (10%), p50 (median), p90 (90%) bounds
              </span>
            </div>
            <MetricChart
              points={timeseriesData.points}
              anomalies={[]}
              mad={timeseriesData.mad}
              metricName={metric.name}
              unit={metric.unit}
              forecastPoints={forecastResult?.forecasts}
            />
          </div>
        </ScrollReveal>

        {/* Separate Forecast vs Actual Track Record Chart */}
        <ScrollReveal direction="up" delay={0.15}>
          <div className="mb-12 glass-card-lg p-4 rounded-xl bg-slate-900/40 backdrop-blur-sm border border-slate-800">
            <ForecastVsActualChart
              points={accuracyResponse?.points || []}
              metricName={metric.name}
              unit={metric.unit}
            />
          </div>
        </ScrollReveal>

        {/* Evaluation Log Table */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 backdrop-blur-sm p-6 shadow-2xl hover:shadow-glow-cyan-sm transition-all duration-300">
          <div className="flex items-center justify-between mb-6 border-b border-slate-800 pb-4">
            <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              <Info className="h-5 w-5 text-cyan-400" />
              Walk-Forward Backtest Evaluation Log
            </h3>
            <span className="text-slate-400 text-xs font-semibold">
              {accuracyResponse?.points.length || 0} evaluation points
            </span>
          </div>

          {!accuracyResponse?.points || accuracyResponse.points.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-center border border-dashed border-slate-800 rounded-xl">
              <p className="text-slate-400 text-sm font-medium">
                No backtest evaluation logs found for this horizon and model backend.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-bold">
                    <th className="pb-3 pr-4">Evaluation Date</th>
                    <th className="pb-3 px-4">Predicted (p50)</th>
                    <th className="pb-3 px-4">Actual Value</th>
                    <th className="pb-3 px-4">Abs Error</th>
                    <th className="pb-3 px-4">Abs Error %</th>
                    <th className="pb-3 px-4">In p10–p90 Band</th>
                    <th className="pb-3 px-4">Model Type</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {sortedAccuracyPoints.map((pt, idx) => {
                      const pctErrText = pt.abs_pct_error !== null
                        ? `${(pt.abs_pct_error * 100).toFixed(2)}%`
                        : "--";

                      return (
                        <tr key={idx} className="text-slate-300 hover:bg-slate-900/40 hover:shadow-glow-indigo-sm transition">
                          <td className="py-3 pr-4 font-semibold font-mono">{pt.date}</td>
                          <td className="py-3 px-4 font-mono">
                            {pt.predicted_p50.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                          </td>
                          <td className="py-3 px-4 font-mono font-bold text-white">
                            {pt.actual.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                          </td>
                          <td className="py-3 px-4 font-mono text-slate-400">
                            {pt.abs_error.toFixed(2)}
                          </td>
                          <td className="py-3 px-4 font-mono font-bold text-cyan-400">
                            {pctErrText}
                          </td>
                          <td className="py-3 px-4">
                            {pt.in_bounds === true ? (
                              <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-400">
                                <CheckCircle className="h-3.5 w-3.5" /> In Bounds
                              </span>
                            ) : pt.in_bounds === false ? (
                              <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-400">
                                <XCircle className="h-3.5 w-3.5" /> Out of Bounds
                              </span>
                            ) : (
                              <span className="text-slate-500 text-xs">--</span>
                            )}
                          </td>
                          <td className="py-3 px-4">
                            {pt.used_ml_model ? (
                              <span className="px-2 py-0.5 rounded-sm text-[11px] font-bold bg-purple-950/40 text-purple-300 border border-purple-800/40">
                                ML Model ({backend})
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-sm text-[11px] font-bold bg-slate-800 text-slate-400">
                                Seasonal Naive Fallback
                              </span>
                            )}
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
