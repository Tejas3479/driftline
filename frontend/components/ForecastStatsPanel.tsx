"use client";

import React from "react";
import { AccuracyResponse } from "../app/api";

interface ForecastStatsPanelProps {
  accuracy: AccuracyResponse | null;
  modelVersion: string | null;
  backend: string;
}

export default function ForecastStatsPanel({
  accuracy,
  modelVersion,
  backend,
}: ForecastStatsPanelProps) {
  const mapeText = accuracy?.mape !== null && accuracy?.mape !== undefined
    ? `${(accuracy.mape * 100).toFixed(2)}%`
    : "N/A (Cold start)";

  const coverageText = accuracy?.coverage_pct !== null && accuracy?.coverage_pct !== undefined
    ? `${(accuracy.coverage_pct * 100).toFixed(1)}%`
    : "N/A";

  const isCoverageWellCalibrated = accuracy?.coverage_pct !== null && accuracy?.coverage_pct !== undefined
    ? Math.abs(accuracy.coverage_pct - 0.8) <= 0.1
    : true;

  const totalEvals = accuracy?.total_evaluations ?? 0;
  const mlEvals = accuracy?.ml_evaluations ?? 0;

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-8">
      {/* MAPE Card */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-5 shadow-lg">
        <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-2">
          12-Week MAPE
        </h4>
        <p className="text-3xl font-extrabold text-cyan-400">
          {mapeText}
        </p>
        <p className="text-slate-500 text-[11px] font-semibold mt-1">
          Mean Absolute Percentage Error
        </p>
      </div>

      {/* Coverage Card */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-5 shadow-lg">
        <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-2">
          80% Interval Coverage
        </h4>
        <div className="flex items-baseline gap-2">
          <p
            className={`text-3xl font-extrabold ${
              isCoverageWellCalibrated ? "text-purple-400" : "text-amber-400"
            }`}
          >
            {coverageText}
          </p>
          <span className="text-xs font-bold text-slate-500">(Target: ~80%)</span>
        </div>
        <p className="text-slate-500 text-[11px] font-semibold mt-1">
          Actual points within p10–p90 band
        </p>
      </div>

      {/* Evaluated Folds Card */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-5 shadow-lg">
        <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-2">
          Evaluated Folds
        </h4>
        <p className="text-3xl font-extrabold text-white">
          {mlEvals}{" "}
          <span className="text-slate-500 text-sm font-semibold">
            / {totalEvals} total
          </span>
        </p>
        <p className="text-slate-500 text-[11px] font-semibold mt-1">
          Walk-forward backtest folds
        </p>
      </div>

      {/* Model Backend & Version Card */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-5 shadow-lg">
        <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-2">
          Model Engine
        </h4>
        <p className="text-2xl font-extrabold text-slate-200 capitalize">
          {backend}
        </p>
        <p className="text-slate-400 font-mono text-xs mt-1">
          {modelVersion || `${backend}-v1`}
        </p>
      </div>
    </div>
  );
}
