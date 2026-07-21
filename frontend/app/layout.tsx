import "./globals.css";
import type { Metadata } from "next";

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
      <body>{children}</body>
    </html>
  );
}
