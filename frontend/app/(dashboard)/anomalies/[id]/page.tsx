"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { ArrowLeft, AlertTriangle, Activity, BarChart2, Filter, Info, ShieldCheck } from "lucide-react";
import ScrollReveal from "@/components/ScrollReveal";
import {
  fetchAnomalyDetail,
  fetchMetrics,
  fetchAnomalyDrivers,
  fetchTimeseries,
  Anomaly,
  Metric,
  AnomalyDriversResponse,
  TimeseriesResponse,
} from "@/app/api";
import SegmentBarChart from "@/components/SegmentBarChart";
import FeedbackControl from "@/components/FeedbackControl";
import { useApi } from "@/hooks/useApi";
import { useSWRConfig } from "swr";

// Dynamically import Plotly chart component to prevent SSR window issues
const MetricChart = dynamic(() => import("@/components/MetricChart"), {
  ssr: false,
  loading: () => (
    <div className="flex h-96 w-full items-center justify-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400 animate-pulse">
      Loading timeseries chart...
    </div>
  ),
});

export default function AnomalyDetailPage({ params }: { params: { id: string } }) {
  const anomalyId = parseInt(params.id, 10);

  const [selectedSegment, setSelectedSegment] = useState<string | null>(null);
  const { mutate } = useSWRConfig();
  const { data: anomaly, error: anomalyError, isLoading: loadingAnomaly } = useApi<Anomaly>(
    !isNaN(anomalyId) ? `/api/v1/anomalies/${anomalyId}` : null
  );
  
  const { data: metrics, isLoading: loadingMetrics } = useApi<Metric[]>("/api/v1/metrics");
  
  const { data: drivers, isLoading: loadingDrivers } = useApi<AnomalyDriversResponse>(
    !isNaN(anomalyId) ? `/api/v1/anomalies/${anomalyId}/drivers` : null
  );

  const metric = metrics?.find((m) => m.id === anomaly?.metric_id) || null;

  const tsUrl = metric 
    ? (selectedSegment ? `/api/v1/metrics/${metric.id}/timeseries?segment=${encodeURIComponent(selectedSegment)}` : `/api/v1/metrics/${metric.id}/timeseries`) 
    : null;
    
  const { data: timeseries, isLoading: tsLoading } = useApi<TimeseriesResponse>(tsUrl);

  const loading = loadingAnomaly || loadingMetrics || loadingDrivers;
  const error = anomalyError ? anomalyError.message : isNaN(anomalyId) ? "Invalid Anomaly ID" : null;

  const handleFeedbackSubmitted = async (updatedAnomaly: Anomaly) => {
    // Update local cache without revalidating instantly
    mutate(`/api/v1/anomalies/${anomalyId}`, updatedAnomaly, false);
    // Refresh metrics to get updated z_score_weight if returned
    mutate("/api/v1/metrics");
  };

  if (loading) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-24 text-slate-100">
        <div className="flex flex-col items-center gap-4">
          <Activity className="h-12 w-12 animate-pulse text-cyan-400" />
          <p className="text-slate-400 font-medium animate-pulse">Loading anomaly root-cause detail...</p>
        </div>
      </main>
    );
  }

  if (error || !anomaly || !metric || !drivers) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-24 text-slate-100">
        <div className="max-w-md rounded-xl border border-red-900 bg-red-950/20 p-6 text-center text-red-200">
          <AlertTriangle className="mx-auto h-12 w-12 text-red-500 mb-4" />
          <h2 className="text-xl font-bold mb-2">Error Loading Anomaly</h2>
          <p className="text-slate-400 text-sm mb-4">{error || "Anomaly not found"}</p>
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-lg bg-slate-800 px-4 py-2 text-white font-medium hover:bg-slate-700 transition"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </Link>
        </div>
      </main>
    );
  }

  // Top structural importance feature
  const topStructural = drivers.structural_importance && drivers.structural_importance.length > 0
    ? drivers.structural_importance[0]
    : null;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-12">
      <div className="mx-auto max-w-7xl space-y-8">
        <ScrollReveal direction="up">
          <div className="space-y-8">
            {/* Navigation & Header */}
            <div>
              <Link
                href="/"
                className="inline-flex items-center gap-2 text-sm font-semibold text-slate-400 hover:text-cyan-400 transition mb-6"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to Overview
              </Link>

              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 border-b border-slate-800 pb-6">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <span className="rounded-md bg-amber-500/10 px-2.5 py-1 text-xs font-bold text-amber-400 border border-amber-500/20 shadow-glow-amber-sm">
                      ANOMALY #{anomaly.id}
                    </span>
                    <span className="text-slate-400 text-xs font-semibold">
                      Detected on {anomaly.date}
                    </span>
                  </div>
                  <h1 className="text-3xl font-extrabold tracking-tight text-white flex items-center gap-3">
                    <span>{metric.name}</span>
                    <span className="text-sm font-normal text-slate-400">({metric.grain})</span>
                  </h1>
                </div>

                <div className="flex flex-wrap items-center gap-4">
                  {/* Severity Badge */}
                  <div className="flex flex-col items-end glass-card-lg rounded-xl px-4 py-2 shadow-glow-amber-sm">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                      Severity Score
                    </span>
                    <span className="text-xl font-black text-amber-400">
                      {anomaly.severity_score.toFixed(1)}
                    </span>
                  </div>

                  {/* Type Badge */}
                  <div className="flex flex-col items-end glass-card-lg rounded-xl px-4 py-2 shadow-glow-cyan-sm">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                      Classification
                    </span>
                    <span className="text-sm font-bold text-cyan-400 uppercase">
                      {anomaly.type.replace("_", " ")}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Prominent Explanation Card */}
            <div className="glass-card-lg rounded-2xl border border-cyan-500/30 bg-linear-to-r from-cyan-950/40 via-slate-900 to-indigo-950/40 p-6 md:p-8 relative overflow-hidden shadow-glow-cyan-sm">
              <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none">
                <BarChart2 className="h-48 w-48 text-cyan-400" />
              </div>
              
              <div className="relative z-10">
                <span className="text-xs font-extrabold text-cyan-400 uppercase tracking-widest mb-2 block">
                  Root-Cause Driver Explanation
                </span>
                <p className="text-xl md:text-2xl font-bold leading-relaxed text-slate-100">
                  "{drivers.explanation_text}"
                </p>
              </div>
            </div>
          </div>
        </ScrollReveal>

        {/* Feedback Control Section */}
        <FeedbackControl
          anomalyId={anomaly.id}
          currentStatus={anomaly.status}
          onFeedbackSubmitted={handleFeedbackSubmitted}
        />

        {/* Main Driver Analysis Section: Segment Bar Chart */}
        <ScrollReveal direction="up" delay={0.25}>
          <div className="space-y-8">
            <SegmentBarChart
              driversData={drivers}
              metric={metric}
              selectedSegment={selectedSegment}
              onSelectSegment={(seg) => setSelectedSegment(seg)}
            />

            {/* Secondary Context Callout: Structural Importance */}
            <div className="glass-card-lg rounded-xl p-4 sm:p-5">
              <div className="flex items-start gap-3">
                <Info className="h-5 w-5 text-indigo-400 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
                    Historical Structural Context
                  </h4>
                  {topStructural ? (
                    <p className="text-sm text-slate-300 font-medium">
                      Historically, <strong className="text-indigo-300">{topStructural.feature}</strong> tends to matter most for this metric (relative predictive importance of {topStructural.importance.toFixed(1)}%).
                    </p>
                  ) : (
                    <p className="text-sm text-slate-400">
                      Historically, feature importance data requires at least 30 days of historical data to train.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </ScrollReveal>

        {/* Time-Series Chart Component with Segment Filter State */}
        <ScrollReveal direction="up" delay={0.15}>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h3 className="text-xl font-bold text-slate-100">
                  Timeseries Trend & Baseline
                </h3>
                {selectedSegment ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-cyan-950 px-3 py-1 text-xs font-bold text-cyan-300 border border-cyan-800 shadow-glow-cyan-sm">
                    <Filter className="h-3.5 w-3.5" />
                    Filtered: {selectedSegment}
                  </span>
                ) : (
                  <span className="rounded-full bg-slate-800 px-3 py-1 text-xs font-semibold text-slate-400">
                    Total Metric Series
                  </span>
                )}
              </div>

              {selectedSegment && (
                <button
                  onClick={() => setSelectedSegment(null)}
                  className="text-xs font-bold text-cyan-400 hover:text-cyan-300 hover:underline transition"
                >
                  Reset to Total Metric Series
                </button>
              )}
            </div>

            {tsLoading ? (
              <div className="flex h-96 items-center justify-center glass-card-lg rounded-xl text-slate-400 font-medium animate-pulse">
                Loading segment timeseries...
              </div>
            ) : timeseries ? (
              <MetricChart
                points={timeseries.points}
                anomalies={selectedSegment ? [] : [anomaly]}
                mad={timeseries.mad}
                metricName={selectedSegment ? `${metric.name} (${selectedSegment})` : metric.name}
                unit={metric.unit}
              />
            ) : null}
          </div>
        </ScrollReveal>
      </div>
    </main>
  );
}
