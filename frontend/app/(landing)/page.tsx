"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  Activity,
  ShieldAlert,
  BarChart2,
  TrendingUp,
  GitBranch,
  Layers,
  FileText,
  ArrowRight,
  CheckCircle2,
  Zap,
  Target,
  Clock,
} from "lucide-react";
import LandingNav from "@/components/LandingNav";
import GlowButton from "@/components/GlowButton";
import TypewriterText from "@/components/TypewriterText";
import AnimatedCounter from "@/components/AnimatedCounter";
import MeteorShower from "@/components/MeteorShower";
import ScrollReveal from "@/components/ScrollReveal";
import TextReveal from "@/components/TextReveal";
import AtroposCard from "@/components/AtroposCard";

/* ══════════════════════════════════════════════
   HELPER: Staggered fade-up animation variants
   ══════════════════════════════════════════════ */
const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.6, ease: [0.16, 1, 0.3, 1] },
  }),
};

/* ══════════════════════════════════════════════
   BENTO FEATURE DATA
   ══════════════════════════════════════════════ */
const features = [
  {
    icon: ShieldAlert,
    title: "Hybrid Anomaly Detection",
    desc: "Four anomaly types — spike, dip, level-shift, volatility change — detected with IsolationForest + robust z-scores.",
    gradient: "from-rose-500/20 to-orange-500/20",
    iconColor: "text-rose-400",
    large: true,
  },
  {
    icon: BarChart2,
    title: "Root-Cause Drivers",
    desc: "Waterfall bridge attribution across segments. CatBoost structural importance reveals which dimensions explain the anomaly.",
    gradient: "from-cyan-500/20 to-blue-500/20",
    iconColor: "text-cyan-400",
    large: true,
  },
  {
    icon: TrendingUp,
    title: "Quantile Forecasting",
    desc: "p10/p50/p90 prediction bands via LightGBM & XGBoost with walk-forward backtesting.",
    gradient: "from-violet-500/20 to-purple-500/20",
    iconColor: "text-violet-400",
    large: false,
  },
  {
    icon: GitBranch,
    title: "Adaptive Feedback",
    desc: "Mark false positives — future detection weights decay. Your signal gets cleaner over time.",
    gradient: "from-emerald-500/20 to-teal-500/20",
    iconColor: "text-emerald-400",
    large: false,
  },
  {
    icon: Layers,
    title: "Segment Decomposition",
    desc: "Up to 3 categorical dimensions sliced into small-multiple visual comparisons.",
    gradient: "from-sky-500/20 to-indigo-500/20",
    iconColor: "text-sky-400",
    large: false,
  },
  {
    icon: FileText,
    title: "Automated Digests",
    desc: "PDF reports and email alerts on schedule. Never miss a metric movement again.",
    gradient: "from-amber-500/20 to-yellow-500/20",
    iconColor: "text-amber-400",
    large: false,
  },
];

/* ══════════════════════════════════════════════
   HOW IT WORKS STEPS
   ══════════════════════════════════════════════ */
const steps = [
  {
    step: "01",
    title: "Connect Your Data",
    desc: "Upload CSV or connect a database. Driftline ingests your time-series metric with up to 3 categorical dimensions.",
    icon: Activity,
    color: "text-cyan-400",
  },
  {
    step: "02",
    title: "Detect & Decompose",
    desc: "The pipeline decomposes your metric into trend, seasonal, and residual components — then scans for anomalies in real-time.",
    icon: Target,
    color: "text-indigo-400",
  },
  {
    step: "03",
    title: "Get Actionable Insights",
    desc: "See exactly which segments drove the anomaly, with quantile forecasts showing where the metric is heading.",
    icon: Zap,
    color: "text-violet-400",
  },
];

/* ══════════════════════════════════════════════
   MAIN LANDING PAGE
   ══════════════════════════════════════════════ */
export default function LandingPage() {
  return (
    <main className="relative overflow-hidden">
      <LandingNav />

      {/* ═══════ SECTION 1: HERO ═══════ */}
      <section className="relative flex min-h-screen flex-col items-center justify-center px-6 pt-24 pb-20">
        {/* Animated mesh background */}
        <div className="bg-mesh-animated absolute inset-0 z-0" />

        {/* Floating ambient orbs */}
        <div
          className="absolute top-[15%] left-[10%] h-72 w-72 rounded-full opacity-30 blur-[100px] animate-float"
          style={{ background: "radial-gradient(circle, rgba(6, 182, 212, 0.4), transparent)" }}
        />
        <div
          className="absolute top-[60%] right-[15%] h-96 w-96 rounded-full opacity-20 blur-[120px] animate-float-slow"
          style={{ background: "radial-gradient(circle, rgba(99, 102, 241, 0.35), transparent)" }}
        />
        <div
          className="absolute top-[30%] right-[30%] h-48 w-48 rounded-full opacity-25 blur-[80px] animate-float-delayed"
          style={{ background: "radial-gradient(circle, rgba(139, 92, 246, 0.3), transparent)" }}
        />

        {/* Meteor shower */}
        <MeteorShower count={10} />

        {/* Particle field */}
        <div className="particles-field" />

        {/* Hero content */}
        <div className="relative z-10 mx-auto max-w-4xl text-center">
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="mb-8 inline-flex items-center gap-2 rounded-full border border-slate-700/60 bg-slate-900/60 px-4 py-1.5 text-xs font-semibold text-slate-300 backdrop-blur-sm"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Open Source · Self-Hosted · Privacy-First
          </motion.div>

          {/* Headline */}
          <div className="mb-6">
            <TextReveal
              as="h1"
              type="words"
              triggerOnScroll={false}
              className="text-5xl font-extrabold leading-tight tracking-tight text-white sm:text-6xl md:text-7xl"
            >
              Stop Guessing Why Your
            </TextReveal>
            <div className="mt-2 text-5xl font-extrabold leading-tight tracking-tight sm:text-6xl md:text-7xl">
              <span className="text-gradient-cyan">
                <TypewriterText
                  words={[
                    "Revenue Dropped",
                    "Churn Spiked",
                    "Conversions Fell",
                    "Costs Surged",
                  ]}
                  typingSpeed={70}
                  deletingSpeed={40}
                  pauseDuration={2500}
                />
              </span>
            </div>
          </div>

          {/* Subheadline */}
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.6, ease: "easeOut" }}
            className="mx-auto mb-10 max-w-2xl text-lg leading-relaxed text-slate-400 sm:text-xl"
          >
            Automated anomaly detection, root-cause driver attribution, and
            quantile forecasting — in one lightweight engine.
          </motion.p>

          {/* CTA Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8, duration: 0.5 }}
            className="flex flex-wrap items-center justify-center gap-4"
          >
            <GlowButton href="/dashboard" variant="primary" size="lg" magnetic>
              Get Started <ArrowRight className="h-4 w-4 ml-1" />
            </GlowButton>
            <GlowButton href="#how-it-works" variant="secondary" size="lg">
              See How It Works
            </GlowButton>
          </motion.div>

          {/* Trust metrics */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.1, duration: 0.6 }}
            className="mt-14 flex flex-wrap items-center justify-center gap-6 sm:gap-8"
          >
            {[
              { icon: CheckCircle2, label: "Recall", value: 100, suffix: "%" },
              { icon: Target, label: "MAPE", value: 2.64, suffix: "%", decimals: 2 },
              { icon: Clock, label: "Detection", value: 1, prefix: "<", suffix: "s" },
              { icon: Layers, label: "Anomaly Types", value: 4, suffix: "" },
            ].map((stat, i) => (
              <div
                key={stat.label}
                className="flex items-center gap-2 rounded-full border border-slate-800/60 bg-slate-900/40 px-4 py-2 backdrop-blur-sm"
              >
                <stat.icon className="h-3.5 w-3.5 text-cyan-400" />
                <AnimatedCounter
                  value={stat.value}
                  decimals={stat.decimals || 0}
                  prefix={stat.prefix}
                  suffix={stat.suffix}
                  className="text-sm font-bold text-white"
                />
                <span className="text-xs text-slate-500">{stat.label}</span>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══════ SECTION 2: TECH TRUST STRIP ═══════ */}
      <section className="relative border-y border-slate-800/40 bg-surface-0/50 py-10 backdrop-blur-sm">
        <ScrollReveal direction="fade">
          <p className="mb-6 text-center text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
            Powered by
          </p>
          <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-4 px-6 opacity-60">
            {["Python", "FastAPI", "scikit-learn", "LightGBM", "XGBoost", "CatBoost", "Plotly", "Next.js"].map(
              (tech) => (
                <span
                  key={tech}
                  className="text-sm font-semibold text-slate-400 transition-colors hover:text-white"
                >
                  {tech}
                </span>
              )
            )}
          </div>
        </ScrollReveal>
      </section>

      {/* ═══════ SECTION 3: FEATURE BENTO GRID ═══════ */}
      <section id="features" className="relative py-24 px-6">
        <div className="mx-auto max-w-6xl">
          <ScrollReveal direction="up">
            <div className="mb-16 text-center">
              <p className="mb-3 text-sm font-bold uppercase tracking-[0.15em] text-cyan-400">
                Capabilities
              </p>
              <h2 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
                Everything You Need to
                <span className="text-gradient-cyan"> Understand Your Metrics</span>
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-400">
                Six integrated modules that work together — from raw data ingestion to actionable anomaly explanations.
              </p>
            </div>
          </ScrollReveal>

          {/* Bento grid */}
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((feat, i) => {
              const Icon = feat.icon;
              return (
                <ScrollReveal
                  key={feat.title}
                  direction="up"
                  delay={i * 0.08}
                  className={feat.large ? "sm:col-span-2" : ""}
                >
                  <AtroposCard intensity="subtle" className="h-full">
                    <div
                      className={`group relative overflow-hidden rounded-2xl border border-slate-800/60 bg-linear-to-br ${feat.gradient} p-6 backdrop-blur-sm transition-all duration-300 hover:border-slate-700/80 hover:shadow-lg hover:shadow-cyan-500/5 h-full`}
                    >
                      {/* Background glow on hover */}
                      <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-linear-to-br from-cyan-500/10 to-transparent opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-100" />

                      <div className="relative z-10">
                        <div className={`mb-4 inline-flex items-center justify-center rounded-xl bg-slate-900/60 p-3 ${feat.iconColor}`}>
                          <Icon className="h-5 w-5" />
                        </div>
                        <h3 className="mb-2 text-lg font-bold text-white">
                          {feat.title}
                        </h3>
                        <p className="text-sm leading-relaxed text-slate-400">
                          {feat.desc}
                        </p>
                      </div>
                    </div>
                  </AtroposCard>
                </ScrollReveal>
              );
            })}
          </div>
        </div>
      </section>

      {/* ═══════ SECTION 4: INTERACTIVE DEMO (SCROLL-PINNED) ═══════ */}
      <section className="relative py-28 px-6 overflow-hidden">
        <div className="mx-auto max-w-6xl">
          <ScrollReveal direction="up">
            <div className="mb-16 text-center">
              <p className="mb-3 text-sm font-bold uppercase tracking-[0.15em] text-cyan-400">
                Interactive Walkthrough
              </p>
              <h2 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
                See Driftline in <span className="text-gradient-cyan">Action</span>
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-400">
                A live peek into the real-time detection, driver isolation, and forecasting engine.
              </p>
            </div>
          </ScrollReveal>

          {/* Glassmorphic Browser Frame with Animated Gradient Border */}
          <ScrollReveal direction="up" delay={0.1}>
            <div className="relative rounded-3xl p-px animated-border overflow-hidden shadow-2xl">
              <div className="rounded-[23px] bg-slate-950/90 backdrop-blur-2xl p-6 md:p-10 border border-slate-800/80">
                {/* Browser Top Bar */}
                <div className="flex items-center justify-between border-b border-slate-800/80 pb-5 mb-8">
                  <div className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-full bg-red-500/80" />
                    <span className="h-3 w-3 rounded-full bg-amber-500/80" />
                    <span className="h-3 w-3 rounded-full bg-emerald-500/80" />
                  </div>
                  <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-800 px-4 py-1.5 rounded-full text-xs font-mono text-cyan-400">
                    <ShieldAlert className="h-3.5 w-3.5 text-cyan-400 animate-pulse" />
                    app.driftline.io/intelligence
                  </div>
                  <div className="h-2 w-12 rounded-full bg-slate-800" />
                </div>

                {/* 3 Walkthrough Scenes Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* Scene 1: Anomaly Detected */}
                  <AtroposCard intensity="subtle" className="h-full">
                    <div className="rounded-2xl border border-amber-500/30 bg-slate-900/60 p-6 h-full flex flex-col justify-between group hover:border-amber-500/60 transition">
                      <div>
                        <div className="flex items-center justify-between mb-4">
                          <span className="rounded-full bg-amber-950/80 px-2.5 py-0.5 text-[10px] font-extrabold uppercase text-amber-300 border border-amber-800/50">
                            Scene 01
                          </span>
                          <span className="flex h-2 w-2 rounded-full bg-amber-400 animate-ping" />
                        </div>
                        <h4 className="text-lg font-bold text-white mb-2">Anomaly Detected</h4>
                        <p className="text-xs text-slate-400 leading-relaxed mb-6">
                          IsolationForest flags a 4.2σ divergence on Revenue metric at 04:00 UTC.
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-950 p-4 border border-slate-800/80">
                        <div className="flex items-center justify-between text-xs mb-2">
                          <span className="text-slate-400 font-mono">z-score:</span>
                          <span className="text-amber-400 font-mono font-bold">-4.21 σ</span>
                        </div>
                        <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                          <div className="h-full bg-linear-to-r from-amber-500 to-red-500 w-4/5" />
                        </div>
                      </div>
                    </div>
                  </AtroposCard>

                  {/* Scene 2: Drivers Identified */}
                  <AtroposCard intensity="subtle" className="h-full">
                    <div className="rounded-2xl border border-cyan-500/30 bg-slate-900/60 p-6 h-full flex flex-col justify-between group hover:border-cyan-500/60 transition">
                      <div>
                        <div className="flex items-center justify-between mb-4">
                          <span className="rounded-full bg-cyan-950/80 px-2.5 py-0.5 text-[10px] font-extrabold uppercase text-cyan-300 border border-cyan-800/50">
                            Scene 02
                          </span>
                          <Zap className="h-4 w-4 text-cyan-400" />
                        </div>
                        <h4 className="text-lg font-bold text-white mb-2">Drivers Identified</h4>
                        <p className="text-xs text-slate-400 leading-relaxed mb-6">
                          CatBoost isolates primary contributor: Organic Search UK segment drop.
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-950 p-4 border border-slate-800/80 space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-300 font-mono">Organic Search</span>
                          <span className="text-cyan-400 font-bold">78.4%</span>
                        </div>
                        <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                          <div className="h-full bg-cyan-400 w-3/4" />
                        </div>
                      </div>
                    </div>
                  </AtroposCard>

                  {/* Scene 3: Forecast Adjusted */}
                  <AtroposCard intensity="subtle" className="h-full">
                    <div className="rounded-2xl border border-indigo-500/30 bg-slate-900/60 p-6 h-full flex flex-col justify-between group hover:border-indigo-500/60 transition">
                      <div>
                        <div className="flex items-center justify-between mb-4">
                          <span className="rounded-full bg-indigo-950/80 px-2.5 py-0.5 text-[10px] font-extrabold uppercase text-indigo-300 border border-indigo-800/50">
                            Scene 03
                          </span>
                          <TrendingUp className="h-4 w-4 text-indigo-400" />
                        </div>
                        <h4 className="text-lg font-bold text-white mb-2">Forecast Adjusted</h4>
                        <p className="text-xs text-slate-400 leading-relaxed mb-6">
                          Quantile LightGBM recalibrates P10–P90 bands automatically for next 7 days.
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-950 p-4 border border-slate-800/80 flex items-center justify-between">
                        <span className="text-xs text-slate-400">P50 MAPE</span>
                        <span className="text-xs font-mono font-bold text-emerald-400">1.84% (Optimal)</span>
                      </div>
                    </div>
                  </AtroposCard>
                </div>
              </div>
            </div>
          </ScrollReveal>
        </div>
      </section>

      {/* ═══════ SECTION 5: HOW IT WORKS ═══════ */}
      <section id="how-it-works" className="relative py-24 px-6">
        <div className="mx-auto max-w-4xl">
          <ScrollReveal direction="up">
            <div className="mb-16 text-center">
              <p className="mb-3 text-sm font-bold uppercase tracking-[0.15em] text-indigo-400">
                Workflow
              </p>
              <h2 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
                Three Steps to <span className="text-gradient-violet">Clarity</span>
              </h2>
            </div>
          </ScrollReveal>

          <div className="relative">
            {/* Connecting gradient line */}
            <div className="absolute left-8 top-0 bottom-0 w-px bg-linear-to-b from-cyan-500/50 via-indigo-500/50 to-violet-500/50 hidden sm:block" />

            <div className="space-y-12">
              {steps.map((step, i) => {
                const Icon = step.icon;
                return (
                  <ScrollReveal
                    key={step.step}
                    direction="left"
                    delay={i * 0.15}
                  >
                    <div className="flex gap-6 sm:gap-8">
                      {/* Step indicator */}
                      <div className="relative shrink-0">
                        <div
                          className={`flex h-16 w-16 items-center justify-center rounded-2xl border border-slate-800/60 bg-slate-900/80 backdrop-blur-sm ${step.color}`}
                        >
                          <Icon className="h-6 w-6" />
                        </div>
                      </div>

                      {/* Content */}
                      <div className="pt-2">
                        <p className={`mb-1 text-xs font-bold uppercase tracking-[0.15em] ${step.color}`}>
                          Step {step.step}
                        </p>
                        <h3 className="mb-2 text-xl font-bold text-white">
                          {step.title}
                        </h3>
                        <p className="text-sm leading-relaxed text-slate-400 max-w-lg">
                          {step.desc}
                        </p>
                      </div>
                    </div>
                  </ScrollReveal>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* ═══════ SECTION 5: PERFORMANCE STATS ═══════ */}
      <section id="performance" className="relative py-24 px-6 border-y border-slate-800/40">
        <MeteorShower count={8} />
        <div className="relative z-10 mx-auto max-w-5xl">
          <ScrollReveal direction="up">
            <div className="mb-14 text-center">
              <p className="mb-3 text-sm font-bold uppercase tracking-[0.15em] text-emerald-400">
                Proven Accuracy
              </p>
              <h2 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
                Numbers That <span className="text-gradient-cyan">Speak</span>
              </h2>
            </div>
          </ScrollReveal>

          <ScrollReveal direction="up" staggerChildren stagger={0.12}>
            <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
              {[
                { value: 100, suffix: "%", label: "Anomaly Recall", desc: "Every anomaly detected" },
                { value: 2.64, suffix: "%", decimals: 2, label: "Forecast MAPE", desc: "Industry-leading accuracy" },
                { value: 12, suffix: "-wk", label: "Backtest Window", desc: "Walk-forward validated" },
                { value: 4, suffix: "", label: "Anomaly Types", desc: "Spike · Dip · Shift · Vol" },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="group rounded-2xl border border-slate-800/60 bg-slate-900/30 p-6 text-center backdrop-blur-sm transition-all duration-300 hover:border-cyan-500/30 hover:shadow-glow-cyan-sm"
                >
                  <AnimatedCounter
                    value={stat.value}
                    decimals={stat.decimals || 0}
                    suffix={stat.suffix}
                    className="text-4xl font-extrabold text-white sm:text-5xl"
                    duration={2}
                  />
                  <p className="mt-3 text-sm font-bold text-slate-300">
                    {stat.label}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {stat.desc}
                  </p>
                </div>
              ))}
            </div>
          </ScrollReveal>
        </div>
      </section>

      {/* ═══════ SECTION 6: OPEN SOURCE CTA ═══════ */}
      <section className="relative py-32 px-6">
        {/* Ambient glow */}
        <div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-96 w-96 rounded-full opacity-20 blur-[120px]"
          style={{ background: "radial-gradient(circle, rgba(34, 211, 238, 0.3), rgba(99, 102, 241, 0.2), transparent)" }}
        />

        <div className="relative z-10 mx-auto max-w-3xl text-center">
          <ScrollReveal direction="up">
            <h2 className="mb-6 text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
              Open Source.{" "}
              <span className="text-gradient-cyan">Self-Host in 5 Minutes.</span>
            </h2>
            <p className="mb-10 text-lg text-slate-400">
              Driftline is fully open source. Run it on your infrastructure,
              keep your data private, and contribute back to the community.
            </p>
          </ScrollReveal>

          <ScrollReveal direction="up" delay={0.2}>
            <div className="flex flex-wrap items-center justify-center gap-4">
              <GlowButton href="/dashboard" variant="primary" size="lg" magnetic>
                Open Dashboard <ArrowRight className="h-4 w-4 ml-1" />
              </GlowButton>
            </div>
          </ScrollReveal>
        </div>
      </section>

      {/* ═══════ SECTION 7: FOOTER ═══════ */}
      <footer className="border-t border-slate-800/40 bg-surface-0/80 py-12 px-6 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 sm:flex-row">
          {/* Logo */}
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-linear-to-br from-cyan-500 to-indigo-500">
              <Activity className="h-3.5 w-3.5 text-white" strokeWidth={2.5} />
            </div>
            <span className="text-sm font-bold text-slate-300">
              Driftline
            </span>
          </div>

          {/* Links */}
          <div className="flex items-center gap-6 text-xs text-slate-500">
            <a href="/dashboard" className="hover:text-white transition-colors">
              Dashboard
            </a>
            <a href="#features" className="hover:text-white transition-colors">
              Features
            </a>
          </div>

          {/* Credit */}
          <p className="text-xs text-slate-600">
            Built with ❤️ and Python
          </p>
        </div>
      </footer>
    </main>
  );
}
