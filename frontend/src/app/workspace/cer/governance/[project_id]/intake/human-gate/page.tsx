"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useCERAuth, cerReviewFetch } from "@/core/cer_auth";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface IntakeStatusResponse {
  project_id: string;
  intake_session_id: string | null;
  current_state: string;
  artifacts: Record<string, string>;
  history: Array<{
    from_state: string;
    to_state: string;
    reason: string;
    timestamp: string;
  }>;
  stage_progress: Array<{
    stage: string;
    status: string;
    duration_sec: number | null;
    output_artifact: string | null;
  }>;
  is_locked: boolean;
}

interface HumanGateDecisionResponse {
  project_id: string;
  intake_session_id: string;
  decision: string;
  notes: string | null;
  submitted_at: string;
  decision_file: string;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function getIntakeStatus(projectId: string): Promise<IntakeStatusResponse> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/intake/status`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function submitHumanGateDecision(
  projectId: string,
  decision: string,
  notes: string | null
): Promise<HumanGateDecisionResponse> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/intake/human-decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, notes }),
    }
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DECISION_OPTIONS = [
  {
    value: "APPROVED",
    label: "Approve",
    description: "Accept the classification as-is and proceed to locked evidence pack",
    variant: "default" as const,
    color: "text-green-600",
  },
  {
    value: "APPROVED_WITH_CONDITIONS",
    label: "Approve with Conditions",
    description: "Accept but note conditions that must be tracked",
    variant: "default" as const,
    color: "text-yellow-600",
  },
  {
    value: "NEEDS_CORRECTION",
    label: "Needs Correction",
    description: "Request specific corrections before approval",
    variant: "secondary" as const,
    color: "text-orange-600",
  },
  {
    value: "REJECTED",
    label: "Reject",
    description: "Remediation required before re-submission",
    variant: "destructive" as const,
    color: "text-red-600",
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function HumanGatePage() {
  const params = useParams();
  const projectId = decodeURIComponent(String(params.project_id));
  const { user } = useCERAuth();

  const [status, setStatus] = useState<IntakeStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [selectedDecision, setSelectedDecision] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [submitted, setSubmitted] = useState<HumanGateDecisionResponse | null>(null);

  const isGatePending = status?.current_state === "human_gate_pending";
  const canSubmit = isGatePending && selectedDecision && !submitting;
  const canAct = user?.role === "SENIOR_REVIEWER" || user?.role === "ADMIN";

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getIntakeStatus(projectId);
      setStatus(data);
    } catch {
      toast.error("Failed to load intake status");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const result = await submitHumanGateDecision(projectId, selectedDecision!, notes || null);
      setSubmitted(result);
      toast.success(`Decision submitted: ${selectedDecision}`);
      await loadData();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to submit decision");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <p>Loading human gate status...</p>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-72 border-r flex flex-col">
        <div className="p-4 border-b">
          <div className="text-xs text-muted-foreground mb-1">
            <Link href="/workspace/cer/governance/run-home" className="hover:underline">
              ← Run Home
            </Link>
          </div>
          <h2 className="text-sm font-semibold font-mono">{projectId}</h2>
          <p className="text-xs text-muted-foreground mt-1">Human Intake Gate</p>
        </div>

        {/* Navigation */}
        <div className="p-2 space-y-1 flex-1 overflow-y-auto">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">INTAKE PAGES</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../`}>Intake Status</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../classification`}>Classification Review</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7 bg-primary/10" asChild>
            <Link href={`./`}>Human Gate</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../locked-pack`}>Locked Pack</Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {/* Header */}
          <div>
            <h1 className="text-xl font-bold">Human Intake Gate</h1>
            <p className="text-sm text-muted-foreground">
              Review classification results and approve/reject the evidence pack
            </p>
          </div>

          {/* Current State */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Gate Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <Badge
                  variant="outline"
                  className={`text-sm px-3 py-1 ${
                    isGatePending
                      ? "bg-yellow-50 border-yellow-300 text-yellow-800"
                      : status?.current_state === "human_gate_approved"
                      ? "bg-green-50 border-green-300 text-green-800"
                      : status?.current_state === "human_gate_rejected"
                      ? "bg-red-50 border-red-300 text-red-800"
                      : "bg-gray-50 border-gray-300 text-gray-800"
                  }`}
                >
                  {status?.current_state?.replace(/_/g, " ").toUpperCase() || "UNKNOWN"}
                </Badge>
                {status?.intake_session_id && (
                  <span className="text-xs text-muted-foreground font-mono">
                    {status.intake_session_id}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Role Warning */}
          {!canAct && (
            <Card className="border-blue-200 bg-blue-50">
              <CardContent className="pt-4">
                <div className="flex items-center gap-3">
                  <div className="text-2xl">👤</div>
                  <div>
                    <div className="font-medium text-blue-800">Read-Only View</div>
                    <div className="text-sm text-blue-600">
                      You are viewing as {user?.role || "Guest"}. Only SENIOR_REVIEWER or ADMIN can
                      submit decisions.
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Already Submitted */}
          {submitted && (
            <Card className="border-green-200 bg-green-50">
              <CardContent className="pt-4">
                <div className="flex items-center gap-3">
                  <div className="text-2xl">✓</div>
                  <div>
                    <div className="font-medium text-green-800">Decision Submitted</div>
                    <div className="text-sm text-green-600">
                      {submitted.decision} at {new Date(submitted.submitted_at).toLocaleString()}
                    </div>
                    {submitted.notes && (
                      <div className="text-sm text-green-700 mt-1 italic">"{submitted.notes}"</div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Decision Form */}
          {isGatePending && canAct && !submitted && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Decision Options</CardTitle>
                  <CardDescription>Select the appropriate action for this evidence pack</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {DECISION_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      onClick={() => setSelectedDecision(option.value)}
                      className={`w-full text-left p-4 rounded border transition-colors ${
                        selectedDecision === option.value
                          ? "border-primary bg-primary/5"
                          : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-4 h-4 rounded-full border-2 ${
                              selectedDecision === option.value
                                ? "border-primary bg-primary"
                                : "border-gray-300"
                            }`}
                          />
                          <span className={`font-medium ${option.color}`}>{option.label}</span>
                        </div>
                        {selectedDecision === option.value && (
                          <Badge variant="outline" className="text-xs">
                            Selected
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1 ml-7">
                        {option.description}
                      </p>
                    </button>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Notes (Optional)</CardTitle>
                </CardHeader>
                <CardContent>
                  <Textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Add any notes or conditions for this decision..."
                    rows={4}
                    className="resize-none"
                  />
                </CardContent>
              </Card>

              <div className="flex justify-end gap-3">
                <Button variant="outline" asChild>
                  <Link href={`../classification`}>Back to Classification</Link>
                </Button>
                <Button onClick={handleSubmit} disabled={!canSubmit}>
                  {submitting ? "Submitting..." : "Submit Decision"}
                </Button>
              </div>
            </>
          )}

          {/* Not Pending State */}
          {!isGatePending && !submitted && (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center space-y-4">
                  <div className="text-5xl">
                    {status?.current_state === "human_gate_approved"
                      ? "✓"
                      : status?.current_state === "human_gate_rejected"
                      ? "✗"
                      : "⏸"}
                  </div>
                  <div className="text-lg font-medium">
                    {status?.current_state === "human_gate_approved"
                      ? "Already Approved"
                      : status?.current_state === "human_gate_rejected"
                      ? "Already Rejected"
                      : "Gate Not Pending"}
                  </div>
                  <p className="text-sm text-muted-foreground max-w-md mx-auto">
                    {status?.current_state === "human_gate_approved"
                      ? "The evidence pack has been approved. View the locked pack to continue."
                      : status?.current_state === "human_gate_rejected"
                      ? "The evidence pack was rejected. Upload corrected evidence and run intake again."
                      : "This gate will become available after the intake pipeline completes."}
                  </p>
                  <div className="flex gap-3 justify-center pt-2">
                    <Button variant="outline" asChild>
                      <Link href={`../classification`}>View Classification</Link>
                    </Button>
                    <Button asChild>
                      <Link href={`../locked-pack`}>View Locked Pack</Link>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
