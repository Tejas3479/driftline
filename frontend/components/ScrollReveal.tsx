"use client";

import React, { useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

type Direction = "up" | "down" | "left" | "right" | "fade" | "scale";

interface ScrollRevealProps {
  children: React.ReactNode;
  /** Animation direction */
  direction?: Direction;
  /** Delay in seconds before animation starts */
  delay?: number;
  /** Duration of the animation in seconds */
  duration?: number;
  /** Stagger delay between child elements (if wrapping a list) */
  stagger?: number;
  /** ScrollTrigger start position */
  triggerStart?: string;
  /** Additional CSS classes */
  className?: string;
  /** Whether to animate as a single element or stagger children */
  staggerChildren?: boolean;
}

const directionMap: Record<Direction, { x?: number; y?: number; scale?: number }> = {
  up: { y: 40 },
  down: { y: -40 },
  left: { x: 40 },
  right: { x: -40 },
  fade: {},
  scale: { scale: 0.95 },
};

/**
 * ScrollReveal — GSAP ScrollTrigger-powered reveal animation.
 *
 * Wraps children and animates them into view when they enter the viewport.
 * Uses useGSAP hook for automatic cleanup. Supports directional entrance,
 * staggered child reveals, and configurable timing.
 *
 * Respects prefers-reduced-motion via the global CSS kill switch.
 */
export default function ScrollReveal({
  children,
  direction = "up",
  delay = 0,
  duration = 0.7,
  stagger = 0.08,
  triggerStart = "top 85%",
  className = "",
  staggerChildren = false,
}: ScrollRevealProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (!containerRef.current) return;

      // Check reduced motion preference
      const prefersReducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
      ).matches;
      if (prefersReducedMotion) return;

      const from = directionMap[direction];
      const targets = staggerChildren
        ? containerRef.current.children
        : containerRef.current;

      gsap.fromTo(
        targets,
        {
          opacity: 0,
          x: from.x || 0,
          y: from.y || 0,
          scale: from.scale || 1,
        },
        {
          opacity: 1,
          x: 0,
          y: 0,
          scale: 1,
          duration,
          delay,
          stagger: staggerChildren ? stagger : 0,
          ease: "power3.out",
          scrollTrigger: {
            trigger: containerRef.current,
            start: triggerStart,
            toggleActions: "play none none none",
          },
        }
      );
    },
    { scope: containerRef }
  );

  return (
    <div ref={containerRef} className={className}>
      {children}
    </div>
  );
}
