import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Driftline",
  description:
    "Anomaly detection, root-cause driver analysis, and short-horizon forecasting",
};

/**
 * Root layout — minimal HTML shell.
 *
 * Route-group layouts handle their own providers:
 *  - (dashboard) → MetricProvider, Navbar, PageTransition
 *  - (landing)   → SmoothScroll, GrainOverlay, CustomCursor
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-surface-0 text-slate-100 min-h-screen antialiased selection:bg-cyan-500 selection:text-slate-950">
        {children}
      </body>
    </html>
  );
}
