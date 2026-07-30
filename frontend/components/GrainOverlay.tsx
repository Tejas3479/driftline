"use client";

/**
 * GrainOverlay — Film grain noise texture overlay.
 *
 * Uses an inline SVG feTurbulence filter animated via CSS
 * transform shifts. Fixed position, covers entire viewport.
 * GPU-composited via will-change. Extremely subtle (opacity 0.035).
 *
 * Respects prefers-reduced-motion (disabled entirely).
 */
export default function GrainOverlay() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-[9999] opacity-[0.035]"
      style={{ willChange: "transform" }}
    >
      <svg className="h-full w-full" xmlns="http://www.w3.org/2000/svg">
        <filter id="grain-filter">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.65"
            numOctaves="3"
            stitchTiles="stitch"
          />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect
          width="100%"
          height="100%"
          filter="url(#grain-filter)"
          className="animate-grain"
        />
      </svg>
    </div>
  );
}
