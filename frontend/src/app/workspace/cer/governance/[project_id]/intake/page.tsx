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
import { cerReviewFetch } from "@/core/cer_auth";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface IntakeStageProgress {
  stage: string;
  status: string;
  duration_sec: number | null;
  output_artifact: string | null;
}

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
  stage_progress: IntakeStageProgress[];
  is_locked: boolean;
}

interface IntakePathResponse {
  project_id: string;
  raw_intake_path: string;
  uploaded_path: string;
  intake_session_path: string;
}

interface StartIntakeResponse {
  project_id: string;
  intake_session_id: string;
  mode: string;
  current_state: string;
  started_at: string;
  artifact_root: string;
  message: string;
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

async function getIntakePath(projectId: string): Promise<IntakePathResponse> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/intake/path`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function startIntake(projectId: string): Promise<StartIntakeResponse> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/intake/run`,
    { method: "POST" }
  );
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
    throw new Error(err.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const INTAKE_STAGES = [
  { id: "raw_uploaded", label: "Raw Upload", type: "deterministic" },
  { id: "inventory_created", label: "File Inventory", type: "deterministic" },
  { id: "dedupe_completed", label: "Deduplication", type: "deterministic" },
  { id: "parse_completed", label: "Text Extraction", type: "deterministic" },
  { id: "pdf_checked", label: "PDF Check", type: "deterministic" },
  { id: "type_detection_done", label: "Type Detection", type: "llm" },
  { id: "classification_completed", label: "Classification", type: "llm" },
  { id: "completeness_evaluated", label: "Completeness", type: "llm" },
  { id: "citations_traced", label: "Citations", type: "llm" },
  { id: "human_gate_pending", label: "Human Gate", type: "human" },
  { id: "evidence_pack_locked", label: "Lock Pack", type: "system" },
];

const STATE_LABELS: Record<string, string> = {
  raw_uploaded: "Raw Uploaded",
  inventory_created: "Inventory Created",
  dedupe_completed: "Deduplication Complete",
  parse_completed: "Parse Complete",
  pdf_checked: "PDF Checked",
  type_detection_done: "Type Detection Done",
  classification_completed: "Classification Complete",
  completeness_evaluated: "Completeness Evaluated",
  citations_traced: "Citations Traced",
  human_gate_pending: "Human Gate Pending",
  human_gate_approved: "Human Gate Approved",
  human_gate_rejected: "Human Gate Rejected",
  evidence_pack_locked: "Evidence Pack Locked",
  ready_for_cer_review: "Ready for CER Review",
  not_started: "Not Started",
  blocked: "Blocked",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function IntakeStatusPage() {
  const params = useParams();
  const projectId = decodeURIComponent(String(params.project_id));

  const [status, setStatus] = useState<IntakeStatusResponse | null>(null);
  const [paths, setPaths] = useState<IntakePathResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [lastRunResult, setLastRunResult] = useState<StartIntakeResponse | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statusData, pathData] = await Promise.all([
        getIntakeStatus(projectId).catch(() => null),
        getIntakePath(projectId).catch(() => null),
      ]);
      setStatus(statusData);
      setPaths(pathData);
    } catch {
      toast.error("Failed to load intake status");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRunIntake = useCallback(async () => {
    setIsRunning(true);
    setRunError(null);
    setLastRunResult(null);
    try {
      const result = await startIntake(projectId);
      setLastRunResult(result);
      toast.success("Intake run started");
      // Refresh status after a moment
      setTimeout(() => {
        loadData();
      }, 2000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start intake";
      setRunError(msg);
      toast.error(msg);
    } finally {
      setIsRunning(false);
    }
  }, [projectId, loadData]);

  const currentState = status?.current_state || "not_started";
  const isPending = currentState === "human_gate_pending";
  const isLocked = status?.is_locked || currentState === "evidence_pack_locked";

  const getStageStatus = (stageId: string): "pending" | "complete" | "error" => {
    if (currentState === "not_started") return "pending";
    if (currentState === "blocked") return "error";

    const stageIndex = INTAKE_STAGES.findIndex((s) => s.id === stageId);
    // Handle terminal states - if current state is past a stage, it's complete
    const currentIndex = INTAKE_STAGES.findIndex((s) => s.id === currentState);

    if (stageIndex < 0) return "pending";
    // Stage matches current state
    if (stageIndex === currentIndex) {
      // Check if this stage has a progress entry from backend
      const progress = status?.stage_progress?.find((p) => p.stage === stageId);
      if (progress) return progress.status === "complete" ? "complete" : "error";
      // Terminal states: approved/rejected/locked mean complete for human_gate stage
      if (stageId === "human_gate_pending" && (currentState === "human_gate_approved" || currentState === "human_gate_rejected")) {
        return "complete";
      }
      if (stageId === "evidence_pack_locked" && currentState === "evidence_pack_locked") {
        return "complete";
      }
      return "pending";
    }
    // Stage is before current state - it's complete
    if (stageIndex < currentIndex) return "complete";
    // Stage is after current state - it's pending
    return "pending";
  };

  const nextAction = (): { label: string; href?: string; variant: "default" | "outline"; onClick?: () => void } | null => {
    if (currentState === "not_started") {
      return { label: "Run Intake", variant: "default", onClick: handleRunIntake };
    }
    if (currentState === "human_gate_pending" || currentState === "classification_completed") {
      return { label: "Review Classification", href: "./classification", variant: "default" };
    }
    if (isLocked || currentState === "ready_for_cer_review") {
      return { label: "Start CER Review", href: "../gate-1", variant: "default" };
    }
    if (currentState === "human_gate_rejected") {
      return { label: "Re-upload Evidence", href: "../upload", variant: "outline" };
    }
    return null;
  };

  const next = nextAction();

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <p>Loading intake status...</p>
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
          <p className="text-xs text-muted-foreground mt-1">Intake Status</p>
        </div>

        {/* Navigation */}
        <div className="p-2 space-y-1 flex-1 overflow-y-auto">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">INTAKE PAGES</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7 bg-primary/10" asChild>
            <Link href={`./`}>
              Intake Status
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`./classification`}>
              Classification Review
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`./human-gate`}>
              Human Gate
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`./locked-pack`}>
              Locked Pack
            </Link>
          </Button>
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1 mt-3">CER REVIEW</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../upload`}>
              Upload Evidence
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../gate-1`}>
              G1 Route Review
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../gate-3`}>
              G3 BRR Review
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../artifacts`}>
              Artifacts Browser
            </Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold">Intake Status</h1>
              <p className="text-sm text-muted-foreground">
                {status?.intake_session_id
                  ? `Session: ${status.intake_session_id}`
                  : "No intake session yet"}
              </p>
            </div>
            {next && (
              next.onClick ? (
                <Button variant={next.variant} onClick={next.onClick} disabled={isRunning}>
                  {isRunning ? "Running..." : next.label}
                </Button>
              ) : next.href ? (
                <Button asChild variant={next.variant}>
                  <Link href={next.href}>{next.label}</Link>
                </Button>
              ) : null
            )}
          </div>

          {/* Current State Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Current State</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <Badge
                  variant="outline"
                  className={`text-sm px-3 py-1 font-mono ${
                    currentState === "human_gate_pending"
                      ? "bg-yellow-50 border-yellow-300 text-yellow-800"
                      : currentState === "ready_for_cer_review"
                      ? "bg-green-50 border-green-300 text-green-800"
                      : currentState === "human_gate_rejected"
                      ? "bg-red-50 border-red-300 text-red-800"
                      : currentState === "not_started"
                      ? "bg-blue-50 border-blue-300 text-blue-800"
                      : "bg-gray-50 border-gray-300 text-gray-800"
                  }`}
                >
                  {STATE_LABELS[currentState] || currentState}
                </Badge>
                {status?.intake_session_id && (
                  <span className="text-xs text-muted-foreground font-mono">
                    {status.intake_session_id}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Run Intake Status */}
          {(isRunning || lastRunResult || runError) && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Intake Run Status</CardTitle>
              </CardHeader>
              <CardContent>
                {isRunning && (
                  <div className="flex items-center gap-3 text-sm">
                    <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
                    <span className="text-muted-foreground">Running intake pipeline...</span>
                  </div>
                )}
                {lastRunResult && !isRunning && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="default" className="bg-green-600">Completed</Badge>
                      <span className="text-xs text-muted-foreground font-mono">
                        {lastRunResult.intake_session_id}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">{lastRunResult.message}</p>
                  </div>
                )}
                {runError && !isRunning && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="destructive">Failed</Badge>
                    </div>
                    <p className="text-xs text-red-600">{runError}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Path Info */}
          {paths && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">File Paths</CardTitle>
                <CardDescription>Where to place raw project files</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">
                    Raw Intake Input (original files):
                  </div>
                  <code className="text-xs bg-muted px-2 py-1 rounded block break-all">
                    {paths.raw_intake_path}
                  </code>
                  <p className="text-xs text-muted-foreground mt-1">
                    Place all source documents here before running intake
                  </p>
                </div>
                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">
                    Upload Evidence To (alternative):
                  </div>
                  <code className="text-xs bg-muted px-2 py-1 rounded block break-all">
                    {paths.uploaded_path}
                  </code>
                  <p className="text-xs text-muted-foreground mt-1">
                    Navigate to EP-001 through EP-005 folders to upload evidence
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Pipeline Progress */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Pipeline Progress</CardTitle>
              <CardDescription>11-stage intake workflow · 15 backend states</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2">
                {INTAKE_STAGES.map((stage) => {
                  const stageStatus = getStageStatus(stage.id);
                  const isHumanGate = stage.type === "human";
                  return (
                    <div
                      key={stage.id}
                      className={`flex items-center gap-2 p-2 rounded border ${
                        stageStatus === "complete"
                          ? "bg-green-50 border-green-200"
                          : stageStatus === "error"
                          ? "bg-red-50 border-red-200"
                          : "bg-gray-50 border-gray-200"
                      }`}
                    >
                      <div className="text-sm">
                        {stageStatus === "complete" ? (
                          <span className="text-green-600">✓</span>
                        ) : stageStatus === "error" ? (
                          <span className="text-red-600">✗</span>
                        ) : (
                          <span className="text-gray-400">○</span>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium truncate">{stage.label}</div>
                        <div className="text-[10px] text-muted-foreground capitalize">
                          {stage.type}
                          {isHumanGate && " — requires approval"}
                        </div>
                      </div>
                      <Badge
                        variant="outline"
                        className={`text-[10px] ${
                          stageStatus === "complete"
                            ? "border-green-300 text-green-700"
                            : stageStatus === "error"
                            ? "border-red-300 text-red-700"
                            : "border-gray-300 text-gray-500"
                        }`}
                      >
                        {stageStatus}
                      </Badge>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* History */}
          {status?.history && status.history.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">State History</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {status.history.map((entry, i) => (
                    <div key={i} className="flex items-start gap-3 text-xs">
                      <div className="w-2 h-2 mt-1.5 rounded-full bg-primary" />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[10px] font-mono">
                            {entry.from_state} → {entry.to_state}
                          </Badge>
                          <span className="text-muted-foreground text-[10px]">
                            {new Date(entry.timestamp).toLocaleString()}
                          </span>
                        </div>
                        <p className="text-muted-foreground mt-0.5">{entry.reason}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
