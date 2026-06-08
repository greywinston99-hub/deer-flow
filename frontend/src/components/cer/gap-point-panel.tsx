"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { GPointItem } from "@/core/cer_auth/v5_types";

interface GapPointPanelProps {
  gPoints: GPointItem[];
}

function blockingColor(level: string): string {
  switch (level) {
    case "BLOCKING":
      return "bg-red-500 text-white";
    case "WARNING":
      return "bg-amber-500 text-white";
    default:
      return "bg-blue-400 text-white";
  }
}

export function GapPointPanel({ gPoints }: GapPointPanelProps) {
  if (!gPoints.length) {
    return (
      <div className="text-sm text-muted-foreground py-4">
        No gaps identified. Run gap analysis to generate actionable paths.
      </div>
    );
  }

  const blocking = gPoints.filter((g) => g.blocking_level === "BLOCKING");
  const warnings = gPoints.filter((g) => g.blocking_level === "WARNING");
  const canContinue = blocking.length === 0 ? (warnings.length > 0 ? "LIMITED" : "YES") : "NO";

  return (
    <div className="space-y-3" data-testid="gap-point-panel">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">Workflow can continue:</span>
        <Badge className={canContinue === "YES" ? "bg-emerald-500 text-white" : canContinue === "LIMITED" ? "bg-amber-500 text-white" : "bg-red-500 text-white"}>
          {canContinue}
        </Badge>
      </div>

      <div className="text-xs text-muted-foreground">
        G-Points are actionable findings, not final regulatory conclusions.
      </div>

      <div className="space-y-2">
        {gPoints.map((gp) => (
          <Card key={gp.g_point_id} className="border-l-4 border-l-red-500">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">{gp.topic}</CardTitle>
                <Badge className={blockingColor(gp.blocking_level)}>{gp.blocking_level}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div>{gp.description}</div>
              <div className="text-muted-foreground">
                <span className="font-medium">Impact:</span> {gp.business_impact}
              </div>
              <div className="text-muted-foreground">
                <span className="font-medium">Action:</span> {gp.recommended_action}
              </div>
              <div className="text-muted-foreground">
                <span className="font-medium">Owner:</span> {gp.responsible_role}
              </div>
              <div className="text-muted-foreground">
                <span className="font-medium">Can continue:</span> {gp.workflow_can_continue}
              </div>
              {gp.next_action && (
                <div className="text-muted-foreground">
                  <span className="font-medium">Next:</span> {gp.next_action}
                </div>
              )}
              {gp.controlled_hold_reason && (
                <div className="text-muted-foreground">
                  <span className="font-medium">Hold reason:</span> {gp.controlled_hold_reason}
                </div>
              )}
              {gp.evidence_refs.length > 0 && (
                <div className="text-muted-foreground break-all">
                  <span className="font-medium">Evidence:</span> {gp.evidence_refs.slice(0, 3).join(" · ")}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
