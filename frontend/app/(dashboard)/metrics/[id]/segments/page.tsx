"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { ArrowLeft, AlertTriangle, Activity, Info, LayoutGrid } from "lucide-react";
import { fetchMetrics, fetchSegmentComparison, Metric } from "@/app/api";

// Dynamically import SegmentComparisonChart to prevent SSR window/DOM issues with vega-embed
const SegmentComparisonChart = dynamic(() => import("@/components/SegmentComparisonChart"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[450px] w-full items-center justify-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400">
      <div className="flex flex-col items-center gap-2">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
        <p className="text-sm font-semibold animate-pulse mt-2">Loading Vega-Lite segment comparison grid...</p>
      </div>
    </div>
  ),
});

type RangeFilter = "7d" | "30d" | "90d" | "1y" | "all";

export default function SegmentComparisonPage({ params }: { params: { id: string } }) {
  const metricId = parseInt(params.id);
  const [loading, setLoading] = useState(true);
  const [fetchingControls, setFetchingControls] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [metric, setMetric] = useState<Metric | null>(null);
  const [selectedDimension, setSelectedDimension] = useState<string | undefined>(undefined);
  const [range, setRange] = useState<RangeFilter>("all");
  const [vegaSpec, setVegaSpec] = useState<any>(null);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    async function loadData() {
      try {
        if (!metric) {
          setLoading(true);
        } else {
          setFetchingControls(true);
        }
        setError(null);

        // Fetch metric details if not already loaded
        let currentMetric = metric;
        if (!currentMetric) {
          const metrics = await fetchMetrics();
          currentMetric = metrics.find((m) => m.id === metricId) || null;
          if (!currentMetric) {
            throw new Error(`Metric #${metricId} not found.`);
          }
          setMetric(currentMetric);
        }

        // Fetch Vega-Lite spec from backend with server-side date range filtering
        const spec = await fetchSegmentComparison(
          metricId,
          selectedDimension,
          range,
          undefined,
          undefined,
          signal
        );

        setVegaSpec(spec);

        // Extract effective dimension name if not set
        if (!selectedDimension && spec && spec.title) {
          // If dimension wasn't explicitly selected, spec is for default dimension
        }
      } catch (err: any) {
        if (err.name === "AbortError") return;
        console.error("Failed to load segment comparison spec:", err);
        setError(err.message || "Failed to load segment comparison data.");
      } finally {
        setLoading(false);
        setFetchingControls(false);
      }
    }

    if (metricId) {
      loadData();
    }

    return () => {
      controller.abort();
    };
  }, [metricId, selectedDimension, range]);

  if (loading) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-24 text-slate-100">
        <div className="flex flex-col items-center gap-4">
          <Activity className="h-10 w-10 animate-spin text-cyan-400" />
          <p className="text-slate-400 font-medium animate-pulse">
            Generating small-multiples segment comparison...
          </p>
        </div>
      </main>
    );
  }

  if (error || !metric) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-24 text-slate-100">
        <div className="max-w-md rounded-xl border border-red-900 bg-red-950/20 p-6 text-center text-red-200">
          <AlertTriangle className="mx-auto h-12 w-12 text-red-500 mb-4" />
          <h2 className="text-xl font-bold mb-2">Segment Comparison Unavailable</h2>
          <p className="text-slate-400 text-sm mb-6">{error || "Metric dimensions not configured."}</p>
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
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 mb-8 border-b border-slate-800 pb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-slate-500 text-xs font-extrabold uppercase tracking-widest bg-slate-900 border border-slate-800 px-2 py-0.5 rounded">
                Metric #{metric.id}
              </span>
              <span className="rounded-full bg-cyan-950/50 px-2.5 py-0.5 text-xs font-semibold text-cyan-300 border border-cyan-800/40 flex items-center gap-1">
                <LayoutGrid className="h-3.5 w-3.5" /> Altair Small-Multiples
              </span>
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-white mb-2">
              {metric.name} Segment Comparison
            </h1>
            <p className="text-slate-400 font-medium text-sm">
              Side-by-side segment analysis on a unified, shared y-axis scale
            </p>
          </div>

          {/* Controls: Range Selector */}
          <div className="flex items-center gap-4 bg-slate-900 p-2.5 rounded-xl border border-slate-800 shadow-lg">
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
              <span className="text-slate-500 text-[11px] font-bold uppercase px-2">
                Range:
              </span>
              {(["7d", "30d", "90d", "1y", "all"] as RangeFilter[]).map((r) => (
                <button
                  key={r}
                  onClick={() => setRange(r)}
                  className={`px-3 py-1 rounded text-xs font-bold uppercase transition-all ${
                    range === r
                      ? "bg-cyan-500 text-slate-950 shadow"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>

            {fetchingControls && (
              <div className="flex items-center gap-2 text-cyan-400 text-xs font-semibold px-2 animate-pulse">
                <Activity className="h-3.5 w-3.5 animate-spin" /> Updating...
              </div>
            )}
          </div>
        </div>

        {/* Informative Shared Y-Scale Callout Banner */}
        <div className="flex items-start gap-3 rounded-xl border border-cyan-900/40 bg-cyan-950/20 p-4 text-cyan-200 shadow-md mb-8">
          <Info className="h-5 w-5 text-cyan-400 shrink-0 mt-0.5" />
          <div className="text-sm">
            <h4 className="font-bold text-cyan-300 mb-1">
              Shared Vertical Scale Invariant
            </h4>
            <p className="text-cyan-200/80 leading-relaxed">
              All segment facets share an identical global vertical domain scale computed across the entire metric. 
              This prevents scale distortion and allows instant visual identification of segments driving total performance shifts.
            </p>
          </div>
        </div>

        {/* Vega-Lite Small-Multiples Chart */}
        <div className="mb-12">
          <SegmentComparisonChart spec={vegaSpec} />
        </div>
      </div>
    </main>
  );
}
