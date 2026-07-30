"use client";

import React from "react";
import { AccuracyResponse } from "../app/api";
import CountUp from "./CountUp";

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
  const mapeVal = accuracy?.mape != null ? accuracy.mape * 100 : null;
  const hasMape = mapeVal !== null;

  const coverageVal = accuracy?.coverage_pct != null ? accuracy.coverage_pct * 100 : null;
  const hasCoverage = coverageVal !== null;

  const isCoverageWellCalibrated = accuracy?.coverage_pct != null
    ? Math.abs(accuracy.coverage_pct - 0.8) <= 0.1
    : true;

  const totalEvals = accuracy?.total_evaluations ?? 0;
  const mlEvals = accuracy?.ml_evaluations ?? 0;

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-8">
      {/* MAPE Card */}
      <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 backdrop-blur-sm p-5 shadow-lg transition-all duration-300 hover:border-cyan-500/30 hover:shadow-glow-cyan-sm">
        <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-2">
          12-Week MAPE
        </h4>
        <p className="text-3xl font-extrabold text-cyan-400">
          {mapeVal !== null ? (
            <CountUp to={mapeVal} decimals={2} suffix="%" />
          ) : (
            "N/A (Cold start)"
          )}
        </p>
        <p className="text-slate-500 text-[11px] font-semibold mt-1">
          Mean Absolute Percentage Error
        </p>
      </div>

      {/* Coverage Card */}
      <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 backdrop-blur-sm p-5 shadow-lg transition-all duration-300 hover:border-cyan-500/30 hover:shadow-glow-cyan-sm">
        <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-2">
          80% Interval Coverage
        </h4>
        <div className="flex items-baseline gap-2">
          <p
            className={`text-3xl font-extrabold ${
              isCoverageWellCalibrated ? "text-purple-400" : "text-amber-400"
            }`}
          >
            {coverageVal !== null ? (
              <CountUp to={coverageVal} decimals={1} suffix="%" />
            ) : (
              "N/A"
            )}
          </p>
          <span className="text-xs font-bold text-slate-500">(Target: ~80%)</span>
        </div>
        <p className="text-slate-500 text-[11px] font-semibold mt-1">
          Actual points within p10–p90 band
        </p>
      </div>

      {/* Evaluated Folds Card */}
      <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 backdrop-blur-sm p-5 shadow-lg transition-all duration-300 hover:border-cyan-500/30 hover:shadow-glow-cyan-sm">
        <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-2">
          Evaluated Folds
        </h4>
        <p className="text-3xl font-extrabold text-white">
          <CountUp to={mlEvals} decimals={0} />{" "}
          <span className="text-slate-500 text-sm font-semibold">
            / {totalEvals} total
          </span>
        </p>
        <p className="text-slate-500 text-[11px] font-semibold mt-1">
          Walk-forward backtest folds
        </p>
      </div>

      {/* Model Backend & Version Card */}
      <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 backdrop-blur-sm p-5 shadow-lg transition-all duration-300 hover:border-cyan-500/30 hover:shadow-glow-cyan-sm">
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
