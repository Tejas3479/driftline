"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  BarChart2,
  TrendingUp,
  LayoutGrid,
  ShieldAlert,
  Settings,
  Layers,
  Menu,
  X,
  Sparkles,
  Plus,
} from "lucide-react";
import { useMetricContext } from "./MetricContext";
import CustomSelect from "./CustomSelect";
import DataUploadModal from "./DataUploadModal";

export default function Navbar() {
  const pathname = usePathname();
  const { selectedMetricId, setSelectedMetricId, metrics, loading } = useMetricContext();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  const isMetricDisabled = !selectedMetricId || metrics.length === 0;
  const metricId = selectedMetricId ?? 1;

  const isActive = (path: string) => {
    if (path === "/dashboard") return pathname === "/dashboard";
    if (path === "/anomalies") return pathname === "/anomalies";
    if (path === "/settings") return pathname === "/settings";
    return pathname.startsWith(path);
  };

  const navLinks = [
    {
      name: "Overview",
      href: "/dashboard",
      icon: BarChart2,
      active: isActive("/dashboard") && pathname === "/dashboard",
      disabled: false,
    },
    {
      name: "Time Series",
      href: isMetricDisabled ? "#" : `/metrics/${metricId}`,
      icon: Activity,
      active: isActive(`/metrics/${metricId}`) && !pathname.includes("/forecast") && !pathname.includes("/segments"),
      disabled: isMetricDisabled,
    },
    {
      name: "Anomaly Log",
      href: "/anomalies",
      icon: ShieldAlert,
      active: isActive("/anomalies"),
      disabled: false,
    },
    {
      name: "Forecast",
      href: isMetricDisabled ? "#" : `/metrics/${metricId}/forecast`,
      icon: TrendingUp,
      active: isActive(`/metrics/${metricId}/forecast`),
      disabled: isMetricDisabled,
      customStyle: "text-purple-400",
    },
    {
      name: "Segment Comparison",
      href: isMetricDisabled ? "#" : `/metrics/${metricId}/segments`,
      icon: LayoutGrid,
      active: isActive(`/metrics/${metricId}/segments`),
      disabled: isMetricDisabled,
      customStyle: "text-cyan-400",
    },
    {
      name: "Model Health & Settings",
      href: "/settings",
      icon: Settings,
      active: isActive("/settings"),
      disabled: false,
    },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-xl transition-all">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">
        {/* Brand Logo & Context Selector */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-cyan-500 via-teal-400 to-indigo-600 p-[1px] shadow-lg shadow-cyan-500/20 group-hover:shadow-cyan-500/40 transition-shadow">
              <div className="flex h-full w-full items-center justify-center rounded-[11px] bg-slate-950">
                <Activity className="h-5 w-5 text-cyan-400 stroke-[2.5] group-hover:scale-110 transition-transform" />
              </div>
            </div>
            <div className="flex flex-col">
              <span className="text-lg font-extrabold tracking-tight text-white flex items-center gap-1.5">
                Driftline
                <span className="inline-flex items-center rounded-full bg-cyan-950/80 px-2 py-0.5 text-[10px] font-extrabold text-cyan-300 border border-cyan-800/50">
                  <Sparkles className="h-2.5 w-2.5 mr-0.5 text-cyan-400" /> v1.0
                </span>
              </span>
            </div>
          </Link>

          {/* Metric Selector Dropdown & Add Button */}
          <div className="relative flex items-center gap-2">
            {metrics.length > 0 ? (
              <div className="flex items-center gap-2">
                <Layers className="h-3.5 w-3.5 text-cyan-400" />
                <CustomSelect
                  options={metrics.map((m) => ({
                    value: m.id,
                    label: m.name,
                    badge: `#${m.id}`,
                  }))}
                  value={selectedMetricId ?? ""}
                  onChange={(val) => setSelectedMetricId(parseInt(String(val), 10))}
                  placeholder="Select Metric..."
                  className="min-w-[170px]"
                />
              </div>
            ) : (
              <span className="text-[11px] font-semibold text-slate-400 bg-slate-900/60 border border-slate-800 px-3 py-1.5 rounded-xl flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-slate-600" />
                {loading ? "Loading metrics..." : "No metrics configured"}
              </span>
            )}
            
            <button
              onClick={() => setUploadModalOpen(true)}
              className="flex h-[38px] items-center gap-1.5 rounded-xl bg-slate-800/80 px-3 text-xs font-bold text-slate-300 transition-all hover:bg-cyan-500/20 hover:text-cyan-300 border border-slate-700/50 hover:border-cyan-500/30"
            >
              <Plus className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Add Metric</span>
            </button>
          </div>
        </div>

        {/* Desktop Navigation Links */}
        <nav className="hidden lg:flex items-center gap-1 relative">
          {navLinks.map((link) => {
            const Icon = link.icon;
            return (
              <Link
                key={link.name}
                href={link.href}
                className={`relative flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  link.disabled
                    ? "pointer-events-none opacity-40 text-slate-600"
                    : link.active
                    ? "text-white"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/50"
                }`}
              >
                {link.active && (
                  <motion.div
                    layoutId="navTabActive"
                    className="absolute inset-0 rounded-xl bg-slate-800/90 border border-slate-700/80 shadow-md"
                    transition={{ type: "spring", stiffness: 400, damping: 32 }}
                  />
                )}
                <Icon className={`relative z-10 h-3.5 w-3.5 ${link.customStyle || ""}`} />
                <span className="relative z-10">{link.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* Mobile Hamburger Toggle Button */}
        <button
          type="button"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="lg:hidden p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white focus:outline-none"
          aria-label="Toggle navigation menu"
        >
          {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile Drawer Menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="lg:hidden border-t border-slate-800 bg-slate-950/95 backdrop-blur-xl px-6 py-4 space-y-2"
          >
            {navLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Link
                  key={link.name}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-sm font-semibold transition-colors ${
                    link.disabled
                      ? "pointer-events-none opacity-40 text-slate-600"
                      : link.active
                      ? "bg-slate-800/90 text-cyan-300 border border-slate-700/80"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/50"
                  }`}
                >
                  <Icon className={`h-4 w-4 ${link.customStyle || ""}`} />
                  {link.name}
                </Link>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
      
      <DataUploadModal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        onSuccess={(metricId) => {
          setSelectedMetricId(metricId);
          window.location.reload(); // Hard reload for simplicity to pick up new metric globally
        }}
      />
    </header>
  );
}
