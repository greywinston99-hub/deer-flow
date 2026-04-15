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

async function getClosure(threadId: string): Promise<ClosureResponse> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/closure/${threadId}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getArtifacts(threadId: string): Promise<{ thread_id: string; run_id: string; artifact_root_actual: string; artifacts: ArtifactSummary[] }> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/artifacts/${threadId}`);
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
  return new Date(timestamp * 1000).toLocaleString();
}

function GateBadge({ value }: { value: string | null }) {
  if (!value) return <Badge variant="secondary">unknown</Badge>;
  const variant = value === "pass" ? "default" : value === "conditional_pass" ? "secondary" : "destructive";
  return <Badge variant={variant}>{value}</Badge>;
}

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
      setThreads(data.threads);
    } catch (e) {
      toast.error(`Failed to load threads: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoadingThreads(false);
    }
  };

  const loadRuns = async (threadId: string) => {
    try {
      const data = await listRuns(threadId);
      setRunsForThread(data.runs);
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
        getClosure(threadId).catch(() => null),
        getArtifacts(threadId).catch(() => null),
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
        <div className="border-b p-4">
          <h2 className="mb-3 text-sm font-semibold">New Run</h2>
          <div className="flex flex-col gap-2">
            <Input
              placeholder="/path/to/project_profile.yaml"
              value={projectProfile}
              onChange={(e) => setProjectProfile(e.target.value)}
              className="text-xs"
            />
            <Input
              placeholder="input_root (optional)"
              value={inputRoot}
              onChange={(e) => setInputRoot(e.target.value)}
              className="text-xs"
            />
            <Button size="sm" onClick={handleStartRun} disabled={isRunning} className="w-full">
              {isRunning ? "Running..." : "Start Run"}
            </Button>
          </div>
        </div>

        {/* Thread list */}
        <div className="flex flex-1 flex-col overflow-y-auto">
          <div className="flex items-center justify-between px-4 py-2">
            <span className="text-xs font-semibold text-muted-foreground">THREADS</span>
            <Button variant="ghost" size="sm" onClick={loadThreads} disabled={loadingThreads} className="h-6 text-xs">
              {loadingThreads ? "..." : "↺"}
            </Button>
          </div>
          {threads.length === 0 && !loadingThreads && (
            <p className="px-4 py-2 text-xs text-muted-foreground">No threads yet. Start a run to create one.</p>
          )}
          {threads.map((thread) => (
            <div key={thread.thread_id}>
              <button
                className={`w-full px-4 py-2 text-left text-sm hover:bg-muted ${
                  selectedThreadId === thread.thread_id ? "bg-muted" : ""
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
                <div className="truncate font-mono text-xs">{thread.thread_id}</div>
                <div className="mt-0.5 flex items-center gap-1">
                  {thread.latest_has_closure && (
                    <Badge variant="default" className="text-[10px] px-1 py-0">closed</Badge>
                  )}
                  {thread.latest_final_recommended_gate && (
                    <GateBadge value={thread.latest_final_recommended_gate} />
                  )}
                </div>
                <div className="mt-0.5 text-[10px] text-muted-foreground">
                  {thread.latest_mode} · {formatDate(thread.updated_at).split(",")[0]}
                </div>
              </button>
              {/* Runs sub-list */}
              {selectedThreadId === thread.thread_id && runsForThread.length > 0 && (
                <div className="bg-muted/50">
                  {runsForThread.map((run) => (
                    <button
                      key={run.run_id}
                      className={`ml-4 w-[calc(100%-1rem)] border-l-2 px-3 py-1.5 text-left text-xs hover:bg-muted ${
                        selectedRunId === run.run_id ? "border-primary bg-muted" : "border-transparent"
                      }`}
                      onClick={() => setSelectedRunId(run.run_id)}
                    >
                      <div className="truncate font-mono">{run.run_id.slice(0, 12)}…</div>
                      <div className="text-[10px] text-muted-foreground">
                        {run.mode} · {run.executed_steps.length} steps
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
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
              <div>
                <h1 className="text-lg font-semibold">{runDetail.project_name ?? "RMF Review"}</h1>
                <p className="text-muted-foreground text-xs font-mono">
                  {runDetail.thread_id} / {runDetail.run_id.slice(0, 12)}…
                </p>
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
                <div className="flex flex-col gap-6">
                  {/* Gate summary cards */}
                  <div className="grid grid-cols-3 gap-4">
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Machine Recommendation</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <GateBadge value={runDetail.final_recommended_gate} />
                        {runDetail.provisional_gate && (
                          <div className="mt-2">
                            <span className="text-muted-foreground text-xs">Provisional: </span>
                            <GateBadge value={runDetail.provisional_gate} />
                            {runDetail.provisional_only && (
                              <Badge variant="secondary" className="ml-1 text-xs">provisional only</Badge>
                            )}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Human Decision</CardTitle>
                      </CardHeader>
                      <CardContent>
                        {runDetail.human_decision ? (
                          <div className="flex flex-col gap-1">
                            <GateBadge value={runDetail.human_decision.decision as string} />
                            <span className="text-muted-foreground text-xs">
                              by {(runDetail.human_decision.reviewer as string) ?? "unknown"}
                            </span>
                            <span className="text-muted-foreground text-xs">
                              {(runDetail.human_decision.simulated as boolean) ? "⚠ simulated" : "✓ confirmed"}
                            </span>
                          </div>
                        ) : (
                          <Badge variant="secondary">pending</Badge>
                        )}
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Final Gate Status</CardTitle>
                      </CardHeader>
                      <CardContent>
                        {runDetail.has_closure ? (
                          <GateBadge value={runDetail.gate_closure?.final_decision as string ?? null} />
                        ) : (
                          <Badge variant="secondary">not closed</Badge>
                        )}
                      </CardContent>
                    </Card>
                  </div>

                  {/* Steps executed */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Executed Steps ({runDetail.executed_steps.length})</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-1.5">
                        {runDetail.executed_steps.map((step) => (
                          <Badge key={step} variant="outline" className="text-xs">
                            {step}
                          </Badge>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Step summaries */}
                  {runDetail.intake_summary && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Intake Summary</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <pre className="text-muted-foreground overflow-x-auto text-xs">
                          {JSON.stringify(runDetail.intake_summary, null, 2)}
                        </pre>
                      </CardContent>
                    </Card>
                  )}

                  {runDetail.fmea_precheck_summary && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">FMEA Precheck</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <pre className="text-muted-foreground overflow-x-auto text-xs">
                          {JSON.stringify(runDetail.fmea_precheck_summary, null, 2)}
                        </pre>
                      </CardContent>
                    </Card>
                  )}

                  {runDetail.rmf_precheck_summary && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">RMF Precheck</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <pre className="text-muted-foreground overflow-x-auto text-xs">
                          {JSON.stringify(runDetail.rmf_precheck_summary, null, 2)}
                        </pre>
                      </CardContent>
                    </Card>
                  )}

                  {runDetail.dimension_summary && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Dimension Assessment</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <pre className="text-muted-foreground overflow-x-auto text-xs">
                          {JSON.stringify(runDetail.dimension_summary, null, 2)}
                        </pre>
                      </CardContent>
                    </Card>
                  )}

                  {runDetail.human_boundary_summary && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Human Review Queue ({(runDetail.human_boundary_summary.item_count as number) ?? 0} items)</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <pre className="text-muted-foreground overflow-x-auto text-xs">
                          {JSON.stringify(runDetail.human_boundary_summary, null, 2)}
                        </pre>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </TabsContent>

              {/* ---- Artifacts Tab ---- */}
              <TabsContent value="artifacts" className="overflow-y-auto px-6 py-4">
                <div className="flex flex-col gap-3">
                  {!artifactsData?.artifacts.length ? (
                    <p className="text-muted-foreground text-sm">No artifacts found.</p>
                  ) : (
                    artifactsData.artifacts.map((artifact) => (
                      <div
                        key={artifact.download_url}
                        className="flex items-center justify-between rounded border px-4 py-3"
                      >
                        <div className="flex flex-col gap-0.5">
                          <span className="font-medium text-sm">{artifact.artifact_name}</span>
                          <span className="text-muted-foreground text-xs">step: {artifact.step_id}</span>
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
                    ))
                  )}
                </div>
              </TabsContent>

              {/* ---- Human Decision Tab ---- */}
              <TabsContent value="decision" className="overflow-y-auto px-6 py-4">
                {runDetail.has_closure ? (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Decision Already Submitted</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-muted-foreground text-sm mb-3">
                        Gate closure has already been executed for this run.
                      </p>
                      <div className="flex flex-col gap-2">
                        <div>
                          <span className="text-muted-foreground text-xs">Final decision: </span>
                          <GateBadge value={runDetail.gate_closure?.final_decision as string ?? null} />
                        </div>
                        {runDetail.human_decision && (
                          <div>
                            <span className="text-muted-foreground text-xs">Reviewer: </span>
                            <span className="text-xs">{runDetail.human_decision.reviewer as string}</span>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Submit Human Gate Decision</CardTitle>
                      <CardDescription>
                        Submit your decision to trigger gate closure. This will NOT re-run steps 1–7.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="flex flex-col gap-2">
                          <label className="text-sm font-medium">decision *</label>
                          <Select value={decision} onValueChange={setDecision}>
                            <SelectTrigger>
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
                          <label className="text-sm font-medium">reviewer *</label>
                          <Input
                            placeholder="Reviewer name or ID"
                            value={reviewer}
                            onChange={(e) => setReviewer(e.target.value)}
                          />
                        </div>
                      </div>
                      <div className="flex flex-col gap-2">
                        <label className="text-sm font-medium">rationale</label>
                        <Textarea
                          placeholder="Reasoning behind the decision..."
                          rows={3}
                          value={rationale}
                          onChange={(e) => setRationale(e.target.value)}
                        />
                      </div>
                      <div className="flex flex-col gap-2">
                        <label className="text-sm font-medium">linked_review_items (one per line, optional)</label>
                        <Textarea
                          placeholder="item_001&#10;item_002"
                          rows={2}
                          value={linkedReviewItems}
                          onChange={(e) => setLinkedReviewItems(e.target.value)}
                        />
                      </div>
                      <div className="flex flex-col gap-2">
                        <label className="text-sm font-medium">linked_capa_ids (one per line, optional)</label>
                        <Textarea
                          placeholder="capa_001&#10;capa_002"
                          rows={2}
                          value={linkedCapaIds}
                          onChange={(e) => setLinkedCapaIds(e.target.value)}
                        />
                      </div>
                      <Button onClick={handleSubmitDecision} disabled={isSubmitting}>
                        {isSubmitting ? "Submitting..." : "Submit Decision & Trigger Closure"}
                      </Button>

                      {decisionResult && (
                        <div className="mt-2 rounded border bg-muted/50 p-3 text-xs">
                          <p><strong>Success:</strong> {String(decisionResult.success)}</p>
                          <p><strong>Closure executed:</strong> {String(decisionResult.gate_closure_executed)}</p>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              {/* ---- Closure Tab ---- */}
              <TabsContent value="closure" className="overflow-y-auto px-6 py-4">
                {!closureData ? (
                  <p className="text-muted-foreground text-sm">No closure data available.</p>
                ) : (
                  <div className="flex flex-col gap-6">
                    {/* Summary */}
                    <div className="grid grid-cols-3 gap-4">
                      <Card>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm">Closure Status</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <Badge variant={closureData.closure_completed ? "default" : "secondary"}>
                            {closureData.closure_completed ? "completed" : "pending"}
                          </Badge>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm">Final Gate</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <GateBadge value={closureData.final_gate_status} />
                        </CardContent>
                      </Card>
                      <Card>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm">Provisional Gate</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <GateBadge value={closureData.provisional_gate} />
                          {closureData.provisional_only && (
                            <Badge variant="secondary" className="ml-1 text-xs">provisional only</Badge>
                          )}
                        </CardContent>
                      </Card>
                    </div>

                    {/* Human decision */}
                    {closureData.human_decision && (
                      <Card>
                        <CardHeader>
                          <CardTitle className="text-sm">Human Decision</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <pre className="text-xs overflow-x-auto">
                            {JSON.stringify(closureData.human_decision, null, 2)}
                          </pre>
                        </CardContent>
                      </Card>
                    )}

                    {/* Next action */}
                    {closureData.next_action && (
                      <Card>
                        <CardHeader>
                          <CardTitle className="text-sm">Next Action Packet</CardTitle>
                        </CardHeader>
                        <CardContent className="flex flex-col gap-3">
                          <div className="flex items-center gap-3">
                            <Badge variant="outline">{closureData.next_action.packet_type}</Badge>
                            <Badge variant={closureData.next_action.decision === "pass" ? "default" : "destructive"}>
                              {closureData.next_action.decision}
                            </Badge>
                            <span className="text-muted-foreground text-xs">
                              {closureData.next_action.total_actions_count} actions
                              {closureData.next_action.blocking_actions_count > 0 && (
                                <span className="ml-1 text-destructive">
                                  ({closureData.next_action.blocking_actions_count} blocking)
                                </span>
                              )}
                            </span>
                          </div>
                          {closureData.next_action.description && (
                            <p className="text-muted-foreground text-xs">{closureData.next_action.description}</p>
                          )}
                          {closureData.next_action.linked_capa_ids.length > 0 && (
                            <div className="flex flex-col gap-1">
                              <span className="text-xs font-medium">Linked CAPA IDs:</span>
                              <div className="flex flex-wrap gap-1">
                                {closureData.next_action.linked_capa_ids.map((id) => (
                                  <Badge key={id} variant="outline" className="text-xs">{id}</Badge>
                                ))}
                              </div>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    )}

                    {/* Gate closure report */}
                    {closureData.gate_closure_report && (
                      <Card>
                        <CardHeader>
                          <CardTitle className="text-sm">Gate Closure Report</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <pre className="text-muted-foreground overflow-x-auto text-xs">
                            {JSON.stringify(closureData.gate_closure_report, null, 2)}
                          </pre>
                        </CardContent>
                      </Card>
                    )}

                    {/* Rework button */}
                    <Card className="border-dashed">
                      <CardHeader>
                        <CardTitle className="text-sm">Rework Loop</CardTitle>
                        <CardDescription>
                          Trigger a new smoke-run for rework_required decisions.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="flex flex-col gap-3">
                        <Textarea
                          placeholder="Reason for rework (optional)..."
                          rows={2}
                          value={reworkRationale}
                          onChange={(e) => setReworkRationale(e.target.value)}
                        />
                        <Button
                          variant="destructive"
                          onClick={handleRework}
                          disabled={isReworking}
                        >
                          {isReworking ? "Triggering..." : "Trigger Rework Run"}
                        </Button>
                      </CardContent>
                    </Card>
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
