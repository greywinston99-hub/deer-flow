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

interface CERStatusResponse {
  thread_id: string;
  run_id: string | null;
  mode: string | null;
  workflow_name: string | null;
  executed_steps: string[];
  artifact_root_virtual: string | null;
  artifact_root_actual: string | null;
  has_review_package: boolean;
  has_gate_closure_report: boolean;
  has_human_decision: boolean;
  has_human_review_queue: boolean;
  has_provisional_gate: boolean;
  has_five_dimension_review: boolean;
  has_hf_check: boolean;
  has_cross_doc_consistency: boolean;
  final_recommended_gate: string | null;
  provisional_gate: string | null;
  human_gate_required: boolean | null;
  provisional_only: boolean | null;
  human_decision_value: string | null;
  human_decision_reviewer: string | null;
  human_decision_simulated: boolean | null;
  human_decision_date: string | null;
  final_gate_status: string | null;
  closure_completed: boolean;
}

interface ReviewItem {
  item_id: string;
  topic: string;
  priority: string;
  layer: number;
  reviewer_focus: string;
}

interface HumanBoundarySummary {
  item_count: number;
  items: ReviewItem[];
  recommended_gate: string | null;
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
  human_gate_required: boolean;
  intake_summary: Record<string, unknown> | null;
  hf_check_summary: Record<string, unknown> | null;
  five_dim_summary: Record<string, unknown> | null;
  cross_doc_summary: Record<string, unknown> | null;
  human_boundary_summary: HumanBoundarySummary | null;
  review_package_summary: Record<string, unknown> | null;
  final_recommended_gate: string | null;
  provisional_gate: string | null;
  provisional_only: boolean | null;
  human_gate_required_flag: boolean | null;
  human_decision: Record<string, unknown> | null;
  gate_closure: Record<string, unknown> | null;
  next_action_packet: Record<string, unknown> | null;
  has_closure: boolean;
  closure_completed: boolean;
  // P0.5 quality-hardened sub-assessments
  equivalence_assessment_summary: EquivalenceAssessmentSummary | null;
  literature_quality_summary: LiteratureQualitySummary | null;
}

interface EquivalenceAssessmentSummary {
  assessment_id: string | null;
  predicate_device: string | null;
  overall_tier: string | null;
  dimensions_passed_count: number | null;
  dimensions_failed_count: number | null;
  mandatory_human_review: boolean | null;
  top_risks: string[];
}

interface LiteratureQualitySummary {
  literature_search_conducted: boolean | null;
  included_studies_count: number | null;
  high_quality_count: number | null;
  medium_quality_count: number | null;
  low_quality_count: number | null;
  very_low_quality_count: number | null;
  insufficient_info_count: number | null;
  dominant_tier: string | null;
  requires_human_review: boolean | null;
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
  const r = await fetch(`${getBackendBaseURL()}/api/cer/runs`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function listRuns(threadId: string): Promise<{ thread_id: string; runs: RunSummaryItem[] }> {
  const r = await fetch(`${getBackendBaseURL()}/api/cer/runs/${threadId}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getRunDetail(threadId: string, runId: string): Promise<RichRunResponse> {
  const r = await fetch(`${getBackendBaseURL()}/api/cer/run/${threadId}/${runId}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getStatus(threadId: string): Promise<CERStatusResponse> {
  const r = await fetch(`${getBackendBaseURL()}/api/cer/status/${threadId}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getClosure(threadId: string): Promise<ClosureResponse> {
  const r = await fetch(`${getBackendBaseURL()}/api/cer/closure/${threadId}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function submitHumanDecision(body: {
  thread_id: string;
  decision: string;
  reviewer: string;
  rationale: string;
  linked_review_items: string[];
  linked_capa_ids: string[];
}): Promise<HumanDecisionResponse> {
  const r = await fetch(`${getBackendBaseURL()}/api/cer/human-decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function triggerRework(threadId: string, rationale: string): Promise<{ thread_id: string; run_id: string }> {
  const r = await fetch(`${getBackendBaseURL()}/api/cer/rework`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, rationale }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function startCERReview(projectProfile: string, threadId?: string): Promise<{ thread_id: string; run_id: string }> {
  const r = await fetch(`${getBackendBaseURL()}/api/cer/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_profile: projectProfile, thread_id: threadId }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function GateBadge({ gate }: { gate: string | null }) {
  if (!gate) return null;
  const variants: Record<string, string> = {
    pass: "bg-green-100 text-green-800",
    conditional_pass: "bg-yellow-100 text-yellow-800",
    rework_required: "bg-red-100 text-red-800",
    pending: "bg-gray-100 text-gray-800",
  };
  const labels: Record<string, string> = {
    pass: "通过",
    conditional_pass: "有条件通过",
    rework_required: "需整改",
    pending: "待审核",
  };
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${variants[gate] || "bg-gray-100"}`}>{labels[gate] || gate}</span>;
}

function LayerBadge({ layer }: { layer: number }) {
  if (layer === 3) return <span className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-800 text-xs font-medium">L3</span>;
  if (layer === 2) return <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 text-xs font-medium">L2</span>;
  return <span className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-800 text-xs font-medium">L1</span>;
}

function SeverityBadge({ severity }: { severity: string }) {
  const variants: Record<string, string> = {
    high: "bg-red-100 text-red-800",
    medium: "bg-yellow-100 text-yellow-800",
    low: "bg-green-100 text-green-800",
    none: "bg-gray-100 text-gray-800",
  };
  return <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${variants[severity] || "bg-gray-100"}`}>{severity.toUpperCase()}</span>;
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function CERWorkbenchPage() {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [selectedThread, setSelectedThread] = useState<string | null>(null);
  const [runs, setRuns] = useState<RunSummaryItem[]>([]);
  const [selectedRun, setSelectedRun] = useState<{ threadId: string; runId: string } | null>(null);
  const [runDetail, setRunDetail] = useState<RichRunResponse | null>(null);
  const [closure, setClosure] = useState<ClosureResponse | null>(null);
  const [loadingThreads, setLoadingThreads] = useState(false);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // New review form
  const [projectProfile, setProjectProfile] = useState("");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");

  // Human decision form
  const [decision, setDecision] = useState<string>("conditional_pass");
  const [reviewer, setReviewer] = useState("");
  const [rationale, setRationale] = useState("");
  const [submittingDecision, setSubmittingDecision] = useState(false);

  // Rework form
  const [reworkRationale, setReworkRationale] = useState("");
  const [reworking, setReworking] = useState(false);

  const loadThreads = useCallback(async () => {
    setLoadingThreads(true);
    try {
      const data = await listThreads();
      setThreads(data.threads || []);
    } catch {
      toast.error("Failed to load CER threads");
    } finally {
      setLoadingThreads(false);
    }
  }, []);

  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  const loadRuns = useCallback(async (threadId: string) => {
    setLoadingRuns(true);
    try {
      const data = await listRuns(threadId);
      setRuns(data.runs || []);
    } catch {
      toast.error("Failed to load runs");
    } finally {
      setLoadingRuns(false);
    }
  }, []);

  const loadDetail = useCallback(async (threadId: string, runId: string) => {
    setLoadingDetail(true);
    try {
      const [detail, closureData] = await Promise.all([
        getRunDetail(threadId, runId),
        getClosure(threadId).catch(() => null),
      ]);
      setRunDetail(detail);
      setClosure(closureData);
    } catch {
      toast.error("Failed to load run detail");
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const handleSelectThread = useCallback(async (threadId: string) => {
    setSelectedThread(threadId);
    setSelectedRun(null);
    setRunDetail(null);
    setClosure(null);
    await loadRuns(threadId);
  }, [loadRuns]);

  const handleSelectRun = useCallback(async (threadId: string, runId: string) => {
    setSelectedRun({ threadId, runId });
    await loadDetail(threadId, runId);
  }, [loadDetail]);

  const handleStartReview = useCallback(async () => {
    if (!projectProfile.trim()) {
      setStartError("Please enter a project profile path");
      return;
    }
    setStarting(true);
    setStartError("");
    try {
      const result = await startCERReview(projectProfile.trim());
      toast.success(`CER review started: ${result.run_id}`);
      await loadThreads();
      await handleSelectThread(result.thread_id);
      await loadRuns(result.thread_id);
    } catch (e) {
      setStartError(`Failed to start review: ${e}`);
    } finally {
      setStarting(false);
    }
  }, [projectProfile, loadThreads, handleSelectThread, loadRuns]);

  const handleSubmitDecision = useCallback(async () => {
    if (!selectedThread) return;
    if (!reviewer.trim()) {
      toast.error("Please enter reviewer name");
      return;
    }
    setSubmittingDecision(true);
    try {
      const result = await submitHumanDecision({
        thread_id: selectedThread,
        decision,
        reviewer: reviewer.trim(),
        rationale: rationale.trim(),
        linked_review_items: runDetail?.human_boundary_summary?.items?.map((i: { item_id: string }) => i.item_id) || [],
        linked_capa_ids: [],
      });
      if (result.success) {
        toast.success("Human decision submitted and closure executed");
        await loadDetail(selectedThread, selectedRun!.runId);
        await loadThreads();
      } else {
        toast.error("Decision submission had issues");
      }
    } catch (e) {
      toast.error(`Failed to submit decision: ${e}`);
    } finally {
      setSubmittingDecision(false);
    }
  }, [selectedThread, selectedRun, decision, reviewer, rationale, runDetail, loadDetail, loadThreads]);

  const handleRework = useCallback(async () => {
    if (!selectedThread) return;
    setReworking(true);
    try {
      const result = await triggerRework(selectedThread, reworkRationale);
      toast.success("Rework triggered");
      await handleSelectThread(result.thread_id);
    } catch (e) {
      toast.error(`Rework failed: ${e}`);
    } finally {
      setReworking(false);
    }
  }, [selectedThread, reworkRationale, handleSelectThread]);

  const fiveDimData = runDetail?.five_dim_summary?.dimensions as Record<string, { status: string; label: string; requires_human_review: boolean }> | undefined;
  const hfFindings = (runDetail?.hf_check_summary?.findings || []) as Array<{ hf_id: string; label: string; severity: string; detail: string }>;
  const crossDocConflicts = (runDetail?.cross_doc_summary?.conflicts || []) as Array<{ check_group: string; label: string; severity: string; detail: string }>;
  const humanReviewItems = (runDetail?.human_boundary_summary?.items || []) as Array<{ item_id: string; topic: string; priority: string; layer: number; reviewer_focus: string }>;
  const eqSummary = runDetail?.equivalence_assessment_summary as EquivalenceAssessmentSummary | null | undefined;
  const litSummary = runDetail?.literature_quality_summary as LiteratureQualitySummary | null | undefined;
  const pmcfMappings = (runDetail?.cross_doc_summary?.pmcf_cer_mapping || []) as Array<{ mapping_id: string; cer_claim_or_risk: string; pmcf_support_item: string; consistency_status: string; severity: string }>;
  const reviewSummary = runDetail?.review_package_summary as { total_findings: number; findings_by_severity: Record<string, number> } | undefined;

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-80 border-r flex flex-col">
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold">CER Review</h2>
          <p className="text-xs text-muted-foreground">Clinical Evaluation Report</p>
        </div>

        {/* New Review Form */}
        <div className="p-3 border-b space-y-2">
          <Input
            placeholder="/path/to/project_profile.yaml"
            value={projectProfile}
            onChange={(e) => setProjectProfile(e.target.value)}
            className="text-xs h-8"
          />
          {startError && <p className="text-xs text-red-500">{startError}</p>}
          <Button
            size="sm"
            className="w-full"
            onClick={handleStartReview}
            disabled={starting}
          >
            {starting ? "Starting..." : "New CER Review"}
          </Button>
        </div>

        {/* Thread List */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-2">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-muted-foreground">Threads</span>
              <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={loadThreads}>
                Refresh
              </Button>
            </div>
            {loadingThreads && <p className="text-xs text-muted-foreground p-2">Loading...</p>}
            {!loadingThreads && threads.length === 0 && (
              <p className="text-xs text-muted-foreground p-2">No CER reviews yet</p>
            )}
            {threads.map((thread) => (
              <button
                key={thread.thread_id}
                className={`w-full text-left px-2 py-1.5 rounded text-xs mb-1 ${
                  selectedThread === thread.thread_id ? "bg-primary/10" : "hover:bg-muted"
                }`}
                onClick={() => handleSelectThread(thread.thread_id)}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono truncate">{thread.thread_id}</span>
                  <GateBadge gate={thread.latest_final_gate_status || thread.latest_final_recommended_gate} />
                </div>
                <div className="text-muted-foreground truncate">
                  {thread.latest_mode || "—"} · {thread.latest_run_id || "no runs"}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        {!selectedThread && (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <h3 className="text-lg font-medium mb-2">CER Review Workbench</h3>
              <p className="text-sm">Select a thread or start a new CER review</p>
            </div>
          </div>
        )}

        {selectedThread && !selectedRun && (
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold">Thread: {selectedThread}</h3>
                <p className="text-sm text-muted-foreground">{runs.length} run(s)</p>
              </div>
            </div>

            {loadingRuns && <p className="text-sm text-muted-foreground">Loading runs...</p>}
            {!loadingRuns && runs.length === 0 && (
              <p className="text-sm text-muted-foreground">No runs found</p>
            )}
            <div className="space-y-2">
              {runs.map((run) => (
                <Card key={run.run_id} className="cursor-pointer hover:bg-muted/50" onClick={() => handleSelectRun(selectedThread, run.run_id)}>
                  <CardContent className="p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-mono text-sm font-medium">{run.run_id}</span>
                        <span className="ml-2 text-xs text-muted-foreground">{run.mode}</span>
                      </div>
                      <Badge variant="outline" className="text-xs">{run.executed_steps.length} steps</Badge>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {new Date(run.updated_at * 1000).toLocaleString()}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {selectedThread && selectedRun && runDetail && (
          <div className="p-4">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold">CER Review: {runDetail.run_id}</h3>
                <p className="text-sm text-muted-foreground">
                  Thread: {selectedThread} · Mode: {runDetail.mode}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {runDetail.provisional_gate && (
                  <div className="text-right">
                    <p className="text-xs text-muted-foreground">Provisional Gate</p>
                    <GateBadge gate={runDetail.provisional_gate} />
                  </div>
                )}
                {runDetail.human_decision && (
                  <div className="text-right">
                    <p className="text-xs text-muted-foreground">Human Decision</p>
                    <GateBadge gate={(runDetail.human_decision as { decision: string }).decision} />
                  </div>
                )}
                {runDetail.gate_closure && (
                  <div className="text-right">
                    <p className="text-xs text-muted-foreground">Final Gate</p>
                    <GateBadge gate={(runDetail.gate_closure as { final_decision: string }).final_decision} />
                  </div>
                )}
              </div>
            </div>

            <Tabs defaultValue="overview">
              <TabsList className="mb-4">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="hf">HF Checks</TabsTrigger>
                <TabsTrigger value="dimensions">5 Dimensions</TabsTrigger>
                <TabsTrigger value="consistency">Cross-Doc</TabsTrigger>
                <TabsTrigger value="review">Review Queue</TabsTrigger>
                <TabsTrigger value="decision">Decision</TabsTrigger>
              </TabsList>

              {/* Overview */}
              <TabsContent value="overview">
                <div className="grid grid-cols-2 gap-4">
                  {/* Review Summary */}
                  {reviewSummary && (
                    <Card>
                      <CardHeader><CardTitle>Review Summary</CardTitle></CardHeader>
                      <CardContent>
                        <div className="space-y-2 text-sm">
                          <div>Total Findings: <strong>{reviewSummary.total_findings}</strong></div>
                          <div className="flex gap-2">
                            {Object.entries(reviewSummary.findings_by_severity || {}).map(([sev, count]) => (
                              <SeverityBadge key={sev} severity={sev} />
                            ))}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Executed Steps */}
                  <Card>
                    <CardHeader><CardTitle>Executed Steps</CardTitle></CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-1">
                        {runDetail.executed_steps.map((step) => (
                          <Badge key={step} variant="outline" className="text-xs">{step}</Badge>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Five Dimension Overview */}
                  {fiveDimData && (
                    <Card className="col-span-2">
                      <CardHeader><CardTitle>Five-Dimension Overview</CardTitle></CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-5 gap-2">
                          {Object.entries(fiveDimData).map(([dimId, dim]) => (
                            <div key={dimId} className="text-center p-2 border rounded">
                              <div className="text-xs font-mono text-muted-foreground">{dimId}</div>
                              <div className="text-sm font-medium mt-1">{dim.label}</div>
                              <GateBadge gate={dim.status} />
                              {dim.requires_human_review && <div className="text-xs text-purple-600 mt-1">L3</div>}
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </TabsContent>

              {/* HF Checks */}
              <TabsContent value="hf">
                <Card>
                  <CardHeader>
                    <CardTitle>High-Frequency Checks</CardTitle>
                    <CardDescription>CER HF scan results (8 checks)</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {hfFindings.length === 0 && <p className="text-sm text-muted-foreground">No HF findings</p>}
                    <div className="space-y-2">
                      {hfFindings.map((f) => (
                        <div key={f.hf_id} className="p-3 border rounded">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <SeverityBadge severity={f.severity} />
                              <span className="font-mono text-xs">{f.hf_id}</span>
                              <span className="text-sm font-medium">{f.label}</span>
                            </div>
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">{f.detail}</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* P0.5: Equivalence Assessment (HF-005) */}
                {eqSummary && (
                  <Card className="mt-4">
                    <CardHeader>
                      <CardTitle>Equivalence Assessment (HF-005)</CardTitle>
                      <CardDescription>Structured 3-dimension equivalence matrix — human judgment required</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-xs text-muted-foreground">Predicate Device</div>
                          <div className="text-sm font-medium">{eqSummary.predicate_device || "Not identified"}</div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Overall Tier</div>
                          <div className="text-sm font-medium">
                            <span className={eqSummary.overall_tier === "unsupported" ? "text-red-600" : eqSummary.overall_tier === "likely_supported" ? "text-green-600" : "text-yellow-600"}>
                              {eqSummary.overall_tier || "unknown"}
                            </span>
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Dimensions Passed / Failed</div>
                          <div className="text-sm font-medium">
                            {eqSummary.dimensions_passed_count ?? "?"} / {eqSummary.dimensions_failed_count ?? "?"}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Human Review Required</div>
                          <div className="text-sm font-medium">{eqSummary.mandatory_human_review ? "Yes (Layer 3)" : "No"}</div>
                        </div>
                      </div>
                      {eqSummary.top_risks && eqSummary.top_risks.length > 0 && (
                        <div className="mt-3">
                          <div className="text-xs text-muted-foreground mb-1">Top Risks</div>
                          {eqSummary.top_risks.map((risk, i) => (
                            <div key={i} className="text-xs text-red-600">• {risk}</div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* P0.5: Literature Quality (HF-004) */}
                {litSummary && (
                  <Card className="mt-4">
                    <CardHeader>
                      <CardTitle>Literature Quality (HF-004)</CardTitle>
                      <CardDescription>Structured literature quality scoring — human judgment required</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-xs text-muted-foreground">Dominant Tier</div>
                          <div className="text-sm font-medium">
                            <span className={litSummary.dominant_tier === "insufficient_information" ? "text-red-600" : litSummary.dominant_tier === "very_low" ? "text-orange-600" : litSummary.dominant_tier === "low" ? "text-yellow-600" : litSummary.dominant_tier === "medium" ? "text-blue-600" : "text-green-600"}>
                              {litSummary.dominant_tier || "unknown"}
                            </span>
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Search Conducted</div>
                          <div className="text-sm font-medium">{litSummary.literature_search_conducted ? "Yes" : "No / Unknown"}</div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Evidence Units</div>
                          <div className="text-sm font-medium">{litSummary.included_studies_count ?? 0}</div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Human Review Required</div>
                          <div className="text-sm font-medium">{litSummary.requires_human_review ? "Yes (Layer 3)" : "No"}</div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">High Quality</div>
                          <div className="text-sm font-medium text-green-600">{litSummary.high_quality_count ?? 0}</div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Medium Quality</div>
                          <div className="text-sm font-medium text-blue-600">{litSummary.medium_quality_count ?? 0}</div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Low Quality</div>
                          <div className="text-sm font-medium text-yellow-600">{litSummary.low_quality_count ?? 0}</div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Insufficient Info</div>
                          <div className="text-sm font-medium text-red-600">{litSummary.insufficient_info_count ?? 0}</div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              {/* Five Dimensions */}
              <TabsContent value="dimensions">
                <div className="space-y-4">
                  {fiveDimData && Object.entries(fiveDimData).map(([dimId, dim]) => (
                    <Card key={dimId}>
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <div>
                            <CardTitle className="font-mono">{dimId} — {dim.label}</CardTitle>
                            <CardDescription>
                              {dim.requires_human_review ? (
                                <span className="text-purple-600 font-medium">⚠ Layer 3 — Human judgment required</span>
                              ) : (
                                <span>Automated review</span>
                              )}
                            </CardDescription>
                          </div>
                          <GateBadge gate={dim.status} />
                        </div>
                      </CardHeader>
                    </Card>
                  ))}
                </div>
              </TabsContent>

              {/* Cross-Doc Consistency */}
              <TabsContent value="consistency">
                <Card>
                  <CardHeader>
                    <CardTitle>Cross-Document Consistency</CardTitle>
                    <CardDescription>4 consistency groups: CER↔IFU, CER↔RMF, CER↔CEP, CER↔PMCF</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {crossDocConflicts.length === 0 && <p className="text-sm text-muted-foreground">No conflicts</p>}
                    <div className="space-y-2">
                      {crossDocConflicts.map((c) => (
                        <div key={c.check_group} className="p-3 border rounded">
                          <div className="flex items-center gap-2">
                            <SeverityBadge severity={c.severity} />
                            <span className="font-medium text-sm">{c.label}</span>
                            <span className="text-xs text-muted-foreground font-mono">{c.check_group}</span>
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">{c.detail}</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* P0.5: PMCF-CER Chapter-Level Mapping */}
                {pmcfMappings.length > 0 && (
                  <Card className="mt-4">
                    <CardHeader>
                      <CardTitle>PMCF↔CER Mapping (Task C)</CardTitle>
                      <CardDescription>Section-level claim mapping between CER and PMCF plan</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {pmcfMappings.map((m) => (
                          <div key={m.mapping_id} className="p-3 border rounded">
                            <div className="flex items-center gap-2">
                              <SeverityBadge severity={m.severity} />
                              <span className="font-mono text-xs">{m.mapping_id}</span>
                              <span className="text-sm font-medium">{m.cer_claim_or_risk}</span>
                            </div>
                            <div className="text-xs text-muted-foreground mt-1">
                              <span className="text-green-600">CER claims</span> → <span className="text-blue-600">PMCF: {m.pmcf_support_item}</span>
                            </div>
                            <div className="text-xs mt-1">
                              Status: <span className={m.consistency_status === "aligned" ? "text-green-600" : m.consistency_status === "missing_support" ? "text-red-600" : "text-yellow-600"}>{m.consistency_status}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              {/* Review Queue */}
              <TabsContent value="review">
                <Card>
                  <CardHeader>
                    <CardTitle>Human Review Queue</CardTitle>
                    <CardDescription>
                      {humanReviewItems.length} items ·{" "}
                      {humanReviewItems.filter((i) => i.priority === "high").length} high priority ·{" "}
                      {humanReviewItems.filter((i) => i.layer === 3).length} Layer 3
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {humanReviewItems.length === 0 && <p className="text-sm text-muted-foreground">No items</p>}
                    <div className="space-y-2">
                      {humanReviewItems.map((item) => (
                        <div key={item.item_id} className="p-3 border rounded">
                          <div className="flex items-center gap-2 mb-1">
                            <LayerBadge layer={item.layer || 2} />
                            <span className="text-xs font-mono text-muted-foreground">{item.item_id}</span>
                            <Badge variant={item.priority === "high" ? "destructive" : "secondary"} className="text-xs">
                              {item.priority}
                            </Badge>
                            <span className="text-sm font-medium">{item.topic}</span>
                          </div>
                          <p className="text-xs text-muted-foreground">{item.reviewer_focus}</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Human Decision */}
              <TabsContent value="decision">
                <div className="space-y-4">
                  {/* Existing Decision */}
                  {runDetail.human_decision && (
                    <Card>
                      <CardHeader><CardTitle>Existing Human Decision</CardTitle></CardHeader>
                      <CardContent>
                        <div className="space-y-2 text-sm">
                          <div className="flex items-center gap-2">
                            <GateBadge gate={(runDetail.human_decision as { decision: string }).decision} />
                            <span>Decision by {(runDetail.human_decision as { reviewer: string }).reviewer}</span>
                          </div>
                          {(runDetail.human_decision as { rationale: string }).rationale && (
                            <p className="text-muted-foreground">{(runDetail.human_decision as { rationale: string }).rationale}</p>
                          )}
                          <p className="text-xs text-muted-foreground">
                            Date: {(runDetail.human_decision as { decision_date: string }).decision_date || "—"}
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Submit New Decision */}
                  {!runDetail.human_decision && (
                    <Card>
                      <CardHeader>
                        <CardTitle>Submit Human Decision</CardTitle>
                        <CardDescription>
                          Review the findings above and submit your gate decision.
                          Layer 3 items (equivalence, data sufficiency, benefit-risk) require your explicit judgment.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="space-y-2">
                          <label className="text-sm font-medium">Decision</label>
                          <Select value={decision} onValueChange={setDecision}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="pass">Pass — 通过</SelectItem>
                              <SelectItem value="conditional_pass">Conditional Pass — 有条件通过</SelectItem>
                              <SelectItem value="rework_required">Rework Required — 需整改</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <label className="text-sm font-medium">Reviewer</label>
                          <Input
                            placeholder="Reviewer name or ID"
                            value={reviewer}
                            onChange={(e) => setReviewer(e.target.value)}
                          />
                        </div>
                        <div className="space-y-2">
                          <label className="text-sm font-medium">Rationale</label>
                          <Textarea
                            placeholder="Decision rationale..."
                            value={rationale}
                            onChange={(e) => setRationale(e.target.value)}
                            rows={4}
                          />
                        </div>
                        <div className="bg-purple-50 border border-purple-200 rounded p-3">
                          <p className="text-xs text-purple-700">
                            <strong>⚠ Layer 3 Items:</strong> 临床等效性最终成立与否、临床数据充分性最终判定、
                            受益-风险综合评估最终结论 — 这些必须由您的人工判断决定，不得由系统自动终判。
                          </p>
                        </div>
                        <Button
                          className="w-full"
                          onClick={handleSubmitDecision}
                          disabled={submittingDecision || !reviewer.trim()}
                        >
                          {submittingDecision ? "Submitting..." : "Submit Human Decision"}
                        </Button>
                      </CardContent>
                    </Card>
                  )}

                  {/* Closure */}
                  {closure && closure.closure_completed && (
                    <Card>
                      <CardHeader><CardTitle>Gate Closure</CardTitle></CardHeader>
                      <CardContent>
                        <div className="space-y-2 text-sm">
                          <div className="flex items-center gap-2">
                            <GateBadge gate={closure.final_gate_status} />
                            <span>Final Gate Status</span>
                          </div>
                          {closure.next_action && (
                            <div>
                              <p className="font-medium">Next Action: {closure.next_action.description}</p>
                              {closure.next_action.blocking_actions_count > 0 && (
                                <Badge variant="destructive" className="mt-1">Blocking</Badge>
                              )}
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Rework */}
                  {runDetail.gate_closure && (runDetail.gate_closure as { final_decision: string }).final_decision === "rework_required" && (
                    <Card>
                      <CardHeader><CardTitle>Rework</CardTitle></CardHeader>
                      <CardContent className="space-y-4">
                        <Textarea
                          placeholder="Rework rationale..."
                          value={reworkRationale}
                          onChange={(e) => setReworkRationale(e.target.value)}
                          rows={3}
                        />
                        <Button
                          className="w-full"
                          variant="destructive"
                          onClick={handleRework}
                          disabled={reworking}
                        >
                          {reworking ? "Triggering..." : "Trigger Rework Run"}
                        </Button>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          </div>
        )}
      </div>
    </div>
  );
}
