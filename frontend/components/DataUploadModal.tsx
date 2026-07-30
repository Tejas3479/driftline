"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  X,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronRight,
  ChevronLeft,
  Database,
  Info
} from "lucide-react";
import GlowButton from "./GlowButton";
import CustomSelect from "./CustomSelect";
import {
  createMetric,
  inspectCsvData,
  confirmCsvData,
  MetricCreateSchema,
  InspectionResponseSchema,
  DataConfirmSchema
} from "../app/api";

interface DataUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (metricId: number) => void;
}

export default function DataUploadModal({ isOpen, onClose, onSuccess }: DataUploadModalProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1 State: Metric Config
  const [metricConfig, setMetricConfig] = useState<MetricCreateSchema>({
    workspace_id: 1,
    name: "",
    unit: "",
    direction_good: "up_is_good",
    sensitivity: "medium",
    grain: "daily",
  });
  const [createdMetricId, setCreatedMetricId] = useState<number | null>(null);

  // Step 2 State: File Upload & Inspection
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [inspectionResult, setInspectionResult] = useState<InspectionResponseSchema | null>(null);

  useEffect(() => {
    if (!isOpen) {
      // Reset state when closed
      setTimeout(() => {
        setStep(1);
        setMetricConfig({
          workspace_id: 1,
          name: "",
          unit: "",
          direction_good: "up_is_good",
          sensitivity: "medium",
          grain: "daily",
        });
        setCreatedMetricId(null);
        setFile(null);
        setInspectionResult(null);
        setError(null);
      }, 300);
    }
  }, [isOpen]);

  const handleCreateMetric = async () => {
    if (!metricConfig.name) {
      setError("Metric name is required");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const metric = await createMetric(metricConfig);
      setCreatedMetricId(metric.id);
      setStep(2);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleFileDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelection = async (selectedFile: File) => {
    if (!createdMetricId) return;
    if (!selectedFile.name.endsWith('.csv')) {
      setError("Only CSV files are supported");
      return;
    }
    
    setFile(selectedFile);
    setLoading(true);
    setError(null);
    try {
      const result = await inspectCsvData(createdMetricId, selectedFile);
      setInspectionResult(result);
      setStep(3);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setFile(null);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!createdMetricId || !inspectionResult) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const payload: DataConfirmSchema = {
        date_col: inspectionResult.inferred_mapping.date_col,
        value_col: inspectionResult.inferred_mapping.value_col,
        dimension_cols: inspectionResult.inferred_mapping.dimension_cols,
        rows: inspectionResult.rows,
        replace: false
      };
      
      await confirmCsvData(createdMetricId, payload);
      onSuccess(createdMetricId);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
          onClick={onClose}
        />
        
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/50 px-6 py-4">
            <h2 className="flex items-center gap-2 text-lg font-bold text-white">
              <Database className="h-5 w-5 text-cyan-400" />
              Upload New Metric
            </h2>
            <button
              onClick={onClose}
              className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Stepper */}
          <div className="flex items-center justify-between px-8 py-6">
            {[1, 2, 3].map((s) => (
              <div key={s} className="flex items-center">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${
                    step >= s
                      ? "bg-cyan-500 text-white shadow-glow-cyan-sm"
                      : "bg-slate-800 text-slate-500"
                  }`}
                >
                  {s}
                </div>
                <span
                  className={`ml-3 text-sm font-semibold ${
                    step >= s ? "text-slate-200" : "text-slate-600"
                  }`}
                >
                  {s === 1 ? "Configuration" : s === 2 ? "Upload CSV" : "Review"}
                </span>
                {s < 3 && (
                  <div className="mx-4 h-[1px] w-12 bg-slate-800" />
                )}
              </div>
            ))}
          </div>

          {/* Content */}
          <div className="px-8 pb-8">
            {error && (
              <div className="mb-6 flex items-start gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-rose-400">
                <AlertCircle className="h-5 w-5 shrink-0" />
                <p className="text-sm">{error}</p>
              </div>
            )}

            {step === 1 && (
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-5"
              >
                <div>
                  <label className="mb-1.5 block text-sm font-semibold text-slate-300">
                    Metric Name <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={metricConfig.name}
                    onChange={(e) => setMetricConfig({ ...metricConfig, name: e.target.value })}
                    className="w-full rounded-xl border border-slate-700 bg-slate-800/50 px-4 py-2.5 text-slate-200 placeholder-slate-500 transition-colors focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                    placeholder="e.g. Daily Active Users"
                  />
                </div>
                
                <div>
                  <label className="mb-1.5 block text-sm font-semibold text-slate-300">
                    Unit (Optional)
                  </label>
                  <input
                    type="text"
                    value={metricConfig.unit || ""}
                    onChange={(e) => setMetricConfig({ ...metricConfig, unit: e.target.value })}
                    className="w-full rounded-xl border border-slate-700 bg-slate-800/50 px-4 py-2.5 text-slate-200 placeholder-slate-500 transition-colors focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                    placeholder="e.g. USD, Users, %"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="mb-1.5 block text-sm font-semibold text-slate-300">
                      Direction Good
                    </label>
                    <CustomSelect
                      options={[
                        { value: "up_is_good", label: "Up is Good" },
                        { value: "down_is_good", label: "Down is Good" }
                      ]}
                      value={metricConfig.direction_good}
                      onChange={(val) => setMetricConfig({ ...metricConfig, direction_good: val as any })}
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-semibold text-slate-300">
                      Sensitivity
                    </label>
                    <CustomSelect
                      options={[
                        { value: "low", label: "Low" },
                        { value: "medium", label: "Medium" },
                        { value: "high", label: "High" }
                      ]}
                      value={metricConfig.sensitivity}
                      onChange={(val) => setMetricConfig({ ...metricConfig, sensitivity: val as any })}
                    />
                  </div>
                </div>

                <div className="mt-8 flex justify-end">
                  <GlowButton
                    onClick={handleCreateMetric}
                    disabled={loading || !metricConfig.name}
                    className="w-full sm:w-auto"
                  >
                    {loading ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <>Continue <ChevronRight className="h-4 w-4" /></>
                    )}
                  </GlowButton>
                </div>
              </motion.div>
            )}

            {step === 2 && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-6"
              >
                <div
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={handleFileDrop}
                  className={`relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 transition-all ${
                    isDragging
                      ? "border-cyan-500 bg-cyan-500/10"
                      : "border-slate-700 bg-slate-800/30 hover:border-slate-500 hover:bg-slate-800/50"
                  }`}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    className="hidden"
                    accept=".csv"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        handleFileSelection(e.target.files[0]);
                      }
                    }}
                  />
                  
                  {loading ? (
                    <div className="flex flex-col items-center text-cyan-400">
                      <Loader2 className="mb-4 h-10 w-10 animate-spin" />
                      <p className="font-semibold">Inspecting CSV data...</p>
                    </div>
                  ) : (
                    <>
                      <div className="mb-4 rounded-full bg-slate-800 p-4">
                        <Upload className="h-8 w-8 text-cyan-400" />
                      </div>
                      <p className="mb-1 text-base font-semibold text-slate-200">
                        Click to upload or drag and drop
                      </p>
                      <p className="text-sm text-slate-500">
                        CSV files only. Must contain a date column and a numeric value column.
                      </p>
                    </>
                  )}
                </div>
              </motion.div>
            )}

            {step === 3 && inspectionResult && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-6"
              >
                <div className={`rounded-xl border p-5 ${
                  inspectionResult.validation_report.is_valid 
                    ? "border-emerald-500/30 bg-emerald-500/10"
                    : "border-rose-500/30 bg-rose-500/10"
                }`}>
                  <div className="flex items-center gap-3 mb-4">
                    {inspectionResult.validation_report.is_valid ? (
                      <CheckCircle2 className="h-6 w-6 text-emerald-400" />
                    ) : (
                      <AlertCircle className="h-6 w-6 text-rose-400" />
                    )}
                    <h3 className="text-lg font-bold text-white">
                      {inspectionResult.validation_report.is_valid ? "Validation Successful" : "Validation Failed"}
                    </h3>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4 text-sm mb-6">
                    <div className="rounded-lg bg-slate-900/50 p-3">
                      <p className="text-slate-400 mb-1">Total Rows</p>
                      <p className="font-bold text-slate-200">{inspectionResult.validation_report.total_rows.toLocaleString()}</p>
                    </div>
                    <div className="rounded-lg bg-slate-900/50 p-3">
                      <p className="text-slate-400 mb-1">Inferred Columns</p>
                      <div className="flex flex-col gap-1">
                        <span className="text-cyan-300 truncate">Date: {inspectionResult.inferred_mapping.date_col}</span>
                        <span className="text-emerald-300 truncate">Value: {inspectionResult.inferred_mapping.value_col}</span>
                        {inspectionResult.inferred_mapping.dimension_cols.length > 0 && (
                          <span className="text-purple-300 truncate">
                            Dims: {inspectionResult.inferred_mapping.dimension_cols.join(', ')}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {!inspectionResult.validation_report.is_valid && (
                    <div className="space-y-3">
                      <p className="font-semibold text-rose-300">Errors found:</p>
                      <div className="max-h-40 overflow-y-auto space-y-2 rounded-lg bg-slate-900/80 p-3 text-xs text-rose-200">
                        {inspectionResult.validation_report.errors.map((e, i) => (
                          <div key={i} className="flex gap-2">
                            <span className="font-mono text-slate-500">Row {e.row_number}:</span>
                            <span>{e.issue} (Column: {e.column})</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {inspectionResult.validation_report.date_gaps.length > 0 && (
                    <div className="mt-4 flex items-start gap-2 rounded-lg bg-amber-500/10 p-3 text-sm text-amber-200">
                      <Info className="h-4 w-4 shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold mb-1">Missing Dates Detected</p>
                        <p className="text-xs opacity-80">
                          {inspectionResult.validation_report.date_gaps.slice(0, 3).join(', ')}
                          {inspectionResult.validation_report.date_gaps.length > 3 ? ` ...and ${inspectionResult.validation_report.date_gaps.length - 3} more` : ''}
                        </p>
                        <p className="text-xs mt-1 italic">Driftline will auto-interpolate these missing periods.</p>
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-8 flex justify-between">
                  <button
                    onClick={() => {
                      setStep(2);
                      setFile(null);
                      setInspectionResult(null);
                    }}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-slate-400 transition-colors hover:text-white"
                  >
                    <ChevronLeft className="h-4 w-4" /> Try another file
                  </button>
                  
                  <GlowButton
                    onClick={handleConfirm}
                    disabled={loading || !inspectionResult.validation_report.is_valid}
                    variant={inspectionResult.validation_report.is_valid ? "primary" : "secondary"}
                  >
                    {loading ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      "Confirm & Ingest"
                    )}
                  </GlowButton>
                </div>
              </motion.div>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
