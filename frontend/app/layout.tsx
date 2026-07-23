import "./globals.css";
import type { Metadata } from "next";
import { MetricProvider } from "@/components/MetricContext";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "Driftline",
  description: "Anomaly detection, root-cause driver analysis, and short-horizon forecasting",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 min-h-screen antialiased selection:bg-cyan-500 selection:text-slate-950">
        <MetricProvider>
          <Navbar />
          {children}
        </MetricProvider>
      </body>
    </html>
  );
}
