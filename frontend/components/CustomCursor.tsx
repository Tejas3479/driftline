"use client";

import React, { useEffect, useRef, useState } from "react";

/**
 * CustomCursor — Custom dot + ring cursor with magnetic snap.
 *
 * Renders a fixed dot cursor and a ring follower that tracks
 * the mouse with spring lag. On hover over interactive elements
 * (buttons, links, cards), the ring expands.
 *
 * Hidden on touch devices and when prefers-reduced-motion is set.
 * All cursor elements have pointer-events: none.
 */
export default function CustomCursor() {
  const dotRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);
  const [isHovering, setIsHovering] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const mousePos = useRef({ x: 0, y: 0 });
  const ringPos = useRef({ x: 0, y: 0 });
  const rafRef = useRef<number>();

  useEffect(() => {
    // Disable on touch devices or reduced motion
    const isTouchDevice =
      "ontouchstart" in window || navigator.maxTouchPoints > 0;
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (isTouchDevice || prefersReducedMotion) return;

    const handleMouseMove = (e: MouseEvent) => {
      mousePos.current = { x: e.clientX, y: e.clientY };
      if (!isVisible) setIsVisible(true);

      // Dot follows instantly
      if (dotRef.current) {
        dotRef.current.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
      }
    };

    const handleMouseOver = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const isInteractive =
        target.closest("a, button, [role='button'], input, select, textarea, .cursor-pointer, .glass-card");
      setIsHovering(!!isInteractive);
    };

    const handleMouseLeave = () => {
      setIsVisible(false);
    };

    const handleMouseEnter = () => {
      setIsVisible(true);
    };

    // Ring follows with spring lag
    const animate = () => {
      ringPos.current.x += (mousePos.current.x - ringPos.current.x) * 0.15;
      ringPos.current.y += (mousePos.current.y - ringPos.current.y) * 0.15;
      if (ringRef.current) {
        ringRef.current.style.transform = `translate(${ringPos.current.x}px, ${ringPos.current.y}px)`;
      }
      rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseover", handleMouseOver);
    document.addEventListener("mouseleave", handleMouseLeave);
    document.addEventListener("mouseenter", handleMouseEnter);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseover", handleMouseOver);
      document.removeEventListener("mouseleave", handleMouseLeave);
      document.removeEventListener("mouseenter", handleMouseEnter);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [isVisible]);

  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Don't render anything until client-side hydration is complete
  if (!isMounted) return null;

  return (
    <>
      {/* Hide native cursor when custom cursor is active */}
      <style jsx global>{`
        @media (hover: hover) and (pointer: fine) {
          * { cursor: none !important; }
        }
      `}</style>

      {/* Dot — follows mouse precisely */}
      <div
        ref={dotRef}
        aria-hidden="true"
        className="pointer-events-none fixed left-0 top-0 z-10000 -translate-x-1/2 -translate-y-1/2 transition-opacity duration-200"
        style={{
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          backgroundColor: isHovering ? "var(--accent-cyan)" : "#f9fafb",
          opacity: isVisible ? 1 : 0,
        }}
      />

      {/* Ring — follows with spring lag */}
      <div
        ref={ringRef}
        aria-hidden="true"
        className="pointer-events-none fixed left-0 top-0 z-10000 -translate-x-1/2 -translate-y-1/2 transition-[width,height,border-color,opacity] duration-300 ease-out"
        style={{
          width: isHovering ? "48px" : "32px",
          height: isHovering ? "48px" : "32px",
          borderRadius: "50%",
          border: `1.5px solid ${isHovering ? "var(--accent-cyan)" : "rgba(249, 250, 251, 0.4)"}`,
          opacity: isVisible ? 1 : 0,
        }}
      />
    </>
  );
}
