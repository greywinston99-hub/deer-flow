"use client";

import { useCallback, useEffect, useState } from "react";
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
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { getBackendBaseURL } from "@/core/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RMFStartResponse {
  thread_id: string;
  run_id: string;
  mode: string;
  workflow_name: string;
  executed_steps: string[];
  artifact_root_virtual: string;
  artifact_root_actual: string;
}

interface RMFStatusResponse {
  thread_id: string;
  run_id: string | null;
  mode: string | null;
  workflow_name: string | null;
  executed_steps: string[];
  artifact_root_virtual: string | null;
  artifact_root_actual: string | null;
  has_final_report: boolean;
  has_gate_closure_report: boolean;
  has_human_decision: boolean;
  final_recommended_gate: string | null;
  final_gate_status: string | null;
}

interface ArtifactSummary {
  path: string;
  artifact_name: string;
  step_id: string;
  download_url: string;
}

interface RMFArtifactsResponse {
  thread_id: string;
  artifact_root_actual: string;
  artifacts: ArtifactSummary[];
}

interface HumanDecisionResponse {
  success: boolean;
  decision_recorded: boolean;
  gate_closure_executed: boolean;
  artifact_root_actual: string;
  gate_closure_report_path: string;
  next_action_packet_path: string;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function startRMFReview(
  projectProfile: string,
  inputRoot: string | null,
  threadId: string | null,
): Promise<RMFStartResponse> {
  const body: Record<string, string | null> = {
    project_profile: projectProfile,
    input_root: inputRoot,
    thread_id: threadId,
  };
  const response = await fetch(`${getBackendBaseURL()}/api/rmf/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail ?? `HTTP ${response.status}`);
  }
  return response.json();
}

async function getRMFStatus(threadId: string): Promise<RMFStatusResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/rmf/status/${threadId}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail ?? `HTTP ${response.status}`);
  }
  return response.json();
}

async function getRMFArtifacts(threadId: string): Promise<RMFArtifactsResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/rmf/artifacts/${threadId}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail ?? `HTTP ${response.status}`);
  }
  return response.json();
}

async function submitHumanDecision(
  threadId: string,
  decision: string,
  reviewer: string,
  rationale: string,
  linkedReviewItems: string[],
  linkedCapaIds: string[],
): Promise<HumanDecisionResponse> {
  const body = {
    thread_id: threadId,
    decision,
    reviewer,
    rationale,
    linked_review_items: linkedReviewItems,
    linked_capa_ids: linkedCapaIds,
  };
  const response = await fetch(`${getBackendBaseURL()}/api/rmf/human-decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail ?? `HTTP ${response.status}`);
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RMFPage() {
  // Form state
  const [projectProfile, setProjectProfile] = useState("");
  const [inputRoot, setInputRoot] = useState("");
  const [threadId, setThreadId] = useState("");
  const [decision, setDecision] = useState<string>("pass");
  const [reviewer, setReviewer] = useState("");
  const [rationale, setRationale] = useState("");
  const [linkedReviewItems, setLinkedReviewItems] = useState("");
  const [linkedCapaIds, setLinkedCapaIds] = useState("");

  // Run state
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<RMFStartResponse | null>(null);
  const [statusResult, setStatusResult] = useState<RMFStatusResponse | null>(null);
  const [artifactsResult, setArtifactsResult] = useState<RMFArtifactsResponse | null>(null);
  const [humanDecisionResult, setHumanDecisionResult] = useState<HumanDecisionResponse | null>(null);

  // Human decision form state
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);

  useEffect(() => {
    document.title = "RMF Review - DeerFlow";
  }, []);

  const handleStartRun = useCallback(async () => {
    if (!projectProfile.trim()) {
      toast.error("project_profile path is required");
      return;
    }
    setIsRunning(true);
    setRunResult(null);
    setStatusResult(null);
    setArtifactsResult(null);
    setHumanDecisionResult(null);
    toast.info("RMF review started. This may take several minutes...");
    try {
      const result = await startRMFReview(
        projectProfile.trim(),
        inputRoot.trim() || null,
        threadId.trim() || null,
      );
      setRunResult(result);
      if (!threadId.trim()) {
        setThreadId(result.thread_id);
      }
      toast.success(`RMF review completed: ${result.executed_steps.length} steps executed`);
      // Refresh status and artifacts
      const [status, artifacts] = await Promise.all([
        getRMFStatus(result.thread_id),
        getRMFArtifacts(result.thread_id),
      ]);
      setStatusResult(status);
      setArtifactsResult(artifacts);
    } catch (err) {
      toast.error(`RMF review failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsRunning(false);
    }
  }, [projectProfile, inputRoot, threadId]);

  const handleRefreshStatus = useCallback(async () => {
    if (!threadId.trim()) {
      toast.error("thread_id is required to refresh status");
      return;
    }
    try {
      const [status, artifacts] = await Promise.all([
        getRMFStatus(threadId.trim()),
        getRMFArtifacts(threadId.trim()),
      ]);
      setStatusResult(status);
      setArtifactsResult(artifacts);
      toast.success("Status refreshed");
    } catch (err) {
      toast.error(`Failed to refresh: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [threadId]);

  const handleSubmitDecision = useCallback(async () => {
    if (!threadId.trim()) {
      toast.error("thread_id is required to submit decision");
      return;
    }
    if (!reviewer.trim()) {
      toast.error("reviewer name is required");
      return;
    }
    if (!decision) {
      toast.error("decision is required");
      return;
    }
    setIsSubmittingDecision(true);
    toast.info("Submitting human gate decision and triggering closure...");
    try {
      const result = await submitHumanDecision(
        threadId.trim(),
        decision,
        reviewer.trim(),
        rationale.trim(),
        linkedReviewItems.split("\n").map((s) => s.trim()).filter(Boolean),
        linkedCapaIds.split("\n").map((s) => s.trim()).filter(Boolean),
      );
      setHumanDecisionResult(result);
      toast.success("Human gate decision submitted and closure executed");
      // Refresh status
      const status = await getRMFStatus(threadId.trim());
      setStatusResult(status);
    } catch (err) {
      toast.error(`Decision submission failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsSubmittingDecision(false);
    }
  }, [threadId, decision, reviewer, rationale, linkedReviewItems, linkedCapaIds]);

  return (
    <div className="flex h-full w-full max-w-5xl flex-col gap-6 overflow-y-auto px-6 py-6">
      {/* Header */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">RMF Review Workflow</h1>
        <p className="text-muted-foreground text-sm">
          Trigger RMF review runs, view artifacts, and submit human gate decisions.
        </p>
      </div>

      {/* Run Trigger Card */}
      <Card>
        <CardHeader>
          <CardTitle>Trigger Review Run</CardTitle>
          <CardDescription>
            Run the RMF review workflow (smoke-run mode) against a project profile.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label htmlFor="project-profile" className="text-sm font-medium">project_profile path *</label>
            <Input
              id="project-profile"
              placeholder="/absolute/path/to/project_profile.yaml"
              value={projectProfile}
              onChange={(e) => setProjectProfile(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium" htmlFor="input-root">input_root path (optional)</label>
            <Input
              id="input-root"
              placeholder="/absolute/path/to/input/root (optional override)"
              value={inputRoot}
              onChange={(e) => setInputRoot(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium" htmlFor="thread-id">thread_id (optional, auto-generated if empty)</label>
            <Input
              id="thread-id"
              placeholder="Leave empty to auto-generate a new thread_id"
              value={threadId}
              onChange={(e) => setThreadId(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <Button onClick={handleStartRun} disabled={isRunning}>
              {isRunning ? "Running..." : "Start RMF Review"}
            </Button>
            {threadId.trim() && (
              <Button variant="outline" onClick={handleRefreshStatus} disabled={isRunning}>
                Refresh Status
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Run Summary */}
      {runResult && (
        <Card>
          <CardHeader>
            <CardTitle>Run Summary</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground font-medium">thread_id:</span>{" "}
                <span className="font-mono text-xs">{runResult.thread_id}</span>
              </div>
              <div>
                <span className="text-muted-foreground font-medium">run_id:</span>{" "}
                <span className="font-mono text-xs">{runResult.run_id}</span>
              </div>
              <div>
                <span className="text-muted-foreground font-medium">mode:</span>{" "}
                <Badge variant="secondary">{runResult.mode}</Badge>
              </div>
              <div>
                <span className="text-muted-foreground font-medium">workflow:</span>{" "}
                <span className="font-mono text-xs">{runResult.workflow_name}</span>
              </div>
            </div>
            <div>
              <span className="text-muted-foreground text-sm font-medium">
                executed_steps ({runResult.executed_steps.length}):
              </span>
              <div className="mt-1 flex flex-wrap gap-1">
                {runResult.executed_steps.map((step) => (
                  <Badge key={step} variant="outline" className="text-xs">
                    {step}
                  </Badge>
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-muted-foreground text-sm font-medium">artifact_root_actual:</span>
              <span className="break-all font-mono text-xs">{runResult.artifact_root_actual}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Status */}
      {statusResult && (
        <Card>
          <CardHeader>
            <CardTitle>Run Status</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              {statusResult.has_final_report && (
                <Badge variant="default">final_report ✓</Badge>
              )}
              {statusResult.has_human_decision && (
                <Badge variant="default">human_decision ✓</Badge>
              )}
              {statusResult.has_gate_closure_report && (
                <Badge variant="default">gate_closure ✓</Badge>
              )}
              {statusResult.final_recommended_gate && (
                <Badge variant="secondary">
                  recommended_gate: {statusResult.final_recommended_gate}
                </Badge>
              )}
              {statusResult.final_gate_status && (
                <Badge
                  variant={
                    statusResult.final_gate_status === "pass"
                      ? "default"
                      : statusResult.final_gate_status === "conditional_pass"
                        ? "secondary"
                        : "destructive"
                  }
                >
                  gate_status: {statusResult.final_gate_status}
                </Badge>
              )}
              {!statusResult.has_final_report &&
                !statusResult.has_human_decision &&
                !statusResult.has_gate_closure_report && (
                  <span className="text-muted-foreground text-sm">
                    Run in progress or no artifacts yet.
                  </span>
                )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Human Gate Decision Form */}
      {runResult && (
        <>
          <Separator />
          <Card>
            <CardHeader>
              <CardTitle>Human Gate Decision</CardTitle>
              <CardDescription>
                Submit a human gate decision to trigger gate closure. Requires a completed run
                with final_report.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium" htmlFor="decision">decision *</label>
                  <Select value={decision} onValueChange={setDecision}>
                    <SelectTrigger id="decision">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="pass">pass</SelectItem>
                      <SelectItem value="conditional_pass">conditional_pass</SelectItem>
                      <SelectItem value="rework_required">rework_required</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium" htmlFor="reviewer">reviewer *</label>
                  <Input
                    id="reviewer"
                    placeholder="Reviewer name or ID"
                    value={reviewer}
                    onChange={(e) => setReviewer(e.target.value)}
                  />
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium" htmlFor="rationale">rationale</label>
                <Textarea
                  id="rationale"
                  placeholder="Reasoning behind the decision..."
                  rows={3}
                  value={rationale}
                  onChange={(e) => setRationale(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium" htmlFor="linked-items">linked_review_items (one per line, optional)</label>
                <Textarea
                  id="linked-items"
                  placeholder="item_001&#10;item_002"
                  rows={2}
                  value={linkedReviewItems}
                  onChange={(e) => setLinkedReviewItems(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium" htmlFor="linked-capas">linked_capa_ids (one per line, optional)</label>
                <Textarea
                  id="linked-capas"
                  placeholder="capa_001&#10;capa_002"
                  rows={2}
                  value={linkedCapaIds}
                  onChange={(e) => setLinkedCapaIds(e.target.value)}
                />
              </div>
              <Button
                onClick={handleSubmitDecision}
                disabled={isSubmittingDecision || !statusResult?.has_final_report}
              >
                {isSubmittingDecision ? "Submitting..." : "Submit Decision & Trigger Closure"}
              </Button>
              {!statusResult?.has_final_report && runResult && (
                <p className="text-muted-foreground text-xs">
                  Final report not yet available. Complete the review run first.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Human Decision Result */}
          {humanDecisionResult && (
            <Card>
              <CardHeader>
                <CardTitle>Gate Closure Result</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2 text-sm">
                <div>
                  <span className="text-muted-foreground font-medium">success:</span>{" "}
                  <Badge variant={humanDecisionResult.success ? "default" : "destructive"}>
                    {String(humanDecisionResult.success)}
                  </Badge>
                </div>
                <div>
                  <span className="text-muted-foreground font-medium">gate_closure_executed:</span>{" "}
                  <Badge variant={humanDecisionResult.gate_closure_executed ? "default" : "secondary"}>
                    {String(humanDecisionResult.gate_closure_executed)}
                  </Badge>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-muted-foreground font-medium">gate_closure_report:</span>
                  <span className="break-all font-mono text-xs">
                    {humanDecisionResult.gate_closure_report_path}
                  </span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-muted-foreground font-medium">next_action_packet:</span>
                  <span className="break-all font-mono text-xs">
                    {humanDecisionResult.next_action_packet_path}
                  </span>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Artifacts */}
      {artifactsResult && artifactsResult.artifacts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Artifacts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              {artifactsResult.artifacts.map((artifact) => (
                <div
                  key={artifact.download_url}
                  className="flex items-center justify-between rounded border px-3 py-2 text-sm"
                >
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium">{artifact.artifact_name}</span>
                    <span className="text-muted-foreground text-xs">
                      step: {artifact.step_id}
                    </span>
                  </div>
                  <a
                    href={artifact.download_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary text-xs underline hover:no-underline"
                  >
                    view / download
                  </a>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
