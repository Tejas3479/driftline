"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import {
  ShieldAlert,
  Search,
  ArrowUpRight,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  Activity,
  CheckCircle,
  AlertTriangle,
  XCircle,
  HelpCircle,
  SlidersHorizontal,
} from "lucide-react";
import { fetchGlobalAnomalies, GlobalAnomaly } from "../api";

type StatusTab = "all" | "new" | "reviewed" | "resolved" | "false_positive";
type SortOption = "date_desc" | "date_asc" | "severity_desc" | "severity_asc";

export default function GlobalAnomalyLogPage() {
  const [anomalies, setAnomalies] = useState<GlobalAnomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<StatusTab>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortOption>("date_desc");

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    async function loadAnomalies() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchGlobalAnomalies(
          activeTab === "all" ? undefined : activeTab,
          undefined,
          signal
        );
        setAnomalies(data);
      } catch (err: any) {
        if (err.name === "AbortError") return;
        console.error("Failed to load anomalies log:", err);
        setError(err.message || "Failed to load anomaly log.");
      } finally {
        setLoading(false);
      }
    }

    loadAnomalies();

    return () => {
      controller.abort();
    };
  }, [activeTab]);

  // Client-side filtering & sorting
  const filteredAndSortedAnomalies = useMemo(() => {
    let result = [...anomalies];

    // Search query filter (matches metric name or explanation excerpt)
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (a) =>
          a.metric_name.toLowerCase().includes(q) ||
          (a.explanation_excerpt && a.explanation_excerpt.toLowerCase().includes(q))
      );
    }

    // Sort
    result.sort((a, b) => {
      if (sortBy === "date_desc") {
        return new Date(b.date).getTime() - new Date(a.date).getTime();
      } else if (sortBy === "date_asc") {
        return new Date(a.date).getTime() - new Date(b.date).getTime();
      } else if (sortBy === "severity_desc") {
        return b.severity_score - a.severity_score;
      } else if (sortBy === "severity_asc") {
        return a.severity_score - b.severity_score;
      }
      return 0;
    });

    return result;
  }, [anomalies, searchQuery, sortBy]);

  const getSeverityBadge = (score: number) => {
    if (score >= 70) {
      return (
        <span className="inline-flex items-center gap-1 rounded-md border border-red-800/50 bg-red-950/40 px-2.5 py-1 text-xs font-bold text-red-400">
          High ({Math.round(score)})
        </span>
      );
    } else if (score >= 40) {
      return (
        <span className="inline-flex items-center gap-1 rounded-md border border-amber-800/50 bg-amber-950/40 px-2.5 py-1 text-xs font-bold text-amber-400">
          Medium ({Math.round(score)})
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 rounded-md border border-slate-800 bg-slate-900 px-2.5 py-1 text-xs font-bold text-slate-400">
          Low ({Math.round(score)})
        </span>
      );
    }
  };

  const getTypeBadge = (type: string) => {
    const t = type.toLowerCase();
    if (t === "spike") {
      return (
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-cyan-400 bg-cyan-950/40 border border-cyan-800/40 px-2 py-0.5 rounded">
          <TrendingUp className="h-3 w-3" /> Spike
        </span>
      );
    } else if (t === "drop") {
      return (
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-rose-400 bg-rose-950/40 border border-rose-800/40 px-2 py-0.5 rounded">
          <TrendingDown className="h-3 w-3" /> Drop
        </span>
      );
    } else if (t === "level_shift") {
      return (
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-purple-400 bg-purple-950/40 border border-purple-800/40 px-2 py-0.5 rounded">
          <ArrowRight className="h-3 w-3" /> Level Shift
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-400 bg-amber-950/40 border border-amber-800/40 px-2 py-0.5 rounded">
          <Activity className="h-3 w-3" /> Volatility
        </span>
      );
    }
  };

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === "new") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-amber-800/50 bg-amber-950/50 px-2.5 py-0.5 text-[11px] font-extrabold text-amber-400 uppercase tracking-wider">
          <AlertTriangle className="h-3 w-3" /> New
        </span>
      );
    } else if (s === "reviewed") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-blue-800/50 bg-blue-950/50 px-2.5 py-0.5 text-[11px] font-extrabold text-blue-400 uppercase tracking-wider">
          <CheckCircle className="h-3 w-3" /> Reviewed
        </span>
      );
    } else if (s === "resolved") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-800/50 bg-emerald-950/50 px-2.5 py-0.5 text-[11px] font-extrabold text-emerald-400 uppercase tracking-wider">
          <CheckCircle className="h-3 w-3" /> Resolved
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-slate-800 bg-slate-900 px-2.5 py-0.5 text-[11px] font-extrabold text-slate-400 uppercase tracking-wider">
          <XCircle className="h-3 w-3" /> False Positive
        </span>
      );
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8 md:p-16">
      <div className="mx-auto max-w-7xl">
        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8 border-b border-slate-800 pb-8">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <ShieldAlert className="h-6 w-6 text-cyan-400" />
              <span className="text-slate-400 text-xs font-extrabold uppercase tracking-widest">
                Global Event Log
              </span>
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-white mb-2">
              Anomaly Log
            </h1>
            <p className="text-slate-400 text-sm font-medium">
              Sortable, filterable audit log of all detected metric anomalies across the workspace
            </p>
          </div>

          {/* Quick Stats Pill */}
          <div className="flex items-center gap-4 bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-md">
            <div>
              <div className="text-xs text-slate-400 font-bold uppercase">Total Listed</div>
              <div className="text-2xl font-extrabold text-white">{filteredAndSortedAnomalies.length}</div>
            </div>
            <div className="h-8 w-px bg-slate-800" />
            <div>
              <div className="text-xs text-amber-400 font-bold uppercase">Requires Action</div>
              <div className="text-2xl font-extrabold text-amber-400">
                {anomalies.filter((a) => a.status.toLowerCase() === "new").length}
              </div>
            </div>
          </div>
        </div>

        {/* Filter Tabs & Search Bar Controls */}
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4 mb-8">
          {/* Status Tabs */}
          <div className="flex items-center bg-slate-900 p-1.5 rounded-xl border border-slate-800 overflow-x-auto">
            {(
              [
                { id: "all", label: "All Statuses" },
                { id: "new", label: "New" },
                { id: "reviewed", label: "Reviewed" },
                { id: "resolved", label: "Resolved" },
                { id: "false_positive", label: "False Positive" },
              ] as { id: StatusTab; label: string }[]
            ).map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${
                  activeTab === tab.id
                    ? "bg-cyan-500 text-slate-950 shadow-md"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Search & Sort Controls */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[240px]">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
              <input
                type="text"
                placeholder="Search by metric or explanation..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-xl bg-slate-900 border border-slate-800 pl-9 pr-4 py-2 text-xs font-medium text-slate-200 placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
              />
            </div>

            {/* Sort Selector */}
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-2 rounded-xl text-xs font-medium">
              <SlidersHorizontal className="h-3.5 w-3.5 text-slate-400" />
              <span className="text-slate-400">Sort:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortOption)}
                className="bg-transparent text-slate-200 font-bold focus:outline-none cursor-pointer"
              >
                <option value="date_desc" className="bg-slate-900">Date (Newest First)</option>
                <option value="date_asc" className="bg-slate-900">Date (Oldest First)</option>
                <option value="severity_desc" className="bg-slate-900">Severity (High to Low)</option>
                <option value="severity_asc" className="bg-slate-900">Severity (Low to High)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Anomaly Table */}
        {loading ? (
          <div className="flex h-64 w-full items-center justify-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400">
            <Activity className="h-8 w-8 animate-spin text-cyan-400" />
          </div>
        ) : error ? (
          <div className="rounded-xl bg-red-950/20 border border-red-900/50 p-6 text-center text-red-300">
            {error}
          </div>
        ) : filteredAndSortedAnomalies.length === 0 ? (
          <div className="rounded-xl bg-slate-900 border border-slate-800 p-12 text-center text-slate-400">
            <HelpCircle className="mx-auto h-10 w-10 text-slate-600 mb-3" />
            <h3 className="text-base font-bold text-slate-300 mb-1">No Anomalies Found</h3>
            <p className="text-xs text-slate-500">
              No anomalies match the selected status filter or search query.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60 shadow-2xl">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-900 text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-6 py-4">Date</th>
                  <th className="px-6 py-4">Metric</th>
                  <th className="px-6 py-4">Type</th>
                  <th className="px-6 py-4">Severity</th>
                  <th className="px-6 py-4">Explanation Excerpt</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-medium">
                {filteredAndSortedAnomalies.map((anom) => (
                  <tr key={anom.id} className="hover:bg-slate-800/40 transition">
                    <td className="px-6 py-4 whitespace-nowrap font-mono text-xs text-slate-200">
                      {anom.date}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap font-bold text-white">
                      {anom.metric_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getTypeBadge(anom.anomaly_type)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getSeverityBadge(anom.severity_score)}
                    </td>
                    <td className="px-6 py-4 max-w-md truncate text-xs text-slate-400">
                      {anom.explanation_excerpt || "No explanation text generated."}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getStatusBadge(anom.status)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <Link
                        href={`/anomalies/${anom.id}`}
                        className="inline-flex items-center gap-1 text-xs font-bold text-cyan-400 hover:text-cyan-300 transition"
                      >
                        Investigate <ArrowUpRight className="h-3.5 w-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
