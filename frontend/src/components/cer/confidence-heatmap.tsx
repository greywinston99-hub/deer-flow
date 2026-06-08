"use client";

import { Badge } from "@/components/ui/badge";
import type { ConfidenceHeatmapItem } from "@/core/cer_auth/v5_types";

interface ConfidenceHeatmapProps {
  heatmap: ConfidenceHeatmapItem[];
}

function bandColor(band: string): string {
  switch (band) {
    case "HIGH":
      return "bg-emerald-500 text-white";
    case "MEDIUM":
      return "bg-amber-500 text-white";
    case "LOW":
      return "bg-orange-500 text-white";
    default:
      return "bg-slate-400 text-white";
  }
}

export function ConfidenceHeatmap({ heatmap }: ConfidenceHeatmapProps) {
  const summary = {
    HIGH: heatmap.filter((h) => h.confidence_band === "HIGH").length,
    MEDIUM: heatmap.filter((h) => h.confidence_band === "MEDIUM").length,
    LOW: heatmap.filter((h) => h.confidence_band === "LOW").length,
    MISSING: heatmap.filter((h) => h.confidence_band === "MISSING").length,
  };

  return (
    <div className="space-y-4" data-testid="confidence-heatmap">
      <div className="flex items-center gap-4">
        {Object.entries(summary).map(([band, count]) => (
          <div key={band} className="flex items-center gap-2">
            <Badge className={bandColor(band)}>{band}</Badge>
            <span className="text-sm font-medium">{count}</span>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
        {heatmap.map((item) => (
          <div
            key={item.slot_type}
            className={`rounded-md px-3 py-2 text-left text-xs font-medium ${bandColor(item.confidence_band)}`}
            title={`${item.slot_type}: ${item.confidence_score.toFixed(2)} — ${item.recommendation_reason}`}
          >
            <div className="truncate">{item.slot_type.replace(/_/g, " ")}</div>
            <div className="opacity-80">{(item.confidence_score * 100).toFixed(0)}%</div>
            <div className="mt-1 opacity-90">Integrity: {item.integrity_status}</div>
            <div className="opacity-90">Readability: {item.readability_status}</div>
            {item.risk_flags.length > 0 && (
              <div className="mt-1 opacity-90 truncate">
                Risks: {item.risk_flags.slice(0, 2).join(", ")}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground space-y-1">
        <div>Confidence heatmap is decision support only — not confirmation.</div>
        <div>High-confidence items may be staged, but never auto-approved.</div>
        <div>Medium-confidence items are the first reviewer attention zone.</div>
      </div>
    </div>
  );
}
