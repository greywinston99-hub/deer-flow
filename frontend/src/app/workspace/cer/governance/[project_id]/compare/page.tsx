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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCERAuth, cerReviewFetch } from "@/core/cer_auth";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ReworkLane {
  lane: string;
  display_name: string;
  artifacts: {
    artifact: string;
    round_n: string | null;
    round_n_plus_1: string | null;
    status: "UNCHANGED" | "CHANGED" | "NEW" | "REMOVED" | "BOTH_MISSING";
  }[];
}

interface ReworkCompareResponse {
  project_id: string;
  round_n: string;
  round_n_plus_1: string;
  lanes: ReworkLane[];
  gate_decision_comparison: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function getReworkCompare(
  projectId: string,
  runId: string,
  roundN: number,
  roundNPlus1: number
): Promise<ReworkCompareResponse> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/compare?run_id=${encodeURIComponent(runId)}&round_n=${roundN}&round_n_plus_1=${roundNPlus1}`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getArtifactContent(projectId: string, path: string): Promise<Record<string, unknown> | null> {
  try {
    const r = await cerReviewFetch(
      `/api/cer-review/${encodeURIComponent(projectId)}/artifacts/${encodeURIComponent(path)}`
    );
    if (!r.ok) return null;
    const text = await r.text();
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function listRuns(projectId: string): Promise<{ runs: RunItem[] }> {
  const r = await cerReviewFetch(`/api/cer-review/${encodeURIComponent(projectId)}/runs`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

interface RunItem {
  run_id: string;
  round_id: string;
  current_state: string;
  is_stub: boolean;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Status display
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    UNCHANGED: "bg-green-100 text-green-800",
    CHANGED: "bg-red-100 text-red-800",
    NEW: "bg-blue-100 text-blue-800",
    REMOVED: "bg-orange-100 text-orange-800",
    BOTH_MISSING: "bg-gray-100 text-gray-800",
  };
  return <Badge className={variants[status] || "bg-gray-100"}>{status}</Badge>;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ReworkComparePage() {
  const params = useParams();
  const projectId = decodeURIComponent(String(params.project_id));
  const { user } = useCERAuth();

  const [runs, setRuns] = useState<RunItem[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [roundN, setRoundN] = useState(1);
  const [roundNPlus1, setRoundNPlus1] = useState(2);
  const [comparison, setComparison] = useState<ReworkCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedArtifact, setExpandedArtifact] = useState<{ lane: string; artifact: ReworkLane["artifacts"][number] } | null>(null);
  const [artifactContentN, setArtifactContentN] = useState<Record<string, unknown> | null>(null);
  const [artifactContentNP1, setArtifactContentNP1] = useState<Record<string, unknown> | null>(null);
  const [loadingArtifactContent, setLoadingArtifactContent] = useState(false);

  const loadRuns = useCallback(async () => {
    try {
      const data = await listRuns(projectId);
      setRuns(data.runs || []);
      if (data.runs && data.runs.length > 0) {
        setSelectedRunId(data.runs[0]!.run_id);
      }
    } catch {
      /* ignore */
    }
  }, [projectId]);

  const loadComparison = useCallback(async () => {
    if (!selectedRunId) return;
    setLoading(true);
    setComparison(null);
    try {
      const data = await getReworkCompare(projectId, selectedRunId, roundN, roundNPlus1);
      setComparison(data);
    } catch {
      toast.error("Failed to load comparison");
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedRunId, roundN, roundNPlus1]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    if (selectedRunId) {
      loadComparison();
    }
  }, [selectedRunId, roundN, roundNPlus1, loadComparison]);

  const changedCount = comparison?.lanes.reduce(
    (acc, lane) => acc + lane.artifacts.filter((a) => a.status === "CHANGED").length,
    0
  ) ?? 0;

  const newCount = comparison?.lanes.reduce(
    (acc, lane) => acc + lane.artifacts.filter((a) => a.status === "NEW").length,
    0
  ) ?? 0;

  const handleArtifactClick = useCallback(async (lane: string, artifact: ReworkLane["artifacts"][number]) => {
    setExpandedArtifact({ lane, artifact });
    setArtifactContentN(null);
    setArtifactContentNP1(null);
    setLoadingArtifactContent(true);

    const laneDirMap: Record<string, string> = {
      "lane_2a_claim": "03_lanes",
      "lane_2b_evidence": "03_lanes",
      "lane_2c_equivalence": "03_lanes",
      "lane_2d_consistency_pmcf": "03_lanes",
    };

    try {
      const laneDir = laneDirMap[lane] || "03_lanes";
      const [contentN, contentNP1] = await Promise.all([
        artifact.round_n ? getArtifactContent(projectId, `${laneDir}/${artifact.artifact}`) : Promise.resolve(null),
        artifact.round_n_plus_1 ? getArtifactContent(projectId, `${laneDir}/${artifact.artifact}`) : Promise.resolve(null),
      ]);
      setArtifactContentN(contentN);
      setArtifactContentNP1(contentNP1);
    } catch {
      /* ignore */
    } finally {
      setLoadingArtifactContent(false);
    }
  }, [projectId]);

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
          <div className="text-xs text-muted-foreground mb-1">
            <Link
              href={`/workspace/cer/governance/${encodeURIComponent(projectId)}?run_id=${selectedRunId || ""}`}
              className="hover:underline"
            >
              ← Run Detail
            </Link>
          </div>
          <h2 className="text-sm font-semibold">Rework Compare</h2>
          <p className="text-xs text-muted-foreground">Round isolation comparison</p>
        </div>

        {/* Run selector */}
        <div className="p-2 border-b">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">SELECT RUN</div>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {runs.map((run) => (
              <button
                key={run.run_id}
                className={`w-full text-left px-2 py-1 rounded text-[11px] hover:bg-muted ${
                  selectedRunId === run.run_id ? "bg-primary/10 border border-primary/30" : ""
                }`}
                onClick={() => setSelectedRunId(run.run_id)}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono truncate">{run.run_id}</span>
                  {run.is_stub && <Badge variant="outline" className="text-[9px]">STUB</Badge>}
                </div>
                <div className="text-muted-foreground text-[10px]">{run.round_id}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Navigation */}
        <div className="p-2 space-y-1 flex-1 overflow-y-auto">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">NAVIGATE</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/gate-1${selectedRunId ? `?run_id=${encodeURIComponent(selectedRunId)}` : ""}`}>
              G1 Route Review
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/gate-3${selectedRunId ? `?run_id=${encodeURIComponent(selectedRunId)}` : ""}`}>
              G3 BRR Review
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/artifacts${selectedRunId ? `?run_id=${encodeURIComponent(selectedRunId)}` : ""}`}>
              Artifacts Browser
            </Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-xl font-bold">Rework Comparison</h1>
              <p className="text-sm text-muted-foreground">
                {projectId} · Round isolation — each round has its own directory tree
              </p>
            </div>
            {user && (
              <Badge variant="outline" className="text-xs">
                {user.role}
              </Badge>
            )}
          </div>

          {/* Round selector */}
          <Card className="mb-4">
            <CardContent className="p-4">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Round N:</span>
                  <Select value={String(roundN)} onValueChange={(v) => setRoundN(Number(v))}>
                    <SelectTrigger className="w-32 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <SelectItem key={n} value={String(n)}>
                          round_{String(n).padStart(3, "0")}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <span className="text-muted-foreground">→</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Round N+1:</span>
                  <Select value={String(roundNPlus1)} onValueChange={(v) => setRoundNPlus1(Number(v))}>
                    <SelectTrigger className="w-32 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <SelectItem key={n} value={String(n)}>
                          round_{String(n).padStart(3, "0")}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button size="sm" variant="outline" onClick={loadComparison} disabled={!selectedRunId || loading}>
                  Refresh
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Summary */}
          {comparison && (
            <div className="grid grid-cols-4 gap-4 mb-4">
              <Card>
                <CardContent className="p-3 text-center">
                  <div className="text-2xl font-bold">{comparison.round_n}</div>
                  <div className="text-xs text-muted-foreground">Baseline Round</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-3 text-center">
                  <div className="text-2xl font-bold">{comparison.round_n_plus_1}</div>
                  <div className="text-xs text-muted-foreground">Comparison Round</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-3 text-center">
                  <div className="text-2xl font-bold text-red-600">{changedCount}</div>
                  <div className="text-xs text-muted-foreground">Changed Artifacts</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-3 text-center">
                  <div className="text-2xl font-bold text-blue-600">{newCount}</div>
                  <div className="text-xs text-muted-foreground">New Artifacts</div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Round Isolation Note */}
          <Card className="mb-4 border-blue-200 bg-blue-50/50">
            <CardContent className="p-3">
              <p className="text-xs text-blue-800">
                <strong>Round Isolation:</strong> When rework is triggered at GATE_3, the original round is
                archived as S19 and a new round begins at S00. Both rounds exist as separate directory trees
                under <span className="font-mono">artifacts/cer/{projectId}/</span>. Hash comparison
                (SHA-256) is used to determine artifact change status.
              </p>
            </CardContent>
          </Card>

          {/* Comparison Table */}
          {loading && <p className="text-sm text-muted-foreground">Loading comparison...</p>}

          {comparison && (
            <div className="space-y-4">
              {comparison.lanes.map((lane) => (
                <Card key={lane.lane}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="text-sm font-mono">{lane.lane}</CardTitle>
                        <CardDescription>{lane.display_name}</CardDescription>
                      </div>
                      {lane.artifacts.some((a) => a.status !== "UNCHANGED") && (
                        <Badge variant="destructive" className="text-xs">
                          {lane.artifacts.filter((a) => a.status !== "UNCHANGED").length} change(s)
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {lane.artifacts.map((artifact, i) => (
                        <div
                          key={i}
                          className={`p-3 border rounded cursor-pointer hover:shadow-sm transition-shadow ${
                            artifact.status === "CHANGED"
                              ? "border-red-300 bg-red-50/50"
                              : artifact.status === "NEW"
                              ? "border-blue-300 bg-blue-50/50"
                              : artifact.status === "REMOVED"
                              ? "border-orange-300 bg-orange-50/50"
                              : "border-green-200 bg-green-50/50"
                          } ${expandedArtifact?.artifact.artifact === artifact.artifact ? "ring-2 ring-primary" : ""}`}
                          onClick={() => handleArtifactClick(lane.lane, artifact)}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-sm font-medium">{artifact.artifact}</span>
                              {artifact.status !== "UNCHANGED" && (
                                <span className="text-[10px] text-muted-foreground">click to inspect</span>
                              )}
                            </div>
                            <StatusBadge status={artifact.status} />
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                            <div>
                              <span className="font-medium">Round N:</span>{" "}
                              {artifact.round_n ? (
                                <span className="font-mono text-[10px] truncate inline-block max-w-xs align-middle">
                                  {artifact.round_n.slice(0, 16)}…
                                </span>
                              ) : (
                                <span className="text-red-500">NOT PRESENT</span>
                              )}
                            </div>
                            <div>
                              <span className="font-medium">Round N+1:</span>{" "}
                              {artifact.round_n_plus_1 ? (
                                <span className="font-mono text-[10px] truncate inline-block max-w-xs align-middle">
                                  {artifact.round_n_plus_1.slice(0, 16)}…
                                </span>
                              ) : (
                                <span className="text-red-500">NOT PRESENT</span>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Diff Viewer Panel */}
          {comparison && expandedArtifact && (
            <Card className="mt-4 border-purple-200">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-sm font-mono">{expandedArtifact.artifact.artifact}</CardTitle>
                    <CardDescription>
                      {expandedArtifact.lane} · {expandedArtifact.artifact.status}
                    </CardDescription>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs"
                    onClick={() => setExpandedArtifact(null)}
                  >
                    ✕ Close
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {loadingArtifactContent ? (
                  <p className="text-sm text-muted-foreground">Loading artifact content...</p>
                ) : (
                  <div className="space-y-4">
                    {/* SHA comparison */}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-2 border border-green-200 bg-green-50/50 rounded">
                        <div className="text-[10px] font-medium text-green-800 mb-1">Round N SHA</div>
                        <div className="font-mono text-[10px] break-all text-green-700">
                          {expandedArtifact.artifact.round_n || "NOT PRESENT"}
                        </div>
                      </div>
                      <div className="p-2 border border-blue-200 bg-blue-50/50 rounded">
                        <div className="text-[10px] font-medium text-blue-800 mb-1">Round N+1 SHA</div>
                        <div className="font-mono text-[10px] break-all text-blue-700">
                          {expandedArtifact.artifact.round_n_plus_1 || "NOT PRESENT"}
                        </div>
                      </div>
                    </div>

                    {/* Status summary */}
                    <div className="flex items-center gap-2">
                      <StatusBadge status={expandedArtifact.artifact.status} />
                      <span className="text-xs text-muted-foreground">
                        {expandedArtifact.artifact.status === "UNCHANGED" && "Content is identical between rounds"}
                        {expandedArtifact.artifact.status === "CHANGED" && "Content differs between rounds"}
                        {expandedArtifact.artifact.status === "NEW" && "Artifact only exists in Round N+1"}
                        {expandedArtifact.artifact.status === "REMOVED" && "Artifact was removed in Round N+1"}
                        {expandedArtifact.artifact.status === "BOTH_MISSING" && "Artifact absent in both rounds"}
                      </span>
                    </div>

                    {/* Content preview */}
                    {(artifactContentN || artifactContentNP1) && (
                      <div className="grid grid-cols-2 gap-3">
                        {artifactContentN && (
                          <div>
                            <div className="text-[10px] font-medium text-green-800 mb-1 px-1">Round N Content (preview)</div>
                            <pre className="text-[10px] bg-green-50 border border-green-200 p-2 rounded overflow-auto max-h-64">
                              {JSON.stringify(artifactContentN, null, 2).slice(0, 2000)}
                              {JSON.stringify(artifactContentN, null, 2).length > 2000 && "\n... (truncated)"}
                            </pre>
                          </div>
                        )}
                        {artifactContentNP1 && (
                          <div>
                            <div className="text-[10px] font-medium text-blue-800 mb-1 px-1">Round N+1 Content (preview)</div>
                            <pre className="text-[10px] bg-blue-50 border border-blue-200 p-2 rounded overflow-auto max-h-64">
                              {JSON.stringify(artifactContentNP1, null, 2).slice(0, 2000)}
                              {JSON.stringify(artifactContentNP1, null, 2).length > 2000 && "\n... (truncated)"}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {!loading && !comparison && selectedRunId && (
            <Card>
              <CardContent className="p-6 text-center text-muted-foreground">
                <p>No comparison data available. Ensure both rounds exist.</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
