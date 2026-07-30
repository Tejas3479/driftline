"use client";

import { MetricProvider } from "@/components/MetricContext";
import Navbar from "@/components/Navbar";
import PageTransition from "@/components/PageTransition";
import GrainOverlay from "@/components/GrainOverlay";
import SmoothScroll from "@/components/SmoothScroll";
import { UISoundProvider } from "@/components/UISoundEngine";
import CustomCursor from "@/components/CustomCursor";

/**
 * Dashboard layout — wraps all /dashboard, /anomalies, /metrics, /settings pages.
 *
 * Provides: Lenis smooth scrolling, UI sound context, CustomCursor, MetricProvider,
 * Navbar, PageTransition, GrainOverlay.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SmoothScroll>
      <UISoundProvider>
        <div className="bg-mesh-pattern min-h-screen">
          <CustomCursor />
          <GrainOverlay />
          <MetricProvider>
            <Navbar />
            <PageTransition>{children}</PageTransition>
          </MetricProvider>
        </div>
      </UISoundProvider>
    </SmoothScroll>
  );
}
