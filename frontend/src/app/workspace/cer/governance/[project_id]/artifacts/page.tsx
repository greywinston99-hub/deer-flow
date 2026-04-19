"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
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
import { Input } from "@/components/ui/input";
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

interface ArtifactListing {
  path: string;
  artifact_name: string;
  state: string | null;
  lane: string | null;
  object_type: string | null;
  has_flags: boolean;
  size_bytes: number;
  modified_at: string;
}

interface ArtifactListResponse {
  project_id: string;
  run_id: string;
  artifacts: ArtifactListing[];
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function listArtifacts(
  projectId: string,
  runId: string,
  lane?: string,
  objectType?: string,
  hasFlags?: boolean
): Promise<ArtifactListResponse> {
  const params = new URLSearchParams({ run_id: runId });
  if (lane && lane !== "all") params.set("lane", lane);
  if (objectType && objectType !== "all") params.set("object_type", objectType);
  if (hasFlags) params.set("has_flags", "true");
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/artifacts?${params}`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getArtifactRaw(projectId: string, path: string): Promise<unknown> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/artifacts/${encodeURIComponent(path)}`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const text = await r.text();
  try {
    return JSON.parse(text);
  } catch {
    return { _raw: text };
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
// Lane display names
// ---------------------------------------------------------------------------

const LANE_NAMES: Record<string, string> = {
  lane_2a_claim: "Lane 2a — Claim Scope",
  lane_2b_evidence: "Lane 2b — SOTA Evidence",
  lane_2c_equivalence: "Lane 2c — Equivalence",
  lane_2d_consistency_pmcf: "Lane 2d — Consistency & PMCF",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ArtifactsBrowserPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = decodeURIComponent(String(params.project_id));
  const initialRunId = searchParams.get("run_id");
  const { user } = useCERAuth();

  const [runs, setRuns] = useState<RunItem[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(initialRunId);
  const [artifacts, setArtifacts] = useState<ArtifactListing[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactListing | null>(null);
  const [artifactContent, setArtifactContent] = useState<unknown>(null);
  const [loadingArtifact, setLoadingArtifact] = useState(false);
  const [filterLane, setFilterLane] = useState<string>("all");
  const [filterObjectType, setFilterObjectType] = useState<string>("all");
  const [filterHasFlags, setFilterHasFlags] = useState<boolean>(false);
  const [search, setSearch] = useState("");

  const loadRuns = useCallback(async () => {
    try {
      const data = await listRuns(projectId);
      const nextRuns = data.runs || [];
      setRuns(nextRuns);
      if (!initialRunId && nextRuns.length > 0) {
        setSelectedRunId(nextRuns[0]!.run_id);
      }
    } catch {
      /* ignore */
    }
  }, [projectId, initialRunId]);

  const loadArtifacts = useCallback(async (runId: string, lane?: string, objectType?: string, hasFlags?: boolean) => {
    setLoading(true);
    setArtifacts([]);
    setSelectedArtifact(null);
    setArtifactContent(null);
    try {
      const data = await listArtifacts(
        projectId,
        runId,
        lane === "all" ? undefined : lane,
        objectType === "all" ? undefined : objectType,
        hasFlags || undefined
      );
      setArtifacts(data.artifacts || []);
    } catch {
      toast.error("Failed to load artifacts");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    if (selectedRunId) {
      loadArtifacts(selectedRunId, filterLane, filterObjectType, filterHasFlags);
    }
  }, [selectedRunId, filterLane, filterObjectType, filterHasFlags, loadArtifacts]);

  const handleArtifactClick = useCallback(async (artifact: ArtifactListing) => {
    setSelectedArtifact(artifact);
    setLoadingArtifact(true);
    setArtifactContent(null);
    try {
      const pathParts = artifact.path.split("/artifacts/");
      const relativePath = pathParts[pathParts.length - 1] ?? artifact.path;
      const content = await getArtifactRaw(projectId, relativePath);
      setArtifactContent(content);
    } catch {
      setArtifactContent({ error: "Failed to load artifact" });
    } finally {
      setLoadingArtifact(false);
    }
  }, [projectId]);

  const filteredArtifacts = artifacts.filter((a) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      a.artifact_name.toLowerCase().includes(q) ||
      a.path.toLowerCase().includes(q)
    );
  });

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
          <h2 className="text-sm font-semibold">Artifact Browser</h2>
          <p className="text-xs text-muted-foreground">Browse lane artifacts by round</p>
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

        {/* Lane filter */}
        <div className="p-2 border-b space-y-1">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">FILTER BY LANE</div>
          <div className="space-y-0.5">
            {["all", "lane_2a_claim", "lane_2b_evidence", "lane_2c_equivalence", "lane_2d_consistency_pmcf", "route", "adjudication"].map((lane) => (
              <button
                key={lane}
                className={`w-full text-left px-2 py-1 rounded text-[11px] hover:bg-muted ${
                  filterLane === lane ? "bg-primary/10 border border-primary/30" : ""
                }`}
                onClick={() => setFilterLane(lane)}
              >
                {lane === "all" ? "All Lanes" :
                  lane === "route" ? "Route (01)" :
                  lane === "adjudication" ? "Adjudication (04)" :
                  LANE_NAMES[lane] || lane}
              </button>
            ))}
          </div>
        </div>

        {/* Object Type filter */}
        <div className="p-2 border-b space-y-1">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">FILTER BY TYPE</div>
          <Select value={filterObjectType} onValueChange={setFilterObjectType}>
            <SelectTrigger className="h-7 text-[11px]">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              <SelectItem value="CLAIM">Claim</SelectItem>
              <SelectItem value="EVIDENCE_BLOCK">Evidence Block</SelectItem>
              <SelectItem value="EQUIVALENCE_UNIT">Equivalence Unit</SelectItem>
              <SelectItem value="RISK_BENEFIT">Risk Benefit</SelectItem>
              <SelectItem value="PMCF_HANDOFF">PMCF / Consistency</SelectItem>
              <SelectItem value="ROUTE_DECISION">Route Decision</SelectItem>
              <SelectItem value="SPECIAL_PROCEDURE">Special Procedure</SelectItem>
              <SelectItem value="FOLLOW_UP">Follow-up</SelectItem>
              <SelectItem value="OTHER">Other</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Has Flags filter */}
        <div className="p-2 border-b">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">FLAGS</div>
          <label className="flex items-center gap-2 px-2 py-1 text-[11px] hover:bg-muted rounded cursor-pointer">
            <input
              type="checkbox"
              checked={filterHasFlags}
              onChange={(e) => setFilterHasFlags(e.target.checked)}
              className="accent-primary"
            />
            <span>Has flags only</span>
          </label>
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
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/compare`}>
              Rework Compare
            </Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selectedRunId && (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Select a run from the sidebar</p>
          </div>
        )}

        {selectedRunId && (
          <div className="max-w-6xl mx-auto">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h1 className="text-xl font-bold">Artifact Browser</h1>
                <p className="text-sm text-muted-foreground">
                  {projectId} · Run: {selectedRunId} · {artifacts.length} artifact(s)
                </p>
              </div>
              <div className="flex items-center gap-3">
                {user && (
                  <Badge variant="outline" className="text-xs">
                    {user.role}
                  </Badge>
                )}
                <Input
                  placeholder="Filter artifacts..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-64 text-xs"
                />
              </div>
            </div>

            {loading && <p className="text-sm text-muted-foreground">Loading artifacts...</p>}

            <div className="grid grid-cols-3 gap-4">
              {/* Artifact List */}
              <div className="col-span-1 space-y-2 max-h-[calc(100vh-12rem)] overflow-y-auto pr-1">
                {/* Active filter summary */}
                {(filterObjectType !== "all" || filterHasFlags) && (
                  <div className="text-[10px] text-muted-foreground px-1 pb-1">
                    Showing {filteredArtifacts.length} of {artifacts.length} artifact(s)
                  </div>
                )}
                {filteredArtifacts.map((artifact) => (
                  <button
                    key={artifact.path}
                    className={`w-full text-left p-3 border rounded hover:bg-muted/50 transition-colors ${
                      selectedArtifact?.path === artifact.path ? "border-primary bg-primary/5" : ""
                    }`}
                    onClick={() => handleArtifactClick(artifact)}
                  >
                    <div className="flex items-center justify-between mb-1 flex-wrap gap-1">
                      <span className="font-mono text-xs font-medium truncate max-w-[120px]">{artifact.artifact_name}</span>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {artifact.has_flags && (
                          <Badge variant="destructive" className="text-[9px]">⚑</Badge>
                        )}
                        {artifact.object_type && artifact.object_type !== "OTHER" && (
                          <Badge variant="secondary" className="text-[9px]">{artifact.object_type}</Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1 mb-1">
                      {artifact.state && (
                        <Badge variant="outline" className="text-[9px] font-mono">{artifact.state}</Badge>
                      )}
                      {artifact.lane && (
                        <Badge variant="outline" className="text-[9px]">{artifact.lane}</Badge>
                      )}
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      {(artifact.size_bytes / 1024).toFixed(1)} KB · {new Date(artifact.modified_at).toLocaleString()}
                    </div>
                  </button>
                ))}
                {!loading && filteredArtifacts.length === 0 && (
                  <p className="text-xs text-muted-foreground p-2">No artifacts found.</p>
                )}
              </div>

              {/* Artifact Detail */}
              <div className="col-span-2">
                {selectedArtifact ? (
                  <Card>
                    <CardHeader>
                      <div className="flex items-start justify-between flex-wrap gap-2">
                        <div className="flex-1 min-w-0">
                          <CardTitle className="text-sm font-mono">{selectedArtifact.artifact_name}</CardTitle>
                          <CardDescription className="text-[10px] font-mono break-all mt-1">
                            {selectedArtifact.path}
                          </CardDescription>
                        </div>
                        <div className="flex flex-wrap gap-1 flex-shrink-0">
                          {selectedArtifact.object_type && selectedArtifact.object_type !== "OTHER" && (
                            <Badge variant="secondary" className="text-[10px]">{selectedArtifact.object_type}</Badge>
                          )}
                          {selectedArtifact.state && (
                            <Badge variant="outline" className="text-[10px] font-mono">{selectedArtifact.state}</Badge>
                          )}
                          {selectedArtifact.lane && (
                            <Badge variant="outline" className="text-[10px]">{selectedArtifact.lane}</Badge>
                          )}
                          {selectedArtifact.has_flags && (
                            <Badge variant="destructive" className="text-[10px]">⚑ Flagged</Badge>
                          )}
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      {loadingArtifact ? (
                        <p className="text-sm text-muted-foreground">Loading artifact content...</p>
                      ) : artifactContent ? (
                        typeof artifactContent === "object" && "_raw" in artifactContent ? (
                          <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-[calc(100vh-16rem)]">
                            {(artifactContent as { _raw: string })._raw}
                          </pre>
                        ) : (
                          <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-[calc(100vh-16rem)]">
                            {JSON.stringify(artifactContent, null, 2)}
                          </pre>
                        )
                      ) : null}
                    </CardContent>
                  </Card>
                ) : (
                  <Card>
                    <CardContent className="flex items-center justify-center h-64 text-muted-foreground">
                      <p className="text-sm">Select an artifact to inspect</p>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
