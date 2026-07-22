"use client";

import React, { useState } from "react";
import { ThumbsUp, ThumbsDown, CheckCircle2, AlertOctagon } from "lucide-react";
import { submitAnomalyFeedback, Anomaly } from "../app/api";

interface FeedbackControlProps {
  anomalyId: number;
  currentStatus: 'new' | 'reviewed' | 'resolved' | 'false_positive';
  onFeedbackSubmitted: (updated: Anomaly) => void;
}

export default function FeedbackControl({
  anomalyId,
  currentStatus,
  onFeedbackSubmitted,
}: FeedbackControlProps) {
  const [status, setStatus] = useState<string>(currentStatus);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const handleFeedback = async (targetStatus: 'reviewed' | 'false_positive') => {
    try {
      setSubmitting(true);
      setFeedbackMsg(null);
      const updated = await submitAnomalyFeedback(anomalyId, targetStatus);
      setStatus(updated.status);
      onFeedbackSubmitted(updated);
      
      if (targetStatus === 'false_positive') {
        setFeedbackMsg("Recorded as false positive. Decay applied to dominant score weight.");
      } else {
        setFeedbackMsg("Confirmed as reviewed anomaly.");
      }
    } catch (err: any) {
      console.error("Failed to submit feedback:", err);
      setFeedbackMsg(err.message || "Failed to submit feedback");
    } finally {
      setSubmitting(false);
    }
  };

  const isFalsePositive = status === 'false_positive';
  const isReviewed = status === 'reviewed' || status === 'resolved';

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-slate-300">
          {isFalsePositive ? (
            <AlertOctagon className="h-5 w-5 text-rose-400" />
          ) : isReviewed ? (
            <CheckCircle2 className="h-5 w-5 text-emerald-400" />
          ) : (
            <ThumbsUp className="h-5 w-5 text-cyan-400" />
          )}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Anomaly Status
            </span>
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${
                isFalsePositive
                  ? "bg-rose-950 text-rose-300 border border-rose-800"
                  : isReviewed
                  ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                  : "bg-amber-950 text-amber-300 border border-amber-800"
              }`}
            >
              {status.toUpperCase().replace("_", " ")}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Was this anomaly detection accurate and useful?
          </p>
        </div>
      </div>

      <div className="flex flex-col items-end gap-2 w-full sm:w-auto">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <button
            onClick={() => handleFeedback('reviewed')}
            disabled={submitting}
            className={`flex flex-1 sm:flex-initial items-center justify-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition duration-200 ${
              isReviewed
                ? "bg-emerald-600 text-white shadow-md shadow-emerald-900/30"
                : "bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
            } disabled:opacity-50`}
          >
            <ThumbsUp className="h-4 w-4" />
            <span>Confirm Anomaly</span>
          </button>

          <button
            onClick={() => handleFeedback('false_positive')}
            disabled={submitting}
            className={`flex flex-1 sm:flex-initial items-center justify-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition duration-200 ${
              isFalsePositive
                ? "bg-rose-600 text-white shadow-md shadow-rose-900/30"
                : "bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
            } disabled:opacity-50`}
          >
            <ThumbsDown className="h-4 w-4" />
            <span>False Positive</span>
          </button>
        </div>

        {feedbackMsg && (
          <span className="text-[11px] font-semibold text-cyan-400 animate-fade-in">
            {feedbackMsg}
          </span>
        )}
      </div>
    </div>
  );
}
