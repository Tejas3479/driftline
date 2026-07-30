"use client";

import React, { useEffect, useRef } from "react";
import vegaEmbed from "vega-embed";

interface SegmentComparisonChartProps {
  spec: any;
}

export default function SegmentComparisonChart({ spec }: SegmentComparisonChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !spec) return;

    let resView: any = null;

    const embedPromise = vegaEmbed(containerRef.current, spec, {
      actions: false,
      renderer: "svg",
      theme: "dark",
    });

    if (embedPromise && typeof embedPromise.then === "function") {
      embedPromise
        .then((res) => {
          resView = res.view;
        })
        .catch((err) => {
          console.error("Failed to render Vega-Lite spec with vega-embed:", err);
        });
    }

    return () => {
      if (resView && typeof resView.finalize === "function") {
        resView.finalize();
      }
    };
  }, [spec]);


  if (!spec) {
    return (
      <div className="flex h-96 items-center justify-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400">
        No segment comparison spec available.
      </div>
    );
  }

  return (
    <div className="w-full glass-card-lg rounded-xl p-6 shadow-2xl overflow-x-auto">
      <div ref={containerRef} className="w-full flex justify-center" data-testid="vega-embed-container" />
    </div>
  );
}
