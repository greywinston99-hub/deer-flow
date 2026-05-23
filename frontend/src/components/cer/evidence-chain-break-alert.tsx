"use client";

import { AlertTriangle } from "lucide-react";
import type { ChainBreak } from "@/hooks/use-evidence-lineage";

interface EvidenceChainBreakAlertProps {
  breaks: ChainBreak[];
}

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "bg-red-50 border-red-200 text-red-800",
  HIGH: "bg-orange-50 border-orange-200 text-orange-800",
  MEDIUM: "bg-yellow-50 border-yellow-200 text-yellow-800",
  LOW: "bg-blue-50 border-blue-200 text-blue-800",
};

export function EvidenceChainBreakAlert({ breaks }: EvidenceChainBreakAlertProps) {
  if (!breaks || breaks.length === 0) return null;

  const criticalCount = breaks.filter((b) => b.severity === "CRITICAL").length;
  const highCount = breaks.filter((b) => b.severity === "HIGH").length;

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-3">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-red-600" />
        <span className="text-sm font-semibold text-red-800">
          Evidence Chain Breaks Detected
        </span>
        <span className="text-xs text-red-600">
          {criticalCount > 0 && `${criticalCount} CRITICAL`}
          {criticalCount > 0 && highCount > 0 && " · "}
          {highCount > 0 && `${highCount} HIGH`}
        </span>
      </div>
      <div className="mt-2 space-y-1">
        {breaks.slice(0, 5).map((b, i) => (
          <div
            key={i}
            className={`rounded px-2 py-1 text-xs border ${SEVERITY_COLORS[b.severity] || SEVERITY_COLORS.LOW}`}
          >
            <span className="font-medium">{b.type}</span>: {b.message}
          </div>
        ))}
        {breaks.length > 5 && (
          <div className="text-xs text-red-600">
            +{breaks.length - 5} more breaks
          </div>
        )}
      </div>
    </div>
  );
}
