"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { 
  AlertTriangle, 
  TrendingUp, 
  ArrowRight, 
  BarChart2, 
  Activity, 
  RefreshCw, 
  Terminal, 
  Database,
  ShieldAlert,
  Zap
} from "lucide-react";
import { motion } from "framer-motion";
import ScrollReveal from "@/components/ScrollReveal";
import AtroposCard from "@/components/AtroposCard";
import GlowButton from "@/components/GlowButton";
import DataUploadModal from "@/components/DataUploadModal";
import { useApi } from "@/hooks/useApi";
import { useSWRConfig } from "swr";
import { Metric, TimeseriesResponse, Anomaly, TimeseriesPoint } from "@/app/api";

function MetricCard({ metric }: { metric: Metric }) {
  const { data: tsData, isLoading: tsLoading } = useApi<TimeseriesResponse>(`/api/v1/metrics/${metric.id}/timeseries`);
  const { data: anomalies = [], isLoading: anomLoading } = useApi<Anomaly[]>(`/api/v1/metrics/${metric.id}/anomalies`);

  const points = tsData?.points || [];

  const {
    latestValue,
    recentAnomaly,
    pctChange,
    absChange,
    sparklinePoints,
  } = useMemo(() => {
    let latestVal: number | null = null;
    let recentAnom: Anomaly | null = null;
    let pctChg: number | null = null;
    let absChg: number | null = null;
    let sparklinePts: TimeseriesPoint[] = [];

    if (points.length > 0) {
      const sortedPoints = [...points].sort(
        (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
      );
      latestVal = sortedPoints[sortedPoints.length - 1].value_total;
      sparklinePts = sortedPoints.slice(-30);

      const maxDate = new Date(sortedPoints[sortedPoints.length - 1].date);
      const sevenDaysAgo = new Date(maxDate.getTime() - 7 * 24 * 60 * 60 * 1000);

      const newRecentAnoms = anomalies
        .filter((a) => {
          const aDate = new Date(a.date);
          return a.status === "new" && aDate >= sevenDaysAgo && aDate <= maxDate;
        })
        .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

      if (newRecentAnoms.length > 0) {
        recentAnom = newRecentAnoms[0];
        const pt = sortedPoints.find((p) => p.date === recentAnom!.date);
        if (pt && pt.trend !== null && pt.seasonal !== null) {
          const expected = pt.trend + pt.seasonal;
          const actual = pt.value_total;

          if (Math.abs(expected) >= 1e-3) {
            pctChg = ((actual - expected) / expected) * 100;
          } else {
            absChg = actual - expected;
          }
        }
      }
    }

    return {
      latestValue: latestVal,
      recentAnomaly: recentAnom,
      pctChange: pctChg,
      absChange: absChg,
      sparklinePoints: sparklinePts,
    };
  }, [points, anomalies]);

  if (tsLoading || anomLoading) {
    return (
      <div className="h-64 rounded-2xl glass-panel p-6 flex flex-col justify-between animate-pulse">
        <div className="space-y-3">
          <div className="h-4 w-24 rounded-sm bg-slate-800" />
          <div className="h-6 w-48 rounded-sm bg-slate-800" />
        </div>
        <div className="h-12 w-32 rounded-sm bg-slate-800" />
        <div className="h-10 w-full rounded-xl bg-slate-800/60" />
      </div>
    );
  }

  const hasAnomaly = recentAnomaly !== null;

  let sparklineSvgPath = "";
  let sparklineAreaPath = "";
  if (sparklinePoints.length > 1) {
    const vals = sparklinePoints.map((p) => p.value_total);
    const minVal = Math.min(...vals);
    const maxVal = Math.max(...vals);
    const valRange = maxVal - minVal || 1.0;

    const width = 130;
    const height = 44;

    const coordinates = sparklinePoints.map((p, idx) => {
      const x = (idx / (sparklinePoints.length - 1)) * width;
      const y = height - ((p.value_total - minVal) / valRange) * (height - 6) - 3;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    sparklineSvgPath = `M ${coordinates.join(" L ")}`;
    sparklineAreaPath = `M 0,${height} L ${coordinates.join(" L ")} L ${width},${height} Z`;
  }

  const strokeColor = hasAnomaly ? "#f59e0b" : "#22d3ee";
  const gradientId = `sparkline-grad-${metric.id}`;

  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 16 },
        show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
      }}
      whileHover={{ y: -4, transition: { duration: 0.15 } }}
      className="h-full"
    >
      <AtroposCard intensity="subtle" className="h-full">
        <div
          className={`relative flex flex-col justify-between rounded-3xl p-6 glass-card shadow-2xl h-full ${
            hasAnomaly
              ? "border-amber-500/40 hover:border-amber-500/70 hover:shadow-amber-500/10 hover:shadow-glow-amber-sm"
              : "border-slate-800/80 hover:border-cyan-500/40 hover:shadow-cyan-500/10 hover:shadow-glow-cyan-sm"
          }`}
        >
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-[11px] font-mono font-extrabold uppercase tracking-wider text-slate-500 bg-slate-950/80 border border-slate-800 px-2.5 py-0.5 rounded-lg">
                METRIC #{metric.id}
              </span>
              <span className="rounded-full bg-cyan-950/50 px-2.5 py-0.5 text-[11px] font-extrabold text-cyan-300 border border-cyan-800/40 uppercase">
                {metric.grain}
              </span>
            </div>

            <h3 className="text-xl font-extrabold text-white mb-2 truncate">
              {metric.name}
            </h3>

            <div className="flex items-end justify-between gap-4 mt-6 mb-6">
              <div>
                <p className="text-3xl font-extrabold tracking-tight font-mono text-white">
                  {latestValue !== null ? latestValue.toLocaleString() : "--"}
                </p>
                <p className="text-slate-400 text-xs font-semibold mt-1">
                  Latest Value ({metric.unit || "units"})
                </p>
              </div>

              {sparklineSvgPath && (
                <div className="flex flex-col items-end">
                  <svg className="h-11 w-32 overflow-visible" viewBox="0 0 130 44">
                    <defs>
                      <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={strokeColor} stopOpacity="0.35" />
                        <stop offset="100%" stopColor={strokeColor} stopOpacity="0.0" />
                      </linearGradient>
                    </defs>
                    <path d={sparklineAreaPath} fill={`url(#${gradientId})`} />
                    <path
                      d={sparklineSvgPath}
                      fill="none"
                      stroke={strokeColor}
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <span className="text-[10px] font-bold text-slate-500 font-mono mt-1">
                    30d trend
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-800/80">
            {hasAnomaly && recentAnomaly ? (
              <Link
                href={`/anomalies/${recentAnomaly.id}`}
                className="flex items-start gap-3 rounded-2xl bg-amber-950/40 border border-amber-500/40 p-3.5 hover:bg-amber-950/80 transition duration-300 group"
              >
                <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5 animate-pulse" />
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
                  <span className="text-[10px] text-amber-400 font-extrabold tracking-wider mt-1 block">
                    ROOT-CAUSE DRIVERS →
                  </span>
                </div>
              </Link>
            ) : (
              <Link
                href={`/metrics/${metric.id}`}
                className="flex items-center justify-between rounded-2xl bg-slate-900/60 border border-slate-800 p-3.5 hover:bg-slate-800/60 transition duration-300 text-slate-300 hover:text-white group"
              >
                <span className="text-xs font-bold">View Timeseries Dashboard</span>
                <ArrowRight className="h-4 w-4 text-cyan-400 group-hover:translate-x-1 transition" />
              </Link>
            )}
          </div>
        </div>
      </AtroposCard>
    </motion.div>
  );
}

export default function Home() {
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  
  const { data: metrics = [], error: metricsError, isLoading, mutate } = useApi<Metric[]>("/api/v1/metrics");
  const { mutate: globalMutate } = useSWRConfig();
  
  const retrying = isLoading;
  const loading = isLoading;
  const error = metricsError ? metricsError.message : null;
  const loadData = () => { mutate(); };

  if (loading) {
    return (
      <main className="min-h-screen bg-mesh-pattern text-slate-100 p-8 md:p-16">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12 border-b border-slate-800/80 pb-8">
            <div className="space-y-3">
              <div className="h-9 w-64 rounded-xl bg-slate-900 animate-pulse" />
              <div className="h-4 w-96 rounded-lg bg-slate-900/60 animate-pulse" />
            </div>
            <div className="h-8 w-44 rounded-full bg-slate-900/80 animate-pulse" />
          </div>

          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-64 rounded-2xl glass-panel p-6 flex flex-col justify-between animate-pulse"
              >
                <div className="space-y-3">
                  <div className="h-4 w-24 rounded-sm bg-slate-800" />
                  <div className="h-6 w-48 rounded-sm bg-slate-800" />
                </div>
                <div className="h-12 w-32 rounded-sm bg-slate-800" />
                <div className="h-10 w-full rounded-xl bg-slate-800/60" />
              </div>
            ))}
          </div>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-mesh-pattern p-6 md:p-12 text-slate-100">
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-xl w-full rounded-3xl border border-amber-500/30 bg-slate-950/80 backdrop-blur-2xl p-8 md:p-10 shadow-2xl glow-amber text-center relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none">
            <Database className="h-40 w-40 text-amber-500" />
          </div>

          <div className="relative z-10">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-400 mb-6">
              <AlertTriangle className="h-8 w-8 animate-bounce" />
            </div>

            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-950/80 border border-amber-800/60 px-3 py-1 text-xs font-bold text-amber-300 uppercase tracking-widest mb-4">
              <span className="h-2 w-2 rounded-full bg-amber-400 animate-ping" /> Engine Disconnected
            </span>

            <h2 className="text-2xl font-extrabold tracking-tight text-white mb-2">
              Driftline Backend Offline
            </h2>

            <p className="text-slate-400 text-sm leading-relaxed mb-6">
              Could not establish connection to the FastAPI analysis engine at <code className="font-mono text-cyan-400 bg-slate-900 px-1.5 py-0.5 rounded-sm">http://127.0.0.1:8000</code>.
            </p>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-left text-xs space-y-2 mb-6">
              <div className="font-bold text-slate-300 flex items-center gap-1.5">
                <Terminal className="h-4 w-4 text-cyan-400" /> How to Start the Engine:
              </div>
              <p className="text-slate-400 font-mono bg-slate-950 p-2.5 rounded-xl border border-slate-800 text-[11px] overflow-x-auto text-cyan-300">
                1. docker compose up -d db<br />
                2. python -m uvicorn main:app --port 8000
              </p>
            </div>

            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={loadData}
              disabled={retrying}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-linear-to-r from-amber-500 to-orange-600 px-6 py-3 text-sm font-extrabold text-slate-950 hover:from-amber-400 hover:to-orange-500 transition shadow-lg shadow-amber-500/20 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${retrying ? "animate-spin" : ""}`} />
              {retrying ? "Reconnecting..." : "Retry Connection"}
            </motion.button>
          </div>
        </motion.div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-mesh-pattern text-slate-100 p-8 md:p-16">
      <div className="mx-auto max-w-7xl relative">
        <div className="absolute top-0 left-1/4 -z-10 h-72 w-72 rounded-full bg-linear-to-tr from-cyan-500/15 to-indigo-500/10 blur-3xl pointer-events-none" />

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12 border-b border-slate-800/80 pb-8">
          <div>
            <div className="flex items-center gap-2.5 mb-2">
              <span className="inline-flex items-center gap-1 text-[11px] font-extrabold uppercase tracking-widest bg-cyan-950/60 text-cyan-300 border border-cyan-800/50 px-2.5 py-0.5 rounded-full">
                <Zap className="h-3 w-3 text-cyan-400" /> Automated Anomaly Engine
              </span>
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-gradient-cyan mb-2">
              Driftline Intelligence
            </h1>
            <p className="text-slate-400 font-medium text-sm">
              Real-time statistical decomposition, driver attribution, and quantile forecasting
            </p>
          </div>

          <div className="flex items-center gap-3 bg-slate-900/60 border border-slate-800 px-4 py-2 rounded-2xl glass-panel">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
            </span>
            <span className="text-slate-300 text-xs font-bold">Engine Operational</span>
          </div>
        </div>

        {metrics.length === 0 && (
          <div className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-slate-800 bg-slate-900/20 p-16 text-center glass-panel">
            <BarChart2 className="h-16 w-16 text-slate-600 mb-4 animate-pulse" />
            <h3 className="text-xl font-bold text-slate-300 mb-2">No Active Metrics Configured</h3>
            <p className="text-slate-500 text-sm max-w-sm mb-6">
              Get started by uploading timeseries observations or configuring automated ingestion connectors.
            </p>
            <GlowButton onClick={() => setUploadModalOpen(true)} className="mb-4">
              <Database className="h-4 w-4 mr-2" /> Upload your first metric
            </GlowButton>
            
            <DataUploadModal 
              isOpen={uploadModalOpen} 
              onClose={() => setUploadModalOpen(false)}
              onSuccess={() => window.location.reload()}
            />
          </div>
        )}

        <ScrollReveal direction="up" staggerChildren stagger={0.08}>
          <motion.div
            initial="hidden"
            animate="show"
            variants={{
              hidden: { opacity: 0 },
              show: {
                opacity: 1,
                transition: { staggerChildren: 0.08 },
              },
            }}
            className="grid gap-8 md:grid-cols-2 lg:grid-cols-3"
          >
            {metrics.map((metric) => (
              <MetricCard key={metric.id} metric={metric} />
            ))}
          </motion.div>
        </ScrollReveal>
      </div>
    </main>
  );
}
