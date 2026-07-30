"use client";

import React from "react";

interface MeteorShowerProps {
  /** Number of meteor streaks to render */
  count?: number;
}

/**
 * MeteorShower — Animated diagonal shooting-star streaks.
 *
 * Pure CSS animation, zero JS runtime cost.
 * Each meteor gets randomized position, delay, speed, and height.
 * Uses the .meteor class from globals.css.
 */
export default function MeteorShower({ count = 12 }: MeteorShowerProps) {
  const meteors = React.useMemo(() => {
    return Array.from({ length: count }, (_, i) => {
      // Deterministic pseudo-random based on index
      const seed = (i * 137 + 47) % 100;
      return {
        id: i,
        left: `${(seed * 1.1) % 100}%`,
        height: `${50 + (seed % 80)}px`,
        speed: `${2 + (seed % 3)}s`,
        delay: `${(seed * 0.07) % 5}s`,
        opacity: 0.3 + (seed % 50) / 100,
      };
    });
  }, [count]);

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      {meteors.map((m) => (
        <div
          key={m.id}
          className="meteor"
          style={{
            left: m.left,
            height: m.height,
            opacity: m.opacity,
            ["--meteor-speed" as string]: m.speed,
            ["--meteor-delay" as string]: m.delay,
          }}
        />
      ))}
    </div>
  );
}
