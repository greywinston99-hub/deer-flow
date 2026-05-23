"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type {
  ReviewFeedbackFinding,
  ReviewFeedbackPayload,
  ReviewFeedbackSeverity,
} from "@/core/cer_auth/v5_types";
import { useState } from "react";

interface ReviewFeedbackPanelProps {
  feedback: ReviewFeedbackPayload | null;
  onResolve?: (actions: FeedbackAction[]) => void;
}

export interface FeedbackAction {
  finding_id: string;
  action: "adopted" | "ignored" | "partially_addressed";
  note: string;
}

const SEVERITY_CONFIG: Record<
  ReviewFeedbackSeverity,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; order: number }
> = {
  CRITICAL: { label: "CRITICAL", variant: "destructive", order: 0 },
  HIGH: { label: "HIGH", variant: "default", order: 1 },
  MEDIUM: { label: "MEDIUM", variant: "secondary", order: 2 },
  LOW: { label: "LOW", variant: "outline", order: 3 },
  INFORMATIONAL: { label: "INFO", variant: "outline", order: 4 },
};

const DEPTH_LABEL: Record<string, string> = {
  PRIMARY_VERBATIM: "Primary (Verbatim)",
  PRIMARY_DERIVED: "Primary (Derived)",
  SECONDARY_SUMMARY: "Secondary (Summary)",
  MISSING_PRIMARY: "Missing Primary",
};

const CATEGORY_LABEL: Record<string, string> = {
  cross_doc_inconsistency: "Cross-Doc Inconsistency",
  regulatory_boundary_violation: "Regulatory Boundary",
  evidence_quality_gap: "Evidence Quality",
  claim_evidence_mismatch: "Claim-Evidence Mismatch",
  terminology_non_standard: "Terminology",
  format_degradation: "Format",
  missing_evidence: "Missing Evidence",
  orphan_requirement: "Orphan Requirement",
  metadata_inconsistency: "Metadata",
};

function severitySort(a: ReviewFeedbackFinding, b: ReviewFeedbackFinding): number {
  return SEVERITY_CONFIG[a.severity].order - SEVERITY_CONFIG[b.severity].order;
}

export function ReviewFeedbackPanel({ feedback, onResolve }: ReviewFeedbackPanelProps) {
  const [actions, setActions] = useState<Record<string, FeedbackAction>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});

  if (!feedback || feedback.finding_count === 0) {
    return (
      <div className="text-sm text-muted-foreground">
        No review feedback available.
      </div>
    );
  }

  const sortedFindings = [...feedback.findings].sort(severitySort);

  const handleAction = (findingId: string, action: FeedbackAction["action"]) => {
    setActions((prev) => {
      const next: Record<string, FeedbackAction> = { ...prev };
      next[findingId] = {
        finding_id: findingId,
        action,
        note: notes[findingId] || "",
      };
      return next;
    });
  };

  const handleNoteChange = (findingId: string, value: string) => {
    setNotes((prev) => ({ ...prev, [findingId]: value }));
    if (actions[findingId]) {
      setActions((prev) => {
        const next: Record<string, FeedbackAction> = { ...prev };
        const existing = prev[findingId]!;
        next[findingId] = { finding_id: existing.finding_id, action: existing.action, note: value };
        return next;
      });
    }
  };

  const handleSubmit = () => {
    const resolvedActions = Object.values(actions);
    if (resolvedActions.length > 0) {
      onResolve?.(resolvedActions);
    }
  };

  const resolvedCount = Object.keys(actions).length;

  return (
    <div className="space-y-4" data-testid="review-feedback-panel">
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {feedback.message}
        </div>
        <div className="text-xs text-muted-foreground">
          {resolvedCount} / {feedback.finding_count} resolved
        </div>
      </div>

      {sortedFindings.map((f) => {
        const cfg = SEVERITY_CONFIG[f.severity];
        const action = actions[f.finding_id];
        return (
          <Card key={f.finding_id} className={action ? "border-green-200 bg-green-50/30" : undefined}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant={cfg.variant}>{cfg.label}</Badge>
                  <Badge variant="outline">{DEPTH_LABEL[f.evidence_depth] || f.evidence_depth}</Badge>
                  <Badge variant="outline">{CATEGORY_LABEL[f.category] || f.category}</Badge>
                </div>
                <span className="text-xs text-muted-foreground font-mono">{f.finding_id}</span>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="text-sm">{f.description}</div>

              {f.rationale && (
                <div className="text-xs text-muted-foreground">
                  <span className="font-medium">Rationale:</span> {f.rationale}
                </div>
              )}

              {f.suggested_rework_node && (
                <div className="text-xs text-muted-foreground">
                  <span className="font-medium">Suggested rework:</span>{" "}
                  {f.suggested_rework_node.replace(/_/g, " ")}
                </div>
              )}

              {f.target_claim_id && (
                <div className="text-xs text-muted-foreground">
                  Target claim: <code>{f.target_claim_id}</code>
                </div>
              )}

              <Textarea
                placeholder="Add note (e.g. why adopted or ignored)..."
                className="text-xs min-h-[60px]"
                value={notes[f.finding_id] || ""}
                onChange={(e) => handleNoteChange(f.finding_id, e.target.value)}
              />

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant={action?.action === "adopted" ? "default" : "outline"}
                  onClick={() => handleAction(f.finding_id, "adopted")}
                >
                  Adopted
                </Button>
                <Button
                  size="sm"
                  variant={action?.action === "partially_addressed" ? "default" : "outline"}
                  onClick={() => handleAction(f.finding_id, "partially_addressed")}
                >
                  Partial
                </Button>
                <Button
                  size="sm"
                  variant={action?.action === "ignored" ? "secondary" : "outline"}
                  onClick={() => handleAction(f.finding_id, "ignored")}
                >
                  Ignore
                </Button>
              </div>
            </CardContent>
          </Card>
        );
      })}

      {feedback.findings.length > 0 && (
        <div className="flex justify-end">
          <Button
            onClick={handleSubmit}
            disabled={resolvedCount === 0}
          >
            Submit Resolution ({resolvedCount})
          </Button>
        </div>
      )}
    </div>
  );
}
