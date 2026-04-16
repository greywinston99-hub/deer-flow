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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { getBackendBaseURL } from "@/core/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RunSummaryItem {
  run_id: string;
  mode: string;
  workflow_name: string;
  executed_steps: string[];
  artifact_root_actual: string;
  updated_at: number;
}

interface ThreadSummary {
  thread_id: string;
  latest_run_id: string | null;
  latest_mode: string | null;
  latest_executed_steps: string[];
  latest_final_recommended_gate: string | null;
  latest_final_gate_status: string | null;
  latest_has_closure: boolean;
  updated_at: number;
}

interface NextActionSummary {
  packet_type: string | null;
  decision: string | null;
  description: string | null;
  blocking_actions_count: number;
  total_actions_count: number;
  linked_capa_ids: string[];
}

interface ClosureResponse {
  thread_id: string;
  run_id: string;
  closure_completed: boolean;
  final_gate_status: string | null;
  human_decision: Record<string, unknown> | null;
  provisional_gate: string | null;
  provisional_only: boolean | null;
  next_action: NextActionSummary | null;
  gate_closure_report: Record<string, unknown> | null;
}

interface ArtifactSummary {
  path: string;
  artifact_name: string;
  step_id: string;
  download_url: string;
}

interface RichRunResponse {
  thread_id: string;
  run_id: string;
  mode: string;
  workflow_name: string;
  executed_steps: string[];
  artifact_root_virtual: string;
  artifact_root_actual: string;
  project_id: string | null;
  project_name: string | null;
  primary_review_object: string | null;
  input_root: string | null;
  human_gate_required: boolean;
  intake_summary: Record<string, unknown> | null;
  fmea_precheck_summary: Record<string, unknown> | null;
  rmf_precheck_summary: Record<string, unknown> | null;
  dimension_summary: Record<string, unknown> | null;
  human_boundary_summary: Record<string, unknown> | null;
  final_recommended_gate: string | null;
  provisional_gate: string | null;
  provisional_only: boolean | null;
  human_gate_required_flag: boolean | null;
  human_decision: Record<string, unknown> | null;
  gate_closure: Record<string, unknown> | null;
  next_action_packet: Record<string, unknown> | null;
  has_closure: boolean;
  closure_completed: boolean;
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

async function listThreads(): Promise<{ threads: ThreadSummary[] }> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/runs`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function listRuns(threadId: string): Promise<{ thread_id: string; runs: RunSummaryItem[] }> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/runs/${threadId}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getRunDetail(threadId: string, runId: string): Promise<RichRunResponse> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/run/${threadId}/${runId}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getClosure(threadId: string, runId?: string): Promise<ClosureResponse> {
  const url = runId
    ? `${getBackendBaseURL()}/api/rmf/closure/${threadId}?run_id=${encodeURIComponent(runId)}`
    : `${getBackendBaseURL()}/api/rmf/closure/${threadId}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getArtifacts(threadId: string, runId?: string): Promise<{ thread_id: string; run_id: string; artifact_root_actual: string; artifacts: ArtifactSummary[] }> {
  const url = runId
    ? `${getBackendBaseURL()}/api/rmf/artifacts/${threadId}?run_id=${encodeURIComponent(runId)}`
    : `${getBackendBaseURL()}/api/rmf/artifacts/${threadId}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function startRun(projectProfile: string, inputRoot: string | null, threadId: string | null): Promise<{ thread_id: string; run_id: string }> {
  const body: Record<string, string | null> = {
    project_profile: projectProfile,
    input_root: inputRoot,
    thread_id: threadId,
  };
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail ?? `HTTP ${r.status}`);
  }
  return r.json();
}

async function submitDecision(
  threadId: string,
  decision: string,
  reviewer: string,
  rationale: string,
  linkedReviewItems: string[],
  linkedCapaIds: string[],
): Promise<HumanDecisionResponse> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/human-decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      thread_id: threadId,
      decision,
      reviewer,
      rationale,
      linked_review_items: linkedReviewItems,
      linked_capa_ids: linkedCapaIds,
    }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail ?? `HTTP ${r.status}`);
  }
  return r.json();
}

async function triggerRework(threadId: string, rationale: string): Promise<{ thread_id: string; run_id: string }> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/rework`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, rationale }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail ?? `HTTP ${r.status}`);
  }
  return r.json();
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(timestamp: number): string {
  const d = new Date(timestamp * 1000);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString();
}

function formatRunId(runId: string): string {
  if (runId.length <= 16) return runId;
  return `${runId.slice(0, 8)}…${runId.slice(-6)}`;
}

// ---------------------------------------------------------------------------
// Helper components
// ---------------------------------------------------------------------------

function GateBadge({ value }: { value: string | null }) {
  if (!value) return <Badge variant="secondary">unknown</Badge>;
  const variant = value === "pass" ? "default" : value === "conditional_pass" ? "secondary" : "destructive";
  return <Badge variant={variant}>{value}</Badge>;
}

/** Machine recommendation — uses blue/outline style */
function MachineBadge({ value }: { value: string | null }) {
  if (!value) return <Badge variant="outline" className="border-blue-400 text-blue-600">unknown</Badge>;
  const variant = value === "pass" ? "default" : value === "conditional_pass" ? "secondary" : "destructive";
  return (
    <Badge variant={variant} className={value === "pass" ? "bg-blue-500 hover:bg-blue-600" : value === "conditional_pass" ? "bg-orange-400 hover:bg-orange-500 text-white" : "bg-red-600 hover:bg-red-700"}>
      {value}
    </Badge>
  );
}

/** Human decision — uses green/emerald style to distinguish from machine */
function HumanBadge({ value }: { value: string | null }) {
  if (!value) return <Badge variant="outline" className="border-green-400 text-green-600">pending</Badge>;
  return (
    <Badge variant="default" className={value === "pass" ? "bg-emerald-600 hover:bg-emerald-700" : value === "conditional_pass" ? "bg-amber-600 hover:bg-amber-700" : "bg-red-700 hover:bg-red-800"}>
      {value}
    </Badge>
  );
}

function ReworkAlert({ onGoToClosure }: { onGoToClosure: () => void }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-orange-300 bg-orange-50 px-4 py-3 dark:bg-orange-950/30 dark:border-orange-800">
      <div className="flex items-center gap-2">
        <Badge variant="default" className="bg-orange-500 hover:bg-orange-600">⚠ rework_required</Badge>
        <span className="text-sm text-orange-800 dark:text-orange-200">
          This run requires rework before it can proceed. Review the closure and trigger a rework run.
        </span>
      </div>
      <Button size="sm" variant="outline" className="border-orange-400 text-orange-700 hover:bg-orange-100 dark:text-orange-300 dark:hover:bg-orange-900" onClick={onGoToClosure}>
        Go to Closure →
      </Button>
    </div>
  );
}

function EmptyArtifactsState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="mb-3 text-4xl opacity-20">📄</div>
      <p className="text-sm font-medium text-muted-foreground">No artifacts yet</p>
      <p className="mt-1 text-xs text-muted-foreground">Artifacts will appear here once the run completes.</p>
    </div>
  );
}

/** Renders a step summary as a readable key-value card instead of raw JSON */
function StepSummaryCard({ title, summary }: { title: string; summary: Record<string, unknown> }) {
  const entries = Object.entries(summary).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (entries.length === 0) return null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2">
          {entries.map(([key, value]) => (
            <div key={key} className="flex flex-col gap-0.5">
              <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{key.replace(/_/g, " ")}</span>
              <span className="text-xs font-mono break-all">
                {typeof value === "object" ? JSON.stringify(value) : String(value as string | number | boolean | bigint | symbol)}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
      <div className="h-px flex-1 bg-border" />
    </div>
  );
}

// Artifact grouping helper
type ArtifactGroup = {
  label: string;
  stepIds: string[];
  keyArtifacts?: string[];
};

const ARTIFACT_GROUPS: ArtifactGroup[] = [
  { label: "Manifest", stepIds: ["rmf_intake_agent"], keyArtifacts: ["run_manifest.json", "input_inventory.json"] },
  { label: "Parse", stepIds: ["rmf_parse_normalize_agent"], keyArtifacts: ["rmf_normalized.json", "fmea_normalized.json"] },
  { label: "FMEA Precheck", stepIds: ["fmea_precheck_agent"], keyArtifacts: ["fmea_precheck_report.json"] },
  { label: "RMF Precheck", stepIds: ["rmf_precheck_agent"], keyArtifacts: ["rmf_precheck_report.json"] },
  { label: "Dimension Review", stepIds: ["rmf_dimension_review_agent"], keyArtifacts: ["dimension_assessment.json", "dimension_review_report.md"] },
  { label: "Human Boundary", stepIds: ["rmf_human_boundary_agent"], keyArtifacts: ["human_gate_decision.json", "provisional_gate_recommendation.json", "human_review_queue.json"] },
  { label: "Final Report", stepIds: ["rmf_report_agent"], keyArtifacts: ["final_report.md", "final_report.json", "capa_action_list.json"] },
  { label: "Gate Closure", stepIds: ["rmf_gate_closure_agent"], keyArtifacts: ["gate_closure_report.md", "gate_closure_report.json", "next_action_packet.json"] },
];

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function RMFWorkbenchPage() {
  // ---- Thread list state ----
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [runsForThread, setRunsForThread] = useState<RunSummaryItem[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [loadingThreads, setLoadingThreads] = useState(false);

  // ---- Run detail state ----
  const [runDetail, setRunDetail] = useState<RichRunResponse | null>(null);
  const [closureData, setClosureData] = useState<ClosureResponse | null>(null);
  const [artifactsData, setArtifactsData] = useState<{ artifacts: ArtifactSummary[] } | null>(null);
  // ---- Run form state ----
  const [projectProfile, setProjectProfile] = useState("");
  const [inputRoot, setInputRoot] = useState("");
  const [isRunning, setIsRunning] = useState(false);

  // ---- Human decision form state ----
  const [decision, setDecision] = useState<string>("pass");
  const [reviewer, setReviewer] = useState("");
  const [rationale, setRationale] = useState("");
  const [linkedReviewItems, setLinkedReviewItems] = useState("");
  const [linkedCapaIds, setLinkedCapaIds] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [decisionResult, setDecisionResult] = useState<HumanDecisionResponse | null>(null);

  // ---- Rework state ----
  const [reworkRationale, setReworkRationale] = useState("");
  const [isReworking, setIsReworking] = useState(false);

  // ---- Active tab ----
  const [activeTab, setActiveTab] = useState("overview");

  // ---- Load threads on mount ----
  useEffect(() => {
    document.title = "RMF Review Workbench - DeerFlow";
    void loadThreads();
  }, []);

  // ---- Load runs when thread selected ----
  useEffect(() => {
    if (selectedThreadId) {
      void loadRuns(selectedThreadId);
    } else {
      setRunsForThread([]);
      setSelectedRunId(null);
      setRunDetail(null);
    }
    // loadRuns is intentionally not a dep: it must not trigger re-runs
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedThreadId]);

  // ---- Load run detail when run selected ----
  useEffect(() => {
    if (selectedThreadId && selectedRunId) {
      void loadRunDetail(selectedThreadId, selectedRunId);
    } else {
      setRunDetail(null);
      setClosureData(null);
      setArtifactsData(null);
    }
  }, [selectedThreadId, selectedRunId]);

  const loadThreads = async () => {
    setLoadingThreads(true);
    try {
      const data = await listThreads();
      setThreads(data.threads ?? []);
    } catch (e) {
      toast.error(`Failed to load threads: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoadingThreads(false);
    }
  };

  const loadRuns = async (threadId: string) => {
    try {
      const data = await listRuns(threadId);
      setRunsForThread(data.runs ?? []);
      if (data.runs.length > 0 && !selectedRunId) {
        setSelectedRunId(data.runs.at(0)!.run_id);
      }
    } catch (e) {
      toast.error(`Failed to load runs: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const loadRunDetail = async (threadId: string, runId: string) => {
    try {
      const [detail, closure, artifacts] = await Promise.all([
        getRunDetail(threadId, runId),
        getClosure(threadId, runId).catch(() => null),
        getArtifacts(threadId, runId).catch(() => null),
      ]);
      setRunDetail(detail);
      setClosureData(closure);
      setArtifactsData(artifacts);
    } catch (e) {
      toast.error(`Failed to load run detail: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const handleStartRun = useCallback(async () => {
    if (!projectProfile.trim()) {
      toast.error("project_profile path is required");
      return;
    }
    setIsRunning(true);
    try {
      const result = await startRun(projectProfile.trim(), inputRoot.trim() || null, null);
      toast.success("RMF review started");
      await loadThreads();
      setSelectedThreadId(result.thread_id);
      // Select the new run once runs load
    } catch (e) {
      toast.error(`Start failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setIsRunning(false);
    }
  }, [projectProfile, inputRoot]);

  const handleRefresh = useCallback(() => {
    if (selectedThreadId) void loadThreads();
    if (selectedThreadId && selectedRunId) void loadRunDetail(selectedThreadId, selectedRunId);
  }, [selectedThreadId, selectedRunId]);

  const handleSubmitDecision = useCallback(async () => {
    if (!selectedThreadId) return;
    if (!reviewer.trim()) { toast.error("reviewer name is required"); return; }
    setIsSubmitting(true);
    try {
      const result = await submitDecision(
        selectedThreadId,
        decision,
        reviewer.trim(),
        rationale.trim(),
        linkedReviewItems.split("\n").map((s) => s.trim()).filter(Boolean),
        linkedCapaIds.split("\n").map((s) => s.trim()).filter(Boolean),
      );
      setDecisionResult(result);
      toast.success("Human decision submitted and closure executed");
      if (selectedThreadId && selectedRunId) {
        await loadRunDetail(selectedThreadId, selectedRunId);
      }
    } catch (e) {
      toast.error(`Decision failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setIsSubmitting(false);
    }
  }, [selectedThreadId, selectedRunId, decision, reviewer, rationale, linkedReviewItems, linkedCapaIds]);

  const handleRework = useCallback(async () => {
    if (!selectedThreadId) return;
    setIsReworking(true);
    try {
      const result = await triggerRework(selectedThreadId, reworkRationale.trim());
      toast.success("Rework run triggered");
      await loadThreads();
      setSelectedThreadId(result.thread_id);
      setReworkRationale("");
    } catch (e) {
      toast.error(`Rework failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setIsReworking(false);
    }
  }, [selectedThreadId, reworkRationale]);

  // ---------------------------------------------------------------------------
  // Render: left sidebar + main content
  // ---------------------------------------------------------------------------
  return (
    <div className="flex h-full w-full">
      {/* ---- Sidebar ---- */}
      <div className="flex w-72 flex-shrink-0 flex-col border-r">
        {/* New Run form */}
        <div className="border-b">
          <div className="px-4 pt-4 pb-2">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold">New Run</h2>
            </div>
            <div className="flex flex-col gap-2">
              <div>
                <Input
                  placeholder="project_profile.yaml"
                  value={projectProfile}
                  onChange={(e) => setProjectProfile(e.target.value)}
                  className="text-xs"
                />
              </div>
              <div>
                <Input
                  placeholder="input_root (optional)"
                  value={inputRoot}
                  onChange={(e) => setInputRoot(e.target.value)}
                  className="text-xs"
                />
              </div>
              <Button size="sm" onClick={handleStartRun} disabled={isRunning} className="w-full">
                {isRunning ? (
                  <span className="flex items-center gap-1">
                    <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                    Running…
                  </span>
                ) : (
                  "Start Run"
                )}
              </Button>
              <Button size="sm" variant="outline" className="w-full" onClick={() => window.location.href = "/workspace/rmf/projects"}>
                View Projects
              </Button>
            </div>
          </div>
        </div>

        {/* Thread list */}
        <div className="flex flex-1 flex-col overflow-y-auto">
          <SectionDivider label="Recent Runs" />
          {loadingThreads && (
            <div className="flex items-center justify-center py-6">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          )}
          {threads.length === 0 && !loadingThreads && (
            <p className="px-4 py-3 text-xs text-muted-foreground">No runs yet. Start a run above.</p>
          )}
          {threads.map((thread) => {
            const isSelected = selectedThreadId === thread.thread_id;
            return (
              <div key={thread.thread_id}>
                <button
                  className={`w-full px-4 py-2 text-left text-sm transition-colors hover:bg-muted ${
                    isSelected ? "bg-muted" : ""
                  }`}
                  onClick={() => {
                    setSelectedThreadId(thread.thread_id);
                    setSelectedRunId(null);
                    setRunDetail(null);
                    setClosureData(null);
                    setArtifactsData(null);
                    setDecisionResult(null);
                  }}
                >
                  {/* Thread ID row */}
                  <div className={`truncate font-mono text-xs font-medium ${isSelected ? "text-foreground" : "text-foreground/80"}`}>
                    {thread.thread_id}
                  </div>
                  {/* Status badges */}
                  <div className="mt-1 flex flex-wrap items-center gap-1">
                    {thread.latest_has_closure && (
                      <Badge variant="outline" className="text-[10px] px-1 py-0 border-green-500 text-green-600">✓ closed</Badge>
                    )}
                    {thread.latest_final_gate_status === "rework_required" && (
                      <Badge variant="outline" className="text-[10px] px-1 py-0 border-orange-500 text-orange-600">⚠ rework</Badge>
                    )}
                    {thread.latest_final_recommended_gate && (
                      <MachineBadge value={thread.latest_final_recommended_gate} />
                    )}
                  </div>
                  {/* Meta row */}
                  <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                    <Badge variant="outline" className="text-[9px] px-1 py-0">{thread.latest_mode}</Badge>
                    <span>·</span>
                    <span>{formatDate(thread.updated_at)}</span>
                  </div>
                </button>
                {/* Runs sub-list */}
                {isSelected && runsForThread.length > 0 && (
                  <div className="bg-muted/40">
                    {runsForThread.map((run) => {
                      const isRunSelected = selectedRunId === run.run_id;
                      return (
                        <button
                          key={run.run_id}
                          className={`ml-4 flex w-[calc(100%-1rem)] items-center gap-2 border-l-2 px-3 py-1.5 text-left text-xs transition-colors hover:bg-muted ${
                            isRunSelected ? "border-primary bg-muted" : "border-transparent"
                          }`}
                          onClick={() => setSelectedRunId(run.run_id)}
                        >
                          <span className="ml-1 truncate font-mono text-[10px] text-muted-foreground">{formatRunId(run.run_id)}</span>
                          <Badge variant="outline" className="text-[9px] px-1 py-0 shrink-0">{run.executed_steps.length} steps</Badge>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ---- Main content ---- */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {!selectedThreadId || !runDetail ? (
          <div className="flex flex-1 items-center justify-center text-muted-foreground">
            <div className="text-center">
              <p className="text-lg font-medium">RMF Review Workbench</p>
              <p className="mt-1 text-sm">Select a thread from the sidebar or start a new run.</p>
              <Button variant="outline" className="mt-4" onClick={handleRefresh}>
                Refresh Thread List
              </Button>
            </div>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="flex items-center justify-between border-b px-6 py-4">
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-3">
                  <h1 className="text-lg font-semibold">{runDetail.project_name ?? "RMF Review"}</h1>
                  <Badge variant="outline" className="text-xs">{runDetail.mode}</Badge>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-mono">{runDetail.thread_id}</span>
                  <span>›</span>
                  <span className="font-mono">{formatRunId(runDetail.run_id)}</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleRefresh}>
                  ↺ Refresh
                </Button>
                {runDetail.has_closure && (
                  <Button variant="outline" size="sm" onClick={() => setActiveTab("closure")}>
                    View Closure
                  </Button>
                )}
              </div>
            </div>

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 overflow-hidden">
              <TabsList className="mx-6 mt-4">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
                <TabsTrigger value="decision">Human Decision</TabsTrigger>
                <TabsTrigger value="closure">Closure</TabsTrigger>
              </TabsList>

              {/* ---- Overview Tab ---- */}
              <TabsContent value="overview" className="overflow-y-auto px-6 py-4">
                <div className="flex flex-col gap-5">

                  {/* Rework alert — shown when rework_required */}
                  {runDetail.gate_closure?.final_decision === "rework_required" && (
                    <ReworkAlert onGoToClosure={() => setActiveTab("closure")} />
                  )}

                  {/* Gate Decision Summary strip */}
                  <div className="grid grid-cols-3 gap-3">
                    {/* Machine Recommendation */}
                    <div className="flex flex-col gap-2 rounded-lg border border-blue-200 bg-blue-50/50 p-3 dark:border-blue-900 dark:bg-blue-950/20">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400">Machine Recommendation</span>
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <MachineBadge value={runDetail.final_recommended_gate} />
                        {runDetail.provisional_gate && (
                          <div className="flex items-center gap-1.5">
                            <span className="text-[10px] text-muted-foreground">provisional:</span>
                            <MachineBadge value={runDetail.provisional_gate} />
                            {runDetail.provisional_only && (
                              <Badge variant="outline" className="text-[10px]">provisional only</Badge>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                    {/* Human Decision */}
                    <div className="flex flex-col gap-2 rounded-lg border border-emerald-200 bg-emerald-50/50 p-3 dark:border-emerald-900 dark:bg-emerald-950/20">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">Human Decision</span>
                      </div>
                      <div className="flex flex-col gap-1">
                        {runDetail.human_decision ? (
                          <>
                            <HumanBadge value={runDetail.human_decision.decision as string} />
                            <span className="text-[10px] text-muted-foreground">
                              by {(runDetail.human_decision.reviewer as string) ?? "unknown"} ·{" "}
                              {(runDetail.human_decision.simulated as boolean) ? "⚠ simulated" : "✓ confirmed"}
                            </span>
                          </>
                        ) : (
                          <Badge variant="outline" className="w-fit border-dashed border-emerald-400 text-emerald-600">pending</Badge>
                        )}
                      </div>
                    </div>
                    {/* Final Gate Status */}
                    <div className="flex flex-col gap-2 rounded-lg border border-muted-foreground/20 bg-muted/30 p-3">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Final Gate Status</span>
                      </div>
                      <div className="flex flex-col gap-1">
                        {runDetail.has_closure ? (
                          <GateBadge value={runDetail.gate_closure?.final_decision as string ?? null} />
                        ) : (
                          <Badge variant="secondary" className="w-fit">not closed</Badge>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Rework hint — shown when human decision is rework_required but no closure yet */}
                  {runDetail.human_decision && (runDetail.human_decision.decision as string) === "rework_required" && !runDetail.has_closure && (
                    <div className="flex items-center gap-2 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-xs text-orange-800 dark:bg-orange-950/20 dark:text-orange-200">
                      <span>⚠ Rework required — go to the</span>
                      <button className="underline" onClick={() => setActiveTab("closure")}>Closure tab</button>
                      <span>to trigger a rework run.</span>
                    </div>
                  )}

                  {/* Steps executed */}
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm">Workflow Steps ({runDetail.executed_steps.length})</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-1.5">
                        {runDetail.executed_steps.map((step, i) => (
                          <div key={step} className="flex items-center gap-1.5 rounded border bg-card px-2 py-1 text-xs">
                            <span className="text-muted-foreground font-mono text-[10px]">{String(i + 1).padStart(2, "0")}</span>
                            <Badge variant="outline" className="text-[11px]">{step}</Badge>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Step summaries — improved readable layout */}
                  {runDetail.intake_summary && (
                    <StepSummaryCard
                      title="Intake Summary"
                      // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
                      summary={runDetail.intake_summary as Record<string, unknown>}
                    />
                  )}

                  {runDetail.fmea_precheck_summary && (
                    <StepSummaryCard
                      title="FMEA Precheck"
                      // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
                      summary={runDetail.fmea_precheck_summary as Record<string, unknown>}
                    />
                  )}

                  {runDetail.rmf_precheck_summary && (
                    <StepSummaryCard
                      title="RMF Precheck"
                      // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
                      summary={runDetail.rmf_precheck_summary as Record<string, unknown>}
                    />
                  )}

                  {runDetail.dimension_summary && (
                    <StepSummaryCard
                      title="Dimension Assessment"
                      // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
                      summary={runDetail.dimension_summary as Record<string, unknown>}
                    />
                  )}

                  {runDetail.human_boundary_summary && (
                    <StepSummaryCard
                      title={`Human Review Queue (${(runDetail.human_boundary_summary.item_count as number) ?? 0} items)`}
                      // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
                      summary={runDetail.human_boundary_summary as Record<string, unknown>}
                    />
                  )}
                </div>
              </TabsContent>

              {/* ---- Artifacts Tab ---- */}
              <TabsContent value="artifacts" className="overflow-y-auto px-6 py-4">
                {!artifactsData?.artifacts.length ? (
                  <EmptyArtifactsState />
                ) : (
                  <div className="flex flex-col gap-5">
                    {ARTIFACT_GROUPS.map((group) => {
                      const groupArtifacts = artifactsData.artifacts.filter((a) =>
                        group.stepIds.includes(a.step_id),
                      );
                      if (groupArtifacts.length === 0) return null;
                      return (
                        <div key={group.label} className="flex flex-col gap-2">
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm font-semibold">{group.label}</h3>
                            <Badge variant="outline" className="text-[10px]">{groupArtifacts.length}</Badge>
                          </div>
                          <div className="flex flex-col gap-1.5">
                            {groupArtifacts.map((artifact) => {
                              const isKey = group.keyArtifacts?.includes(artifact.artifact_name);
                              return (
                                <div
                                  key={artifact.download_url}
                                  className={`flex items-center justify-between rounded border px-4 py-2.5 transition-colors hover:bg-muted/50 ${isKey ? "border-primary/40 bg-primary/5" : ""}`}
                                >
                                  <div className="flex items-center gap-2.5">
                                    {isKey && <span className="text-xs">★</span>}
                                    <div className="flex flex-col gap-0.5">
                                      <span className={`font-medium text-sm ${isKey ? "font-semibold" : ""}`}>
                                        {artifact.artifact_name}
                                      </span>
                                      <span className="text-muted-foreground text-[10px] font-mono">{artifact.step_id}</span>
                                    </div>
                                  </div>
                                  <a
                                    href={artifact.download_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-1 text-xs text-primary underline hover:no-underline"
                                  >
                                    view
                                    <span className="text-muted-foreground">/</span>
                                    download
                                  </a>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </TabsContent>

              {/* ---- Human Decision Tab ---- */}
              <TabsContent value="decision" className="overflow-y-auto px-6 py-4">
                {runDetail.has_closure ? (
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3 dark:bg-green-950/20 dark:border-green-900">
                      <span className="text-green-600 dark:text-green-400">✓</span>
                      <div>
                        <p className="text-sm font-medium">Decision Already Submitted</p>
                        <p className="text-xs text-muted-foreground">Gate closure has already been executed for this run.</p>
                      </div>
                    </div>
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Recorded Decision</CardTitle>
                      </CardHeader>
                      <CardContent className="flex flex-col gap-3">
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-muted-foreground">Final decision:</span>
                          <GateBadge value={runDetail.gate_closure?.final_decision as string ?? null} />
                        </div>
                        {runDetail.human_decision && (
                          <>
                            <div className="flex items-center gap-3">
                              <span className="text-xs text-muted-foreground">Reviewer:</span>
                              <span className="text-xs font-medium">{runDetail.human_decision.reviewer as string}</span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="text-xs text-muted-foreground">Status:</span>
                              <span className="text-xs">{(runDetail.human_decision.simulated as boolean) ? "⚠ simulated" : "✓ confirmed"}</span>
                            </div>
                            {(runDetail.human_decision.rationale as string) && (
                              <div className="flex flex-col gap-1">
                                <span className="text-xs text-muted-foreground">Rationale:</span>
                                <p className="text-xs rounded bg-muted px-2 py-1.5">{(runDetail.human_decision.rationale as string)}</p>
                              </div>
                            )}
                          </>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">
                    {/* Decision highlight strip */}
                    <div className="flex items-center gap-2 rounded-lg border border-muted-foreground/20 bg-muted/30 px-4 py-2">
                      <span className="text-xs text-muted-foreground">Machine recommended:</span>
                      <MachineBadge value={runDetail.final_recommended_gate} />
                      {runDetail.provisional_gate && (
                        <>
                          <span className="text-xs text-muted-foreground">· provisional:</span>
                          <MachineBadge value={runDetail.provisional_gate} />
                        </>
                      )}
                    </div>
                    <Card>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-sm">Submit Human Gate Decision</CardTitle>
                        <CardDescription>
                          Your decision will trigger gate closure. This does NOT re-run steps 1–7.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="flex flex-col gap-5">
                        {/* Decision + Reviewer row */}
                        <div className="grid grid-cols-2 gap-4">
                          <div className="flex flex-col gap-2">
                            <label className="text-xs font-semibold">decision *</label>
                            <Select value={decision} onValueChange={setDecision}>
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="pass">
                                  <span className="flex items-center gap-2">
                                    <span className="h-2 w-2 rounded-full bg-emerald-500" />pass
                                  </span>
                                </SelectItem>
                                <SelectItem value="conditional_pass">
                                  <span className="flex items-center gap-2">
                                    <span className="h-2 w-2 rounded-full bg-amber-500" />conditional_pass
                                  </span>
                                </SelectItem>
                                <SelectItem value="rework_required">
                                  <span className="flex items-center gap-2">
                                    <span className="h-2 w-2 rounded-full bg-red-500" />rework_required
                                  </span>
                                </SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="flex flex-col gap-2">
                            <label className="text-xs font-semibold">reviewer *</label>
                            <Input
                              placeholder="Reviewer name or ID"
                              value={reviewer}
                              onChange={(e) => setReviewer(e.target.value)}
                            />
                          </div>
                        </div>
                        {/* Rationale */}
                        <div className="flex flex-col gap-2">
                          <label className="text-xs font-semibold">rationale (optional)</label>
                          <Textarea
                            placeholder="Explain the reasoning behind your decision…"
                            rows={3}
                            value={rationale}
                            onChange={(e) => setRationale(e.target.value)}
                          />
                        </div>
                        {/* Linked items row */}
                        <div className="grid grid-cols-2 gap-4">
                          <div className="flex flex-col gap-2">
                            <label className="text-xs font-semibold">linked_review_items (optional, one per line)</label>
                            <Textarea
                              placeholder="item_001&#10;item_002"
                              rows={2}
                              value={linkedReviewItems}
                              onChange={(e) => setLinkedReviewItems(e.target.value)}
                              className="text-xs font-mono"
                            />
                          </div>
                          <div className="flex flex-col gap-2">
                            <label className="text-xs font-semibold">linked_capa_ids (optional, one per line)</label>
                            <Textarea
                              placeholder="capa_001&#10;capa_002"
                              rows={2}
                              value={linkedCapaIds}
                              onChange={(e) => setLinkedCapaIds(e.target.value)}
                              className="text-xs font-mono"
                            />
                          </div>
                        </div>
                        {/* Submit button */}
                        <div className="flex items-center gap-3">
                          <Button
                            onClick={handleSubmitDecision}
                            disabled={isSubmitting}
                            size="lg"
                            className="w-full"
                          >
                            {isSubmitting ? (
                              <span className="flex items-center gap-2">
                                <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                                Submitting…
                              </span>
                            ) : (
                              "Submit Decision & Trigger Closure"
                            )}
                          </Button>
                        </div>

                        {decisionResult && (
                          <div className="flex items-start gap-2 rounded border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-800 dark:bg-green-950/20 dark:text-green-200 dark:border-green-900">
                            <span className="mt-0.5">✓</span>
                            <div>
                              <p className="font-medium">Decision submitted successfully</p>
                              <p className="mt-0.5 text-green-700 dark:text-green-300">
                                Closure {decisionResult.gate_closure_executed ? "executed" : "execution has issues"} — check the Closure tab.
                              </p>
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                )}
              </TabsContent>

              {/* ---- Closure Tab ---- */}
              <TabsContent value="closure" className="overflow-y-auto px-6 py-4">
                {!closureData ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <p className="text-sm text-muted-foreground">No closure data available.</p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-5">
                    {/* Rework Required — prominent alert at top */}
                    {closureData.final_gate_status === "rework_required" && (
                      <div className="flex flex-col gap-3 rounded-lg border-2 border-orange-400 bg-orange-50 p-4 dark:bg-orange-950/20 dark:border-orange-600">
                        <div className="flex items-center gap-2">
                          <span className="text-xl">⚠</span>
                          <div>
                            <p className="text-sm font-semibold text-orange-800 dark:text-orange-200">Rework Required</p>
                            <p className="text-xs text-orange-700 dark:text-orange-300">A new smoke-run must be triggered to address findings.</p>
                          </div>
                        </div>
                        <div className="flex flex-col gap-2">
                          <label className="text-xs font-medium text-orange-800 dark:text-orange-200">Reason for rework (optional)</label>
                          <Textarea
                            placeholder="Describe what needs to be reworked…"
                            rows={2}
                            value={reworkRationale}
                            onChange={(e) => setReworkRationale(e.target.value)}
                          />
                          <Button
                            variant="default"
                            className="bg-orange-600 hover:bg-orange-700"
                            onClick={handleRework}
                            disabled={isReworking}
                          >
                            {isReworking ? (
                              <span className="flex items-center gap-2">
                                <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                                Triggering Rework…
                              </span>
                            ) : (
                              "↻ Trigger Rework Run"
                            )}
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Summary cards */}
                    <div className="grid grid-cols-3 gap-3">
                      <Card>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-xs text-muted-foreground">Closure Status</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <Badge variant={closureData.closure_completed ? "default" : "secondary"} className={closureData.closure_completed ? "bg-emerald-600" : ""}>
                            {closureData.closure_completed ? "✓ completed" : "pending"}
                          </Badge>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-xs text-muted-foreground">Final Gate</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <GateBadge value={closureData.final_gate_status} />
                        </CardContent>
                      </Card>
                      <Card>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-xs text-muted-foreground">Provisional Gate</CardTitle>
                        </CardHeader>
                        <CardContent>
                          {closureData.provisional_gate ? (
                            <div className="flex flex-col gap-1">
                              <MachineBadge value={closureData.provisional_gate} />
                              {closureData.provisional_only && (
                                <Badge variant="outline" className="text-[10px] w-fit">provisional only</Badge>
                              )}
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </CardContent>
                      </Card>
                    </div>

                    {/* Human decision */}
                    {closureData.human_decision && (
                      <Card>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm">Human Decision</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center gap-2">
                              <HumanBadge value={closureData.human_decision.decision as string} />
                              <span className="text-xs text-muted-foreground">by {closureData.human_decision.reviewer as string}</span>
                            </div>
                            {(closureData.human_decision.rationale as string) && (
                              <p className="text-xs text-muted-foreground">{(closureData.human_decision.rationale as string)}</p>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Next action packet */}
                    {closureData.next_action && (
                      <Card>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm">Next Action Packet</CardTitle>
                        </CardHeader>
                        <CardContent className="flex flex-col gap-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline" className="text-xs">{closureData.next_action.packet_type ?? "—"}</Badge>
                            <HumanBadge value={closureData.next_action.decision} />
                            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                              <span>{closureData.next_action.total_actions_count} total actions</span>
                              {closureData.next_action.blocking_actions_count > 0 && (
                                <span className="flex items-center gap-1 rounded bg-red-100 px-1.5 py-0.5 text-red-700 dark:bg-red-950 dark:text-red-300">
                                  {closureData.next_action.blocking_actions_count} blocking
                                </span>
                              )}
                            </span>
                          </div>
                          {closureData.next_action.description && (
                            <p className="text-xs text-muted-foreground">{closureData.next_action.description}</p>
                          )}
                          {closureData.next_action.linked_capa_ids.length > 0 && (
                            <div className="flex flex-col gap-1.5">
                              <span className="text-xs font-medium">Linked CAPA IDs:</span>
                              <div className="flex flex-wrap gap-1">
                                {closureData.next_action.linked_capa_ids.map((id) => (
                                  <Badge key={id} variant="outline" className="text-xs font-mono">{id}</Badge>
                                ))}
                              </div>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    )}

                    {/* Gate closure report */}
                    {closureData.gate_closure_report && (
                      <StepSummaryCard
                        title="Gate Closure Report"
                        // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
                        summary={closureData.gate_closure_report as Record<string, unknown>}
                      />
                    )}

                    {/* Rework section — only show when NOT rework_required (already shown above) */}
                    {closureData.final_gate_status !== "rework_required" && (
                      <Card className="border-dashed">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm">Rework Loop</CardTitle>
                          <CardDescription>Trigger a new smoke-run if additional rework is needed.</CardDescription>
                        </CardHeader>
                        <CardContent className="flex flex-col gap-3">
                          <Textarea
                            placeholder="Reason for rework (optional)…"
                            rows={2}
                            value={reworkRationale}
                            onChange={(e) => setReworkRationale(e.target.value)}
                          />
                          <Button
                            variant="outline"
                            className="border-orange-300 text-orange-700 hover:bg-orange-50 dark:border-orange-700 dark:text-orange-300"
                            onClick={handleRework}
                            disabled={isReworking}
                          >
                            {isReworking ? "Triggering…" : "↻ Trigger Rework Run"}
                          </Button>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </>
        )}
      </div>
    </div>
  );
}
