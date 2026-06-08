"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CopilotSuggestion } from "@/core/cer_auth/v5_types";

interface ReviewCopilotDrawerProps {
  suggestions: CopilotSuggestion[];
  onStageAction?: (actionId: string) => void;
}

export function ReviewCopilotDrawer({ suggestions, onStageAction }: ReviewCopilotDrawerProps) {
  return (
    <div className="space-y-3" data-testid="review-copilot-drawer">
      <div className="text-xs text-muted-foreground">
        Copilot explains and drafts only. Does not decide.
      </div>

      {suggestions.length === 0 && (
        <div className="text-sm text-muted-foreground">
          No suggestions yet. Ask a question or run analysis.
        </div>
      )}

      {suggestions.map((s) => (
        <Card key={s.suggestion_id}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">{s.suggestion_type.replace(/_/g, " ")}</CardTitle>
              {s.requires_human_confirmation && (
                <Badge variant="outline">Human confirmation required</Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="text-sm">{s.text}</div>
            {s.evidence_refs.length > 0 && (
              <div className="text-xs text-muted-foreground break-all">
                Evidence: {s.evidence_refs.slice(0, 4).join(" · ")}
              </div>
            )}
            {s.staged_action && (
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onStageAction?.(s.staged_action!.action_id)}
                >
                  Stage: {s.staged_action.action_type.replace(/_/g, " ")}
                </Button>
                <div className="text-xs text-muted-foreground">
                  Draft only. Human confirmation still required.
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
