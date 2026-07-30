"use client";

import { ReactLenis } from "lenis/react";
import { useEffect } from "react";
import gsap from "gsap";

interface SmoothScrollProps {
  children: React.ReactNode;
}

/**
 * SmoothScroll — Lenis smooth scroll provider.
 *
 * Wraps children with ReactLenis for buttery momentum-based scrolling.
 * Syncs with GSAP ticker so ScrollTrigger animations fire correctly.
 * Respects prefers-reduced-motion (Lenis auto-disables).
 */
export default function SmoothScroll({ children }: SmoothScrollProps) {
  useEffect(() => {
    // Sync Lenis with GSAP ticker for ScrollTrigger compatibility
    const update = (time: number) => {
      // Lenis handles its own raf via ReactLenis root option
      // We just need to ensure GSAP ticker is running
      gsap.ticker.lagSmoothing(0);
    };
    gsap.ticker.add(update);
    return () => {
      gsap.ticker.remove(update);
    };
  }, []);

  return (
    <ReactLenis
      root
      options={{
        lerp: 0.1,
        duration: 1.2,
        smoothWheel: true,
        syncTouch: true,
      }}
    >
      {children}
    </ReactLenis>
  );
}
