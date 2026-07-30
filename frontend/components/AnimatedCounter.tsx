"use client";

import React, { useEffect, useRef, useState } from "react";
import { useInView, useMotionValue, useSpring, motion } from "framer-motion";

interface AnimatedCounterProps {
  /** Target value to count to */
  value: number;
  /** Number of decimal places */
  decimals?: number;
  /** Prefix string (e.g. "$", "<") */
  prefix?: string;
  /** Suffix string (e.g. "%", "x", "ms") */
  suffix?: string;
  /** Duration in seconds */
  duration?: number;
  /** CSS class for the number display */
  className?: string;
}

/**
 * AnimatedCounter — Scroll-triggered number counter.
 *
 * Uses Intersection Observer to trigger count animation
 * when the element enters the viewport. Framer Motion spring
 * physics for natural deceleration. Locale-aware number formatting.
 */
export default function AnimatedCounter({
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  duration = 1.5,
  className = "",
}: AnimatedCounterProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-50px" });
  const [displayValue, setDisplayValue] = useState("0");

  const motionValue = useMotionValue(0);
  const springValue = useSpring(motionValue, {
    stiffness: 100,
    damping: 30,
    duration: duration * 1000,
  });

  useEffect(() => {
    if (isInView) {
      motionValue.set(value);
    }
  }, [isInView, value, motionValue]);

  useEffect(() => {
    const unsubscribe = springValue.on("change", (latest) => {
      const formatted = decimals > 0
        ? latest.toFixed(decimals)
        : Math.round(latest).toLocaleString();
      setDisplayValue(formatted);
    });
    return unsubscribe;
  }, [springValue, decimals]);

  return (
    <motion.span
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: 8 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      {prefix}{displayValue}{suffix}
    </motion.span>
  );
}
