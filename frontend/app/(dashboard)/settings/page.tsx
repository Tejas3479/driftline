"use client";

import React, { useEffect, useState } from "react";
import {
  Settings,
  Activity,
  CheckCircle,
  AlertTriangle,
  Layers,
  Cpu,
  Calendar,
  Zap,
  Sliders,
  Award,
} from "lucide-react";
import ScrollReveal from "@/components/ScrollReveal";
import { useMetricContext } from "@/components/MetricContext";
import { fetchAccuracy, fetchForecast, AccuracyResponse, ForecastResult, Metric, updateMetric, deleteMetric } from "@/app/api";
import CustomSelect from "@/components/CustomSelect";
import TeamManagement from "@/components/TeamManagement";

export default function ModelHealthSettingsPage() {
  const [activeTab, setActiveTab] = useState<"model" | "team">("model");
  const { selectedMetricId, setSelectedMetricId, metrics, loading: metricsLoading, refetchMetrics } = useMetricContext();

  const [accuracy, setAccuracy] = useState<AccuracyResponse | null>(null);
  const [forecast, setForecast] = useState<ForecastResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const currentMetric = metrics.find((m) => m.id === selectedMetricId) || metrics[0];

  const [sensitivity, setSensitivity] = useState(currentMetric?.sensitivity || "medium");
  const [directionGood, setDirectionGood] = useState(currentMetric?.direction_good || "up_is_good");
  const [zScoreWeight, setZScoreWeight] = useState(currentMetric?.z_score_weight ?? 0.5);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (currentMetric) {
      setSensitivity(currentMetric.sensitivity || "medium");
      setDirectionGood(currentMetric.direction_good || "up_is_good");
      setZScoreWeight(currentMetric.z_score_weight ?? 0.5);
    }
  }, [currentMetric]);

  const handleSaveSettings = async () => {
    if (!currentMetric) return;
    try {
      setIsSaving(true);
      setSaveSuccess(false);
      setError(null);
      await updateMetric(currentMetric.id, {
        sensitivity: sensitivity as any,
        direction_good: directionGood as any,
        z_score_weight: zScoreWeight,
      });
      await refetchMetrics();
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message || "Failed to save settings");
    } finally {
      setIsSaving(false);
    }
  };

  const [isDeleting, setIsDeleting] = useState(false);
  
  const handleDeleteMetric = async () => {
    if (!currentMetric) return;
    const confirmDelete = window.confirm(
      `Are you sure you want to permanently delete metric "${currentMetric.name}"? This action cannot be undone and will delete all associated data.`
    );
    if (!confirmDelete) return;

    try {
      setIsDeleting(true);
      setError(null);
      await deleteMetric(currentMetric.id);
      // Let the context handle switching to another metric or showing the empty state
      await refetchMetrics(); 
    } catch (err: any) {
      setError(err.message || "Failed to delete metric");
      setIsDeleting(false);
    }
  };



  useEffect(() => {
    if (!currentMetric) return;

    const controller = new AbortController();
    const { signal } = controller;

    async function loadHealthData() {
      try {
        setLoading(true);
        setError(null);

        const [accData, fcData] = await Promise.all([
          fetchAccuracy(currentMetric.id, 30, "lightgbm", signal),
          fetchForecast(currentMetric.id, 30, "lightgbm", signal),
        ]);

        setAccuracy(accData);
        setForecast(fcData);
      } catch (err: any) {
        if (err.name === "AbortError") return;
        console.error("Failed to load model health data:", err);
        setError(err.message || "Failed to load model health data.");
      } finally {
        setLoading(false);
      }
    }

    loadHealthData();

    return () => {
      controller.abort();
    };
  }, [currentMetric]);

  if (metricsLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">
        <Activity className="h-8 w-8 animate-spin text-cyan-400" />
      </main>
    );
  }

  if (metrics.length === 0) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-24 text-slate-100">
        <div className="max-w-md rounded-xl border border-slate-800 bg-slate-900 p-8 text-center">
          <Settings className="mx-auto h-12 w-12 text-slate-600 mb-4" />
          <h2 className="text-xl font-bold mb-2">No Metrics Configured</h2>
          <p className="text-sm text-slate-400 mb-6">
            Upload your first business metric data to configure settings and view model health telemetry.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8 md:p-16">
      <div className="mx-auto max-w-7xl">
        {/* Page Header */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 mb-8 border-b border-slate-800 pb-8">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Settings className="h-6 w-6 text-cyan-400" />
              <span className="text-slate-400 text-xs font-extrabold uppercase tracking-widest">
                System Telemetry & Controls
              </span>
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-white mb-2">
              Settings & Administration
            </h1>
            <p className="text-slate-400 text-sm font-medium">
              Manage workspace members, model calibration telemetry, and metric parameters
            </p>
          </div>

          {/* Navigation Tabs */}
          <div className="flex bg-slate-900 border border-slate-800 rounded-xl p-1 shadow-lg shrink-0">
            <button
              onClick={() => setActiveTab("model")}
              className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${
                activeTab === "model" ? "bg-cyan-600 text-white shadow-md" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Model Health
            </button>
            <button
              onClick={() => setActiveTab("team")}
              className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${
                activeTab === "team" ? "bg-purple-600 text-white shadow-md" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Workspace Team
            </button>
          </div>
        </div>

        {activeTab === "team" ? (
          <TeamManagement />
        ) : (
          <>
            <div className="flex justify-end mb-6">
              {/* Metric Context Selector */}
              <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 p-3 rounded-xl shadow-lg">
                <Layers className="h-4 w-4 text-cyan-400" />
                <span className="text-xs font-bold text-slate-400 uppercase">Target Metric:</span>
                <CustomSelect
                  options={metrics.map((m) => ({
                    value: m.id,
                    label: m.name,
                    badge: `#${m.id}`,
                  }))}
                  value={currentMetric.id}
                  onChange={(val) => setSelectedMetricId(parseInt(String(val), 10))}
                  placeholder="Select Metric..."
                  className="min-w-[200px]"
                />
              </div>
            </div>

            {/* System Telemetry & Configuration Grid */}
        <ScrollReveal direction="up" staggerChildren stagger={0.1}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
          {/* Column 1: Model Health Telemetry Cards */}
          <div className="lg:col-span-2 space-y-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Cpu className="h-5 w-5 text-cyan-400" /> Model Accuracy & Calibration Telemetry
            </h2>

            {loading ? (
              <div className="flex h-64 items-center justify-center rounded-xl bg-slate-900 border border-slate-800">
                <Activity className="h-8 w-8 animate-spin text-cyan-400" />
              </div>
            ) : error ? (
              <div className="rounded-xl border border-red-900 bg-red-950/20 p-6 text-red-300 text-sm">
                {error}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* 12-Week MAPE Card */}
                <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl hover:border-cyan-500/30 hover:shadow-glow-cyan-sm transition-all">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-400 uppercase mb-2">
                    <span>12-Week Backtest MAPE</span>
                    <Award className="h-4 w-4 text-cyan-400" />
                  </div>
                  <div className="text-3xl font-extrabold text-white mb-2">
                    {accuracy?.mape !== null && accuracy?.mape !== undefined
                      ? `${(accuracy.mape * 100).toFixed(2)}%`
                      : "Cold-Start (N/A)"}
                  </div>
                  <p className="text-xs text-slate-500 font-medium">
                    Mean Absolute Percentage Error evaluated over 12 weekly backtest folds
                  </p>
                </div>

                {/* Interval Coverage Card */}
                <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl hover:border-cyan-500/30 hover:shadow-glow-cyan-sm transition-all">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-400 uppercase mb-2">
                    <span>80% Interval Coverage</span>
                    <Zap className="h-4 w-4 text-purple-400" />
                  </div>
                  <div className="text-3xl font-extrabold text-white mb-2">
                    {accuracy?.coverage_pct !== null && accuracy?.coverage_pct !== undefined
                      ? `${(accuracy.coverage_pct * 100).toFixed(1)}%`
                      : "Cold-Start (N/A)"}
                  </div>
                  <p className="text-xs text-slate-500 font-medium">
                    Target calibration bounds: 80% (P10-P90 prediction interval)
                  </p>
                </div>

                {/* Evaluated Folds Card */}
                <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl hover:border-cyan-500/30 hover:shadow-glow-cyan-sm transition-all">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-400 uppercase mb-2">
                    <span>Backtest Evaluated Folds</span>
                    <Layers className="h-4 w-4 text-blue-400" />
                  </div>
                  <div className="text-3xl font-extrabold text-white mb-2">
                    {accuracy?.total_evaluations ?? 0}
                  </div>
                  <p className="text-xs text-slate-500 font-medium">
                    {accuracy?.ml_evaluations ?? 0} folds evaluated with ML pipeline
                  </p>
                </div>

                {/* Forecast Baseline Date */}
                <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl hover:border-cyan-500/30 hover:shadow-glow-cyan-sm transition-all">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-400 uppercase mb-2">
                    <span>Forecast Baseline Date</span>
                    <Calendar className="h-4 w-4 text-emerald-400" />
                  </div>
                  <div className="text-2xl font-extrabold text-white mb-2 font-mono">
                    {forecast?.as_of_date ?? "N/A"}
                  </div>
                  <p className="text-xs text-slate-500 font-medium">
                    Most recent data point as-of date for recursive model inference
                  </p>
                </div>
              </div>
            )}

            {/* Model Architecture & Backend Engine */}
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl hover:border-cyan-500/30 hover:shadow-glow-cyan-sm transition-all">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-4 flex items-center gap-2">
                <Cpu className="h-4 w-4 text-purple-400" /> ML Pipeline Engine Specifications
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <span className="text-slate-500 font-bold block mb-1">MODEL BACKEND</span>
                  <span className="font-extrabold text-cyan-400 uppercase">
                    {accuracy?.model_backend ?? "lightgbm"}
                  </span>
                </div>
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <span className="text-slate-500 font-bold block mb-1">MODEL VERSION</span>
                  <span className="font-extrabold text-purple-400 font-mono">
                    {forecast?.model_version ?? "lightgbm_v1.0"}
                  </span>
                </div>
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <span className="text-slate-500 font-bold block mb-1">CONFIDENCE STATUS</span>
                  <span className="font-extrabold text-emerald-400 flex items-center gap-2">
                    {forecast?.low_confidence ? (
                      <span className="text-amber-400 flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse"></span>
                        Low Confidence (Cold)
                      </span>
                    ) : (
                      <>
                        <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                        High Confidence (ML)
                      </>
                    )}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Column 2: Metric Configuration Settings */}
          <div className="space-y-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Sliders className="h-5 w-5 text-purple-400" /> Metric Configuration
            </h2>

            <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl hover:border-cyan-500/30 hover:shadow-glow-cyan-sm transition-all space-y-6">
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
                  Metric Name & ID
                </label>
                <div className="text-lg font-extrabold text-white">
                  {currentMetric.name} <span className="text-slate-500 text-xs font-mono">(#{currentMetric.id})</span>
                </div>
              </div>

              <div className="h-px bg-slate-800" />

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
                  Anomaly Detection Sensitivity
                </label>
                <select 
                  value={sensitivity} 
                  onChange={(e) => setSensitivity(e.target.value as "low" | "medium" | "high")}
                  className="w-full bg-slate-950 border border-slate-800 text-cyan-300 font-extrabold text-xs uppercase px-3 py-2 rounded-lg focus:outline-none focus:ring-1 focus:ring-cyan-500"
                >
                  <option value="low">LOW</option>
                  <option value="medium">MEDIUM</option>
                  <option value="high">HIGH</option>
                </select>
                <p className="text-xs text-slate-500 font-medium mt-1">
                  Controls threshold scale factor for z-score & isolation forest scoring
                </p>
              </div>

              <div className="h-px bg-slate-800" />

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
                  Target Direction Preference
                </label>
                <select 
                  value={directionGood} 
                  onChange={(e) => setDirectionGood(e.target.value as "up_is_good" | "down_is_good")}
                  className="w-full bg-slate-950 border border-slate-800 text-emerald-300 font-extrabold text-xs uppercase px-3 py-2 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="up_is_good">UP IS GOOD</option>
                  <option value="down_is_good">DOWN IS GOOD</option>
                </select>
                <p className="text-xs text-slate-500 font-medium mt-1">
                  Defines whether positive shifts indicate healthy or adverse trends
                </p>
              </div>
              
              <div className="h-px bg-slate-800" />

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
                  Z-Score Weight (Ensemble Mix)
                </label>
                <div className="flex items-center gap-4">
                  <input 
                    type="range" 
                    min="0" max="1" step="0.1" 
                    value={zScoreWeight} 
                    onChange={(e) => setZScoreWeight(parseFloat(e.target.value))}
                    className="w-full accent-purple-500"
                  />
                  <span className="text-purple-300 font-extrabold text-xs bg-slate-950 px-2 py-1 rounded border border-slate-800">
                    {zScoreWeight.toFixed(1)}
                  </span>
                </div>
                <p className="text-xs text-slate-500 font-medium mt-1">
                  Weight of Z-Score in final anomaly scoring (remaining weight goes to Isolation Forest)
                </p>
              </div>

              <div className="h-px bg-slate-800" />

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
                  Data Grain
                </label>
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 font-extrabold text-xs text-slate-300 uppercase">
                  {currentMetric.grain || "daily"} (Immutable)
                </div>
              </div>
              
              <div className="pt-4">
                <button 
                  onClick={handleSaveSettings}
                  disabled={isSaving}
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-cyan-600 to-purple-600 hover:from-cyan-500 hover:to-purple-500 text-white font-bold py-2.5 px-4 rounded-lg transition-all shadow-lg hover:shadow-glow-cyan-sm disabled:opacity-50"
                >
                  {isSaving ? <Activity className="h-5 w-5 animate-spin" /> : <Settings className="h-5 w-5" />}
                  {isSaving ? "Saving..." : "Save Settings"}
                </button>
                {saveSuccess && (
                  <div className="mt-2 text-center text-emerald-400 text-xs font-bold flex items-center justify-center gap-1">
                    <CheckCircle className="h-4 w-4" /> Settings updated successfully
                  </div>
                )}
              </div>
              
              <div className="pt-6 mt-6 border-t border-slate-800">
                <button 
                  onClick={handleDeleteMetric}
                  disabled={isDeleting || isSaving}
                  className="w-full flex items-center justify-center gap-2 bg-slate-900/50 border border-red-900/50 hover:bg-red-950 hover:border-red-500 hover:text-red-300 text-red-500 font-bold py-2.5 px-4 rounded-lg transition-all disabled:opacity-50 hover:shadow-[0_0_15px_rgba(239,68,68,0.2)]"
                >
                  {isDeleting ? <Activity className="h-5 w-5 animate-spin" /> : <AlertTriangle className="h-5 w-5" />}
                  {isDeleting ? "Deleting..." : "Permanently Delete Metric"}
                </button>
              </div>
            </div>
          </div>
        </div>
        </ScrollReveal>
        </>
        )}
      </div>
    </main>
  );
}
