"use client";

import React from "react";
import Atropos from "atropos/react";
import "atropos/css";

type Intensity = "subtle" | "medium" | "dramatic";

interface AtroposCardProps {
  children: React.ReactNode;
  /** Tilt intensity preset */
  intensity?: Intensity;
  /** Additional CSS classes for the wrapper */
  className?: string;
  /** Whether to show shadow on tilt */
  shadow?: boolean;
  /** Whether to highlight on hover */
  highlight?: boolean;
}

const intensityConfig: Record<Intensity, { activeOffset: number; rotateXMax: number; rotateYMax: number; shadowScale: number }> = {
  subtle: { activeOffset: 20, rotateXMax: 5, rotateYMax: 5, shadowScale: 1.02 },
  medium: { activeOffset: 35, rotateXMax: 12, rotateYMax: 12, shadowScale: 1.05 },
  dramatic: { activeOffset: 50, rotateXMax: 20, rotateYMax: 20, shadowScale: 1.08 },
};

/**
 * AtroposCard — 3D parallax tilt wrapper using Atropos.
 *
 * Wraps children in an Atropos component for interactive 3D tilt
 * on hover. Children can use data-atropos-offset="N" to control
 * their parallax depth layer.
 *
 * Presets: subtle (5° max), medium (12° max), dramatic (20° max).
 * Disabled automatically on touch devices by Atropos.
 */
export default function AtroposCard({
  children,
  intensity = "subtle",
  className = "",
  shadow = true,
  highlight = true,
}: AtroposCardProps) {
  const config = intensityConfig[intensity];

  return (
    <Atropos
      className={`atropos-card ${className}`}
      activeOffset={config.activeOffset}
      rotateXMax={config.rotateXMax}
      rotateYMax={config.rotateYMax}
      shadow={shadow}
      shadowScale={config.shadowScale}
      highlight={highlight}
    >
      {children}
    </Atropos>
  );
}
