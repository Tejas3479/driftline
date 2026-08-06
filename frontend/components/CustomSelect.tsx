"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useUISound } from "@/components/UISoundEngine";

export interface CustomSelectOption {
  value: string | number;
  label: string;
  badge?: string;
}

interface CustomSelectProps {
  options: CustomSelectOption[];
  value: string | number;
  onChange: (value: any) => void;
  placeholder?: string;
  className?: string;
  label?: string;
}

/**
 * CustomSelect — Premium glassmorphic replacement for native HTML <select>.
 *
 * Features:
 * - Glassmorphic backdrop blur & subtle gradient border
 * - Keyboard navigation (Up, Down, Enter, Escape)
 * - Animated dropdown menu with Framer Motion & CSS @starting-style
 * - Integrated UI procedural sound feedback
 * - Support for optional badges per option
 */
export default function CustomSelect({
  options,
  value,
  onChange,
  placeholder = "Select an option...",
  className = "",
  label,
}: CustomSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const { playSound } = useUISound();

  const selectedOption = options.find((opt) => String(opt.value) === String(value));

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (val: string | number) => {
    playSound("click");
    onChange(val);
    setIsOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) {
      if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
        e.preventDefault();
        setIsOpen(true);
        setFocusedIndex(
          options.findIndex((opt) => String(opt.value) === String(value)) || 0
        );
      }
      return;
    }

    if (e.key === "Escape") {
      setIsOpen(false);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusedIndex((prev) => (prev + 1) % options.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusedIndex((prev) => (prev - 1 + options.length) % options.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (focusedIndex >= 0 && focusedIndex < options.length) {
        handleSelect(options[focusedIndex].value);
      }
    }
  };

  return (
    <div ref={containerRef} className={`relative inline-block ${className}`}>
      {label && (
        <span className="block text-xs font-bold text-slate-400 mb-1.5 uppercase tracking-wider">
          {label}
        </span>
      )}

      {/* Hidden native select for accessibility and tests */}
      <select
        role="combobox"
        aria-label={label || placeholder}
        value={value}
        onChange={(e) => {
          playSound("click");
          onChange(e.target.value);
        }}
        className="sr-only"
        tabIndex={-1}
      >
        {options.map((opt) => (
          <option key={String(opt.value)} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => {
          playSound("click");
          setIsOpen(!isOpen);
        }}
        onKeyDown={handleKeyDown}
        className="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-800/80 bg-slate-900/70 px-3.5 py-2 text-xs font-semibold text-slate-200 shadow-xs transition hover:border-cyan-500/40 hover:bg-slate-900 focus:border-cyan-400 focus:outline-hidden focus:ring-2 focus:ring-cyan-500/20 glass-panel"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="truncate">
          {selectedOption ? selectedOption.label : placeholder}
        </span>
        <ChevronDown
          className={`h-3.5 w-3.5 text-slate-400 transition-transform duration-200 ${
            isOpen ? "rotate-180 text-cyan-400" : ""
          }`}
        />
      </button>

      {/* Dropdown Menu */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.98 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute left-0 z-50 mt-1.5 max-h-60 w-full min-w-[160px] overflow-auto rounded-xl border border-slate-800/90 bg-slate-950/95 p-1.5 shadow-2xl backdrop-blur-2xl glow-cyan-sm"
            role="listbox"
          >
            {options.map((option, idx) => {
              const isSelected = String(option.value) === String(value);
              const isFocused = idx === focusedIndex;

              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => handleSelect(option.value)}
                  onMouseEnter={() => {
                    setFocusedIndex(idx);
                    playSound("hover");
                  }}
                  className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs font-medium transition ${
                    isSelected
                      ? "bg-cyan-500/15 text-cyan-300 font-bold"
                      : isFocused
                      ? "bg-slate-800/60 text-slate-100"
                      : "text-slate-300 hover:bg-slate-800/40 hover:text-white"
                  }`}
                  role="option"
                  aria-selected={isSelected}
                >
                  <span className="truncate">{option.label}</span>
                  <div className="flex items-center gap-1.5 ml-2">
                    {option.badge && (
                      <span className="rounded-sm bg-slate-800/80 px-1.5 py-0.5 text-[10px] font-mono text-slate-400">
                        {option.badge}
                      </span>
                    )}
                    {isSelected && <Check className="h-3 w-3 text-cyan-400" />}
                  </div>
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
