"use client";

import React from "react";
import { Info } from "lucide-react";

export default function LowConfidenceBanner() {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-amber-900/40 bg-amber-950/20 p-4 text-amber-200 shadow-md mb-8">
      <Info className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
      <div className="text-sm">
        <h4 className="font-bold text-amber-300 mb-1">
          Seasonal Estimate Active (Cold-Start Mode)
        </h4>
        <p className="text-amber-200/80 leading-relaxed">
          This metric currently has less than 60 days of historical observation data required for a full ML model. 
          A robust seasonal-naive fallback estimate is being displayed until sufficient training history accumulates.
        </p>
      </div>
    </div>
  );
}
