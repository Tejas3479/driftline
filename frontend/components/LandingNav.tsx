"use client";

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Activity } from "lucide-react";
import GlowButton from "./GlowButton";

/**
 * LandingNav — Floating landing page navigation.
 *
 * Transparent at top → glassmorphic after scrolling 50px.
 * Minimal: logo + section anchors + dashboard CTA.
 */
export default function LandingNav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled
          ? "bg-surface-0/80 backdrop-blur-xl border-b border-slate-800/50 shadow-lg shadow-black/10"
          : "bg-transparent"
      }`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        {/* Logo */}
        <a href="/" className="flex items-center gap-2.5 group">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-linear-to-br from-cyan-500 to-indigo-500 shadow-glow-cyan-sm">
            <Activity className="h-4 w-4 text-white" strokeWidth={2.5} />
          </div>
          <span className="text-lg font-extrabold tracking-tight text-white group-hover:text-gradient-cyan transition-colors">
            Driftline
          </span>
        </a>

        {/* Section Links */}
        <div className="hidden items-center gap-8 md:flex">
          {[
            { label: "Features", id: "features" },
            { label: "How It Works", id: "how-it-works" },
            { label: "Performance", id: "performance" },
          ].map((link) => (
            <button
              key={link.id}
              onClick={() => scrollToSection(link.id)}
              className="text-sm font-medium text-slate-400 transition-colors hover:text-white focus-ring"
            >
              {link.label}
            </button>
          ))}
        </div>

        {/* CTA */}
        <GlowButton
          href="/dashboard"
          variant="primary"
          size="sm"
        >
          Open Dashboard →
        </GlowButton>
      </div>
    </motion.nav>
  );
}
