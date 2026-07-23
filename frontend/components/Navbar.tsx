"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart2,
  TrendingUp,
  LayoutGrid,
  ShieldAlert,
  Settings,
  Layers,
  ChevronDown,
} from "lucide-react";
import { useMetricContext } from "./MetricContext";

export default function Navbar() {
  const pathname = usePathname();
  const { selectedMetricId, setSelectedMetricId, metrics, loading } = useMetricContext();

  const isMetricDisabled = !selectedMetricId || metrics.length === 0;
  const metricId = selectedMetricId ?? 1;

  const currentMetric = metrics.find((m) => m.id === selectedMetricId);

  const isActive = (path: string) => {
    if (path === "/") return pathname === "/";
    if (path === "/anomalies") return pathname === "/anomalies";
    if (path === "/settings") return pathname === "/settings";
    return pathname.startsWith(path);
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">
        {/* Brand Logo & Context Selector */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-cyan-500 to-purple-600 shadow-md group-hover:scale-105 transition-transform">
              <Activity className="h-5 w-5 text-slate-950 stroke-[2.5]" />
            </div>
            <span className="text-lg font-extrabold tracking-tight text-white">
              Driftline
            </span>
          </Link>

          {/* Metric Selector Dropdown */}
          <div className="relative">
            {metrics.length > 0 ? (
              <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-xs font-semibold">
                <Layers className="h-3.5 w-3.5 text-cyan-400" />
                <select
                  value={selectedMetricId ?? ""}
                  onChange={(e) => setSelectedMetricId(parseInt(e.target.value, 10))}
                  className="bg-transparent text-slate-200 font-medium focus:outline-none cursor-pointer pr-1"
                >
                  {metrics.map((m) => (
                    <option key={m.id} value={m.id} className="bg-slate-900 text-slate-200">
                      {m.name} (#{m.id})
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <span className="text-[11px] font-semibold text-slate-500 bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-md">
                {loading ? "Loading metrics..." : "No metrics configured"}
              </span>
            )}
          </div>
        </div>

        {/* Global Navigation Links */}
        <nav className="flex items-center gap-1 md:gap-2">
          {/* Overview */}
          <Link
            href="/"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
              isActive("/") && pathname === "/"
                ? "bg-slate-800 text-cyan-300 border border-slate-700"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
            }`}
          >
            <BarChart2 className="h-3.5 w-3.5" />
            Overview
          </Link>

          {/* Time Series */}
          <Link
            href={isMetricDisabled ? "#" : `/metrics/${metricId}`}
            title={isMetricDisabled ? "Upload your first metric to unlock" : "View Time Series"}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
              isMetricDisabled
                ? "pointer-events-none opacity-40 text-slate-600"
                : isActive(`/metrics/${metricId}`) && !pathname.includes("/forecast") && !pathname.includes("/segments")
                ? "bg-slate-800 text-cyan-300 border border-slate-700"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
            }`}
          >
            <Activity className="h-3.5 w-3.5" />
            Time Series
          </Link>

          {/* Anomaly Log */}
          <Link
            href="/anomalies"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
              isActive("/anomalies")
                ? "bg-slate-800 text-cyan-300 border border-slate-700"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
            }`}
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            Anomaly Log
          </Link>

          {/* Forecast */}
          <Link
            href={isMetricDisabled ? "#" : `/metrics/${metricId}/forecast`}
            title={isMetricDisabled ? "Upload your first metric to unlock" : "View Forecast"}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
              isMetricDisabled
                ? "pointer-events-none opacity-40 text-slate-600"
                : isActive(`/metrics/${metricId}/forecast`)
                ? "bg-purple-950/60 text-purple-300 border border-purple-800/50"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
            }`}
          >
            <TrendingUp className="h-3.5 w-3.5 text-purple-400" />
            Forecast
          </Link>

          {/* Segment Comparison */}
          <Link
            href={isMetricDisabled ? "#" : `/metrics/${metricId}/segments`}
            title={isMetricDisabled ? "Upload your first metric to unlock" : "View Segment Comparison"}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
              isMetricDisabled
                ? "pointer-events-none opacity-40 text-slate-600"
                : isActive(`/metrics/${metricId}/segments`)
                ? "bg-cyan-950/60 text-cyan-300 border border-cyan-800/50"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
            }`}
          >
            <LayoutGrid className="h-3.5 w-3.5 text-cyan-400" />
            Segment Comparison
          </Link>

          {/* Settings & Health */}
          <Link
            href="/settings"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
              isActive("/settings")
                ? "bg-slate-800 text-cyan-300 border border-slate-700"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
            }`}
          >
            <Settings className="h-3.5 w-3.5" />
            Model Health & Settings
          </Link>
        </nav>
      </div>
    </header>
  );
}
