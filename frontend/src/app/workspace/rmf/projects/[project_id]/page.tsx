"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
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

interface ReviewCycle {
  cycle_id: string;
  cycle_number: number;
  thread_id: string;
  run_id: string | null;
  mode: string;
  started_at: string;
  completed_at: string | null;
  machine_recommendation: string | null;
  human_decision: string | null;
  final_gate: string | null;
  status: string;
}

interface HumanDecisionAudit {
  decision_id: string;
  reviewer: string;
  decision: string;
  decision_date: string;
  rationale: string;
  linked_review_items: string[];
  linked_capa_ids: string[];
  source_thread_id: string;
  source_run_id: string;
  source_cycle_id: string;
}

interface ProjectDetail {
  project_id: string;
  project_name: string;
  product_name: string;
  project_profile_path: string;
  input_root: string;
  current_status: string;
  created_at: string;
  updated_at: string;
  latest_thread_id: string | null;
  latest_run_id: string | null;
  latest_gate_status: string | null;
  latest_human_decision: string | null;
  latest_machine_recommendation: string | null;
  total_runs: number;
  total_rework_rounds: number;
  review_cycles: ReviewCycle[];
  human_decision_history: HumanDecisionAudit[];
  audit_trail: HumanDecisionAudit[];
}

interface StartRunResponse {
  project_id: string;
  cycle_id: string;
  cycle_number: number;
  thread_id: string;
  run_id: string;
  status: string;
}

interface HumanDecisionSubmitRequest {
  decision: string;
  reviewer: string;
  rationale: string;
  linked_review_items: string[];
  linked_capa_ids: string[];
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function getProjectDetail(projectId: string): Promise<ProjectDetail> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/projects/${projectId}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function startRunInProject(projectId: string): Promise<StartRunResponse> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/projects/${projectId}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail ?? `HTTP ${r.status}`);
  }
  return r.json();
}

async function submitHumanDecision(
  projectId: string,
  body: HumanDecisionSubmitRequest,
): Promise<{ success: boolean; decision_recorded: boolean; project_status: string }> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/projects/${projectId}/human-decision`, {
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

async function updateProjectStatus(projectId: string, status: string): Promise<void> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-500",
  ready_to_run: "bg-blue-500",
  running: "bg-yellow-500",
  pending_human_decision: "bg-orange-500",
  rework_required: "bg-red-500",
  conditional_pass: "bg-amber-500",
  passed: "bg-green-500",
  closed: "bg-gray-700",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  ready_to_run: "Ready to Run",
  running: "Running",
  pending_human_decision: "Pending Human Decision",
  rework_required: "Rework Required",
  conditional_pass: "Conditional Pass",
  passed: "Passed",
  closed: "Closed",
};

function formatDate(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function gateBadge(gate: string | null | undefined): React.ReactNode {
  if (!gate) return <span className="text-muted-foreground">—</span>;
  const color =
    gate === "pass" ? "bg-green-100 text-green-800" :
    gate === "rework_required" ? "bg-red-100 text-red-800" :
    gate === "conditional_pass" ? "bg-amber-100 text-amber-800" :
    "bg-gray-100";
  return <Badge className={color}>{gate}</Badge>;
}

// ---------------------------------------------------------------------------
// Cycle Row
// ---------------------------------------------------------------------------

function CycleRow({ cycle }: { cycle: ReviewCycle }) {
  const statusColor =
    cycle.status === "running" ? "border-yellow-400" :
    cycle.status === "rework_pending" ? "border-red-400" :
    "border-green-400";

  return (
    <div className={`border-l-4 ${statusColor} pl-4 py-2 space-y-1`}>
      <div className="flex items-center gap-2">
        <span className="font-medium">Round {cycle.cycle_number}</span>
        <Badge variant="outline">{cycle.cycle_id}</Badge>
        <Badge className={cycle.status === "running" ? "bg-yellow-500" : cycle.status === "rework_pending" ? "bg-red-500" : "bg-green-500"}>
          {cycle.status}
        </Badge>
      </div>
      <div className="grid grid-cols-3 gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
        <span>Thread:</span>
        <span className="font-mono col-span-2 truncate">{cycle.thread_id}</span>
        <span>Run ID:</span>
        <span className="font-mono col-span-2 truncate">{cycle.run_id ?? "—"}</span>
        <span>Started:</span>
        <span className="col-span-2">{formatDate(cycle.started_at)}</span>
        <span>Completed:</span>
        <span className="col-span-2">{formatDate(cycle.completed_at ?? "")}</span>
        <span>Machine Rec:</span>
        <span className="col-span-2">{gateBadge(cycle.machine_recommendation)}</span>
        <span>Human Decision:</span>
        <span className="col-span-2">{gateBadge(cycle.human_decision)}</span>
        <span>Final Gate:</span>
        <span className="col-span-2">{gateBadge(cycle.final_gate)}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Human Decision Form
// ---------------------------------------------------------------------------

function HumanDecisionForm({
  projectId,
  latestThreadId,
  onSubmitted,
}: {
  projectId: string;
  latestThreadId: string | null;
  onSubmitted: () => void;
}) {
  const [decision, setDecision] = useState<string>("");
  const [reviewer, setReviewer] = useState("");
  const [rationale, setRationale] = useState("");
  const [linkedItems, setLinkedItems] = useState("");
  const [linkedCapaIds, setLinkedCapaIds] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!decision || !reviewer) return;
    setLoading(true);
    try {
      await submitHumanDecision(projectId, {
        decision,
        reviewer,
        rationale,
        linked_review_items: linkedItems.split("\n").map((s) => s.trim()).filter(Boolean),
        linked_capa_ids: linkedCapaIds.split("\n").map((s) => s.trim()).filter(Boolean),
      });
      toast.success("Human decision submitted");
      onSubmitted();
    } catch (err) {
      toast.error(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="text-sm font-medium">Decision *</label>
        <Select value={decision} onValueChange={setDecision} required>
          <SelectTrigger className="mt-1">
            <SelectValue placeholder="Select decision" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="pass">Pass</SelectItem>
            <SelectItem value="conditional_pass">Conditional Pass</SelectItem>
            <SelectItem value="rework_required">Rework Required</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div>
        <label className="text-sm font-medium">Reviewer *</label>
        <Input
          value={reviewer}
          onChange={(e) => setReviewer(e.target.value)}
          placeholder="Your name"
          required
          className="mt-1"
        />
      </div>
      <div>
        <label className="text-sm font-medium">Rationale</label>
        <Textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Why did you make this decision?"
          className="mt-1"
        />
      </div>
      <div>
        <label className="text-sm font-medium">Linked Review Items (one per line)</label>
        <Textarea
          value={linkedItems}
          onChange={(e) => setLinkedItems(e.target.value)}
          placeholder="e.g. Dimension COMP-003, RMF Section 4.2"
          className="mt-1"
        />
      </div>
      <div>
        <label className="text-sm font-medium">Linked CAPA IDs (one per line)</label>
        <Textarea
          value={linkedCapaIds}
          onChange={(e) => setLinkedCapaIds(e.target.value)}
          placeholder="e.g. CAPA-2024-001"
          className="mt-1"
        />
      </div>
      <Button type="submit" disabled={loading} className="w-full">
        {loading ? "Submitting..." : "Submit Human Decision"}
      </Button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.project_id as string;

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [startingRun, setStartingRun] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getProjectDetail(projectId);
      setProject(data);
    } catch (err) {
      toast.error(String(err));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleStartRun = async () => {
    setStartingRun(true);
    try {
      const result = await startRunInProject(projectId);
      toast.success(`Run started: Round ${result.cycle_number}`);
      load();
    } catch (err) {
      toast.error(String(err));
    } finally {
      setStartingRun(false);
    }
  };

  const handleCloseProject = async () => {
    if (!confirm("Close this project? It will be marked as closed.")) return;
    try {
      await updateProjectStatus(projectId, "closed");
      toast.success("Project closed");
      load();
    } catch (err) {
      toast.error(String(err));
    }
  };

  if (loading) {
    return (
      <div className="w-full max-w-5xl mx-auto p-6">
        <div className="text-center py-12 text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="w-full max-w-5xl mx-auto p-6">
        <div className="text-center py-12 text-muted-foreground">Project not found</div>
      </div>
    );
  }

  const statusColor = STATUS_COLORS[project.current_status] ?? "bg-gray-500";
  const statusLabel = STATUS_LABELS[project.current_status] ?? project.current_status;

  return (
    <div className="w-full max-w-5xl mx-auto p-6 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{project.project_name}</h1>
            <Badge className={`${statusColor} text-white`}>{statusLabel}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">{project.product_name}</p>
        </div>
        <div className="flex gap-2">
          {project.current_status !== "closed" && (
            <>
              <Button
                onClick={handleStartRun}
                disabled={startingRun || project.current_status === "running"}
                variant="default"
              >
                {startingRun ? "Starting..." : "Start New Run"}
              </Button>
              <Button onClick={handleCloseProject} variant="outline">
                Close Project
              </Button>
            </>
          )}
          <Button variant="outline" onClick={() => router.push("/workspace/rmf/projects")}>
            ← All Projects
          </Button>
        </div>
      </div>

      {/* Status Board */}
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground">Total Runs</div>
            <div className="text-2xl font-bold">{project.total_runs}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground">Rework Rounds</div>
            <div className="text-2xl font-bold">{project.total_rework_rounds}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground">Machine Recommendation</div>
            <div className="mt-1">{gateBadge(project.latest_machine_recommendation)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground">Final Gate</div>
            <div className="mt-1">{gateBadge(project.latest_gate_status)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="cycles">Cycles / Rounds</TabsTrigger>
          <TabsTrigger value="audit">Human Decision Audit</TabsTrigger>
          <TabsTrigger value="human-decision">Submit Decision</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Project Information</CardTitle></CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div className="grid grid-cols-2 gap-x-4">
                <span className="text-muted-foreground">Project ID:</span>
                <span className="font-mono">{project.project_id}</span>
                <span className="text-muted-foreground">Product Name:</span>
                <span>{project.product_name}</span>
                <span className="text-muted-foreground">Project Profile:</span>
                <span className="font-mono text-xs truncate">{project.project_profile_path}</span>
                <span className="text-muted-foreground">Input Root:</span>
                <span className="font-mono text-xs truncate">{project.input_root || "—"}</span>
                <span className="text-muted-foreground">Created:</span>
                <span>{formatDate(project.created_at)}</span>
                <span className="text-muted-foreground">Last Updated:</span>
                <span>{formatDate(project.updated_at)}</span>
                <span className="text-muted-foreground">Latest Thread:</span>
                <span className="font-mono">{project.latest_thread_id ?? "—"}</span>
                <span className="text-muted-foreground">Latest Run:</span>
                <span className="font-mono">{project.latest_run_id ?? "—"}</span>
                <span className="text-muted-foreground">Latest Human Decision:</span>
                <span>{gateBadge(project.latest_human_decision)}</span>
              </div>
            </CardContent>
          </Card>

          {/* Recent Cycles */}
          <Card>
            <CardHeader><CardTitle>Recent Cycles</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {project.review_cycles.length === 0 ? (
                <div className="text-sm text-muted-foreground">No cycles yet. Start a run to begin.</div>
              ) : (
                [...project.review_cycles]
                  .sort((a, b) => b.cycle_number - a.cycle_number)
                  .slice(0, 5)
                  .map((c) => <CycleRow key={c.cycle_id} cycle={c} />)
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Cycles Tab */}
        <TabsContent value="cycles" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Review Cycles / Rework Rounds</CardTitle>
              <CardDescription>Full history of all review cycles in this project</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {project.review_cycles.length === 0 ? (
                <div className="text-sm text-muted-foreground">No cycles yet.</div>
              ) : (
                [...project.review_cycles]
                  .sort((a, b) => a.cycle_number - b.cycle_number)
                  .map((c) => <CycleRow key={c.cycle_id} cycle={c} />)
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit Tab */}
        <TabsContent value="audit" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Human Decision Audit Trail</CardTitle>
              <CardDescription>Complete record of all human decisions in this project</CardDescription>
            </CardHeader>
            <CardContent>
              {project.audit_trail.length === 0 ? (
                <div className="text-sm text-muted-foreground">No decisions recorded yet.</div>
              ) : (
                <div className="space-y-4">
                  {project.audit_trail.map((entry) => (
                    <div key={entry.decision_id} className="border rounded-lg p-4 space-y-2">
                      <div className="flex items-center gap-2">
                        <Badge className={
                          entry.decision === "pass" ? "bg-green-100 text-green-800" :
                          entry.decision === "rework_required" ? "bg-red-100 text-red-800" :
                          "bg-amber-100"
                        }>
                          {entry.decision}
                        </Badge>
                        <span className="text-sm text-muted-foreground">by {entry.reviewer}</span>
                        <span className="text-sm text-muted-foreground">on {formatDate(entry.decision_date)}</span>
                      </div>
                      <div className="text-sm">{entry.rationale || <span className="text-muted-foreground italic">No rationale provided</span>}</div>
                      <div className="text-xs text-muted-foreground">
                        Thread: {entry.source_thread_id} | Run: {entry.source_run_id} | Cycle: {entry.source_cycle_id}
                      </div>
                      {entry.linked_review_items.length > 0 && (
                        <div className="text-xs">
                          <span className="text-muted-foreground">Linked Items: </span>
                          {entry.linked_review_items.join(", ")}
                        </div>
                      )}
                      {entry.linked_capa_ids.length > 0 && (
                        <div className="text-xs">
                          <span className="text-muted-foreground">Linked CAPAs: </span>
                          {entry.linked_capa_ids.join(", ")}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Human Decision Form Tab */}
        <TabsContent value="human-decision">
          <Card>
            <CardHeader>
              <CardTitle>Submit Human Decision</CardTitle>
              <CardDescription>
                Record your gate decision for the latest cycle. This will update the project status.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <HumanDecisionForm
                projectId={projectId}
                latestThreadId={project.latest_thread_id}
                onSubmitted={load}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
