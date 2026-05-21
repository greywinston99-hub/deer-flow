"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
import { useCERAuth, cerReviewFetch } from "@/core/cer_auth";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FollowupsSummary {
  total_open: number;
  total_resolved: number;
  total_closed: number;
  projects_with_open: string[];
}

interface ProjectSummary {
  project_id: string;
  display_name: string;
  latest_run_id: string | null;
  latest_round: string | null;
  latest_state: string | null;
  gate_status: string | null;
  updated_at: string | null;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function getFollowupsSummary(): Promise<FollowupsSummary> {
  const r = await cerReviewFetch("/api/cer-review/followups-summary");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function listCERProjects(): Promise<{ projects: ProjectSummary[] }> {
  const r = await cerReviewFetch("/api/cer-review/projects");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function listRuns(projectId: string): Promise<{ project_id: string; runs: RunItem[] }> {
  const r = await cerReviewFetch(`/api/cer-review/${encodeURIComponent(projectId)}/runs`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

interface RunItem {
  run_id: string;
  round_id: string;
  current_state: string;
  artifact_root: string;
  model: string | null;
  execution_mode: string | null;
  is_stub: boolean;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function GateStatusBadge({ gate }: { gate: string | null }) {
  if (!gate) return null;
  const variants: Record<string, string> = {
    GATE_0: "bg-blue-100 text-blue-800",
    GATE_1: "bg-yellow-100 text-yellow-800",
    GATE_2: "bg-orange-100 text-orange-800",
    GATE_3: "bg-purple-100 text-purple-800",
    GATE_3_REWORK: "bg-red-100 text-red-800",
    COMPLETE: "bg-green-100 text-green-800",
  };
  return (
    <Badge className={variants[gate] || "bg-gray-100 text-gray-800"}>
      {gate}
    </Badge>
  );
}

function StateBadge({ state }: { state: string | null }) {
  if (!state) return null;
  return (
    <Badge variant="outline" className="font-mono text-xs">
      {state}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RunHomePage() {
  const router = useRouter();
  const { user } = useCERAuth();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [expandedProject, setExpandedProject] = useState<string | null>(null);
  const [runsMap, setRunsMap] = useState<Record<string, RunItem[]>>({});
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [followupsSummary, setFollowupsSummary] = useState<FollowupsSummary | null>(null);

  const loadProjects = useCallback(async () => {
    setLoadingProjects(true);
    try {
      const data = await listCERProjects();
      setProjects(data.projects || []);
    } catch {
      toast.error("Failed to load CER projects");
    } finally {
      setLoadingProjects(false);
    }
  }, []);

  const loadFollowupsSummary = useCallback(async () => {
    try {
      const data = await getFollowupsSummary();
      setFollowupsSummary(data);
    } catch {
      /* ignore — followups are optional */
    }
  }, []);

  useEffect(() => {
    loadProjects();
    loadFollowupsSummary();
  }, [loadProjects, loadFollowupsSummary]);

  const toggleProject = useCallback(async (projectId: string) => {
    if (expandedProject === projectId) {
      setExpandedProject(null);
      return;
    }
    setExpandedProject(projectId);
    if (!runsMap[projectId]) {
      setLoadingRuns(true);
      try {
        const data = await listRuns(projectId);
        setRunsMap((prev) => ({ ...prev, [projectId]: data.runs || [] }));
      } catch {
        toast.error("Failed to load runs");
      } finally {
        setLoadingRuns(false);
      }
    }
  }, [expandedProject, runsMap]);

  const handleNavigateRun = useCallback((projectId: string, runId: string) => {
    router.push(`/workspace/cer/governance/${encodeURIComponent(projectId)}?run_id=${encodeURIComponent(runId)}`);
  }, [router]);

  const handleNavigateGate1 = useCallback((projectId: string, runId: string) => {
    router.push(`/workspace/cer/governance/${encodeURIComponent(projectId)}/gate-1?run_id=${encodeURIComponent(runId)}`);
  }, [router]);

  const handleNavigateProject = useCallback((projectId: string, runId: string | null) => {
    if (runId) {
      router.push(`/workspace/cer/governance/${encodeURIComponent(projectId)}?run_id=${encodeURIComponent(runId)}`);
    } else {
      router.push(`/workspace/cer/governance/${encodeURIComponent(projectId)}`);
    }
  }, [router]);

  const handleNavigateGate3 = useCallback((projectId: string, runId: string) => {
    router.push(`/workspace/cer/governance/${encodeURIComponent(projectId)}/gate-3?run_id=${encodeURIComponent(runId)}`);
  }, [router]);

  const handleNavigateArtifacts = useCallback((projectId: string, runId: string) => {
    router.push(`/workspace/cer/governance/${encodeURIComponent(projectId)}/artifacts?run_id=${encodeURIComponent(runId)}`);
  }, [router]);

  const handleNavigateCompare = useCallback((projectId: string) => {
    router.push(`/workspace/cer/governance/${encodeURIComponent(projectId)}/compare`);
  }, [router]);

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-80 border-r flex flex-col">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-lg font-semibold">CER Governance</h2>
            {user && (
              <Badge variant="outline" className="text-xs">
                {user.role}
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground">Review Workspace — Governance Data</p>
        </div>

        {/* Navigation */}
        <div className="p-2 border-b space-y-1">
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <a href="/workspace/cer/governance/run-home">🏠 Run Home</a>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <a href="/workspace/cer/governance/new-project">+ New Project</a>
          </Button>
        </div>

        {/* Project List */}
        <div className="flex-1 overflow-y-auto p-2">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground">Projects ({projects.length})</span>
            <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={loadProjects}>
              Refresh
            </Button>
          </div>

          {loadingProjects && <p className="text-xs text-muted-foreground p-2">Loading...</p>}
          {!loadingProjects && projects.length === 0 && (
            <p className="text-xs text-muted-foreground p-2">
              No CER projects found. Projects appear here after the first CER run completes.
            </p>
          )}

          {projects.map((project) => (
            <div key={project.project_id} className="mb-1">
              <button
                className={`w-full text-left px-2 py-2 rounded text-xs hover:bg-muted transition-colors ${
                  expandedProject === project.project_id ? "bg-muted" : ""
                }`}
                onClick={() => toggleProject(project.project_id)}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-medium truncate">{project.project_id}</span>
                  <div className="flex items-center gap-1">
                    <GateStatusBadge gate={project.gate_status} />
                    {expandedProject === project.project_id ? "▾" : "▸"}
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <StateBadge state={project.latest_state} />
                  {project.latest_round && (
                    <span className="text-muted-foreground text-[10px]">{project.latest_round}</span>
                  )}
                </div>
              </button>

              {/* Expanded runs */}
              {expandedProject === project.project_id && (
                <div className="ml-4 mt-1 space-y-1">
                  {(loadingRuns ? [] : runsMap[project.project_id] || []).map((run) => (
                    <div
                      key={run.run_id}
                      className="px-2 py-1.5 rounded text-[11px] bg-card border hover:bg-muted transition-colors"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono font-medium">{run.run_id}</span>
                        <div className="flex items-center gap-1">
                          {run.is_stub && (
                            <Badge variant="outline" className="text-[9px] px-1">STUB</Badge>
                          )}
                          <StateBadge state={run.current_state} />
                        </div>
                      </div>
                      <div className="text-muted-foreground mb-1">
                        {run.round_id} · {run.model || "—"}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-5 text-[10px] px-1"
                          onClick={() => handleNavigateRun(project.project_id, run.run_id)}
                        >
                          Detail
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-5 text-[10px] px-1"
                          onClick={() => handleNavigateGate1(project.project_id, run.run_id)}
                        >
                          G1 Review
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-5 text-[10px] px-1"
                          onClick={() => handleNavigateGate3(project.project_id, run.run_id)}
                        >
                          G3 Review
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-5 text-[10px] px-1"
                          onClick={() => handleNavigateArtifacts(project.project_id, run.run_id)}
                        >
                          Artifacts
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-5 text-[10px] px-1"
                          onClick={() => handleNavigateCompare(project.project_id)}
                        >
                          Compare
                        </Button>
                      </div>
                    </div>
                  ))}
                  {loadingRuns && expandedProject === project.project_id && (
                    <p className="text-[10px] text-muted-foreground px-2 py-1">Loading runs...</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto">
          <div className="mb-6">
            <h1 className="text-2xl font-bold mb-1">CER Review Workspace</h1>
            <p className="text-sm text-muted-foreground">
              Governance-aware CER review interface — reads from real runtime artifacts and governance data.
            </p>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Total Projects</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{projects.length}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Active at GATE_3</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {projects.filter((p) => p.gate_status === "GATE_3").length}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Completed</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {projects.filter((p) => p.gate_status === "COMPLETE").length}
                </div>
              </CardContent>
            </Card>
            <Card className={followupsSummary && followupsSummary.total_open > 0 ? "border-yellow-300" : ""}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Open Follow-ups</CardTitle>
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${followupsSummary && followupsSummary.total_open > 0 ? "text-yellow-600" : ""}`}>
                  {followupsSummary ? followupsSummary.total_open : "—"}
                </div>
                {followupsSummary && followupsSummary.projects_with_open.length > 0 && (
                  <div className="text-xs text-muted-foreground mt-1">
                    Across {followupsSummary.projects_with_open.length} project{followupsSummary.projects_with_open.length > 1 ? "s" : ""}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Project Table */}
          <Card>
            <CardHeader>
              <CardTitle>All CER Projects</CardTitle>
              <CardDescription>Click a project to expand run history</CardDescription>
            </CardHeader>
            <CardContent>
              {projects.length === 0 ? (
                <p className="text-sm text-muted-foreground">No projects yet.</p>
              ) : (
                <div className="space-y-2">
                  {projects.map((project) => (
                    <div
                      key={project.project_id}
                      className="flex items-center justify-between p-3 border rounded hover:bg-muted/50 transition-colors cursor-pointer"
                      onClick={() => handleNavigateProject(project.project_id, project.latest_run_id)}
                    >
                      <div className="flex items-center gap-3">
                        <div>
                          <div className="font-mono font-medium text-sm">{project.project_id}</div>
                          <div className="text-xs text-muted-foreground">
                            {project.latest_round || "—"} · {project.latest_run_id || "no runs"}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <StateBadge state={project.latest_state} />
                        <GateStatusBadge gate={project.gate_status} />
                        {project.updated_at && (
                          <span className="text-[10px] text-muted-foreground">
                            {new Date(project.updated_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Governance Architecture Note */}
          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="text-sm">Data Sources</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-2 border rounded">
                  <div className="font-medium mb-1">Decision Ledger</div>
                  <div className="text-muted-foreground">LEDGER-XXX entries · append-only</div>
                  <div className="text-muted-foreground font-mono text-[10px]">
                    governance/{`{project_id}_decision_ledger.json`}
                  </div>
                </div>
                <div className="p-2 border rounded">
                  <div className="font-medium mb-1">Gate Audit Trail</div>
                  <div className="text-muted-foreground">{"B-G" + "$" + "{" + "n}-XXX per gate decision"}</div>
                  <div className="text-muted-foreground font-mono text-[10px]">
                    governance/gate_audits/{'{project_id}/B-G${n}-XXX.json'}
                  </div>
                </div>
                <div className="p-2 border rounded">
                  <div className="font-medium mb-1">State Transition Log</div>
                  <div className="text-muted-foreground">ST-XXX · JSONL append-only</div>
                  <div className="text-muted-foreground font-mono text-[10px]">
                    governance/state_transition_log.jsonl
                  </div>
                </div>
                <div className="p-2 border rounded">
                  <div className="font-medium mb-1">Follow-up / Backflow</div>
                  <div className="text-muted-foreground">F-XXX / BF-XXX registry</div>
                  <div className="text-muted-foreground font-mono text-[10px]">
                    governance/follow_up_registry.json
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
