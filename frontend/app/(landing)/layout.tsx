"use client";

import GrainOverlay from "@/components/GrainOverlay";
import SmoothScroll from "@/components/SmoothScroll";
import CustomCursor from "@/components/CustomCursor";

import { UISoundProvider } from "@/components/UISoundEngine";

/**
 * Landing page layout — cinematic, distraction-free.
 *
 * Includes: Lenis smooth scrolling, film grain overlay,
 * custom magnetic cursor, and UI sound engine.
 */
export default function LandingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SmoothScroll>
      <UISoundProvider>
        <div className="bg-surface-0 min-h-screen">
          <CustomCursor />
          <GrainOverlay />
          {children}
        </div>
      </UISoundProvider>
    </SmoothScroll>
  );
}
