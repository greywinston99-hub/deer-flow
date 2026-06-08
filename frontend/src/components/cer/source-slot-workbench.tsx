"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SourceSlot } from "@/core/cer_auth/v5_types";

interface SourceSlotWorkbenchProps {
  slots: SourceSlot[];
  onConfirm: (slotId: string, fileId: string) => void;
  onReselect: (slotId: string, fileId: string, reason: string) => void;
  onMarkMissing: (slotId: string, reason: string) => void;
  onMarkOpenFile: (slotId: string, fileIds: string[], reason: string) => void;
  loading?: boolean;
}

function bandColor(band: string): string {
  switch (band) {
    case "HIGH":
      return "bg-emerald-100 text-emerald-800 border-emerald-300";
    case "MEDIUM":
      return "bg-amber-100 text-amber-800 border-amber-300";
    case "LOW":
      return "bg-orange-100 text-orange-800 border-orange-300";
    default:
      return "bg-slate-100 text-slate-800 border-slate-300";
  }
}

function statusBadge(status: string): string {
  switch (status) {
    case "CONFIRMED":
      return "bg-green-500 text-white";
    case "RESELECTED":
      return "bg-blue-500 text-white";
    case "MISSING":
      return "bg-red-500 text-white";
    case "OPEN_FILE_CHECK":
      return "bg-purple-500 text-white";
    case "HOLD":
      return "bg-gray-700 text-white";
    default:
      return "bg-gray-200 text-gray-800";
  }
}

export function SourceSlotWorkbench({
  slots,
  onReselect,
  onConfirm,
  onMarkMissing,
  onMarkOpenFile,
  loading,
}: SourceSlotWorkbenchProps) {
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i} className="h-40 animate-pulse bg-muted" />
        ))}
      </div>
    );
  }

  if (!slots.length) {
    return (
      <div className="text-center text-muted-foreground py-12">
        No source slots available. Run a source scan first.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {slots.map((slot) => {
          const isSelected = selectedSlot === slot.slot_id;
          const topCandidate = slot.candidates[0];
          const firstAlternative = slot.alternatives[0];

          return (
            <Card
              key={slot.slot_id}
              className={`cursor-pointer transition-shadow ${isSelected ? "ring-2 ring-primary" : "hover:shadow-md"}`}
              onClick={() => setSelectedSlot(isSelected ? null : slot.slot_id)}
              data-testid={`slot-card-${slot.slot_type}`}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-semibold">{slot.slot_type.replace(/_/g, " ")}</CardTitle>
                  <Badge variant="outline" className={bandColor(slot.confidence_band)}>
                    {slot.confidence_band}
                  </Badge>
                </div>
                <Badge className={`text-xs ${statusBadge(slot.slot_status)}`}>{slot.slot_status}</Badge>
              </CardHeader>
              <CardContent className="space-y-2">
                {topCandidate ? (
                  <div className="text-sm">
                    <div className="font-medium truncate">{topCandidate.file_name || topCandidate.file_id}</div>
                    <div className="text-xs text-muted-foreground">
                      Confidence: {(slot.confidence_score * 100).toFixed(0)}% · Integrity {slot.integrity_status} · Readability {slot.readability_status}
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground">{slot.missing_reason || "No candidate"}</div>
                )}

                <div className="text-xs text-muted-foreground line-clamp-2">
                  {slot.recommended_canonical_reason}
                </div>

                {slot.direct_evidence_link && (
                  <div className="text-xs">
                    <span className="font-medium">Evidence:</span>{" "}
                    <span className="text-muted-foreground break-all">{slot.direct_evidence_link}</span>
                  </div>
                )}

                {slot.risk_flags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {slot.risk_flags.slice(0, 3).map((flag) => (
                      <Badge key={flag} variant="outline" className="text-[10px]">
                        {flag}
                      </Badge>
                    ))}
                  </div>
                )}

                {slot.primary_action_hint && (
                  <div className="text-xs text-muted-foreground">
                    {slot.primary_action_hint}
                  </div>
                )}

                {isSelected && slot.slot_status === "RECOMMENDED" && topCandidate && (
                  <div className="space-y-3 pt-2">
                    <div className="rounded-md border bg-muted/30 p-2 text-xs space-y-1">
                      <div><span className="font-medium">Integrity check:</span> {slot.integrity_check_summary}</div>
                      {slot.evidence_basis.length > 0 && (
                        <div>
                          <span className="font-medium">Basis:</span> {slot.evidence_basis.slice(0, 2).join(" · ")}
                        </div>
                      )}
                      <div><span className="font-medium">Raw audit count:</span> {slot.raw_candidate_count}</div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="default"
                        onClick={(e) => {
                          e.stopPropagation();
                          onConfirm(slot.slot_id, topCandidate.file_id);
                        }}
                      >
                        Stage
                      </Button>
                      {firstAlternative && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            onReselect(slot.slot_id, firstAlternative.file_id, "Reviewer selected alternative candidate");
                          }}
                        >
                          Reselect
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation();
                          onMarkOpenFile(slot.slot_id, [topCandidate.file_id], "Confidence/readability requires open-file review");
                        }}
                      >
                        Open File Check
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={(e) => {
                          e.stopPropagation();
                          onMarkMissing(slot.slot_id, "Source not available");
                        }}
                      >
                        Mark Missing
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
