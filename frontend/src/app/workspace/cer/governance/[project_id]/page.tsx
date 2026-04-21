"use client";

import { useCallback, useEffect, useState } from "react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCERAuth, cerReviewFetch } from "@/core/cer_auth";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RunDetailResponse {
  project_id: string;
  run_id: string;
  round_id: string;
  current_state: string;
  lane_statuses: Record<string, string>;
  gate_statuses: Record<string, string>;
  ledger_summary: { entries: LedgerEntry[]; total: number };
  ledger_total: number;
  state_log_summary: StateTransitionEntry[];
  bundle_lineage_summary: BundleLineageEntry[];
  findings_summary: FindingEntry[];
  followups_open: number;
  model: string | null;
  execution_mode: string | null;
  is_stub: boolean;
}

interface LedgerEntry {
  entry_id: string;
  entry_type: string;
  run_id: string;
  round_id: string;
  actor: string;
  timestamp: string;
  gate: string | null;
  from_state: string | null;
  to_state: string | null;
  decision_data: Record<string, unknown>;
}

interface StateTransitionEntry {
  entry_id: string;
  run_id: string;
  round_id: string;
  from_state: string;
  to_state: string;
  timestamp: string;
  actor: string;
  trigger: string | null;
  duration_sec: number | null;
}

interface FollowupEntry {
  follow_up_id: string;
  type: string;
  description: string;
  assigned_to: string;
  status: string;
  created_at: string;
  due_date: string | null;
  closure_criteria: string | null;
}

interface FollowupResponse {
  project_id: string;
  follow_ups: FollowupEntry[];
  summary: Record<string, number>;
}

interface BackflowEntry {
  backflow_id: string;
  trigger_type: string;
  source_round: string;
  new_round: string;
  evidence_description: string;
  created_at: string;
}

interface BackflowResponse {
  project_id: string;
  backflows: BackflowEntry[];
}

interface BundleLineageEntry {
  bundle_id?: string;
  id?: string;
  source_bundle?: string;
  derived_bundle?: string;
  artifact_path?: string;
  hash?: string;
  checksum?: string;
  relation_type?: string;
  created_at?: string;
  [key: string]: unknown;
}

interface FindingEntry {
  finding_id?: string;
  id?: string;
  category?: string;
  title?: string;
  description?: string;
  source_limitation_ref?: string;
  severity?: string;
  actionable?: boolean;
  action?: string;
  human_decision_required?: boolean;
  preliminary_judgment?: string;
  status?: string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function getRunDetail(projectId: string, runId: string): Promise<RunDetailResponse> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/run/${encodeURIComponent(runId)}`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getLedger(projectId: string, limit?: number, offset?: number): Promise<{ entries: LedgerEntry[]; total_count: number; has_more: boolean }> {
  const params = new URLSearchParams();
  if (limit != null) params.set("limit", String(limit));
  if (offset != null) params.set("offset", String(offset));
  const qs = params.toString();
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/ledger${qs ? `?${qs}` : ""}`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getFollowups(projectId: string): Promise<FollowupResponse> {
  const r = await cerReviewFetch(`/api/cer-review/${encodeURIComponent(projectId)}/followups`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getBackflows(projectId: string): Promise<BackflowResponse> {
  const r = await cerReviewFetch(`/api/cer-review/${encodeURIComponent(projectId)}/backflows`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
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
// Helpers
// ---------------------------------------------------------------------------

function LaneStatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    COMPLETE: "bg-green-100 text-green-800",
    FLAGGED: "bg-red-100 text-red-800",
    PENDING: "bg-gray-100 text-gray-800",
  };
  return <Badge className={variants[status] || "bg-gray-100"}>{status}</Badge>;
}

function GateStatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    COMPLETE: "bg-green-100 text-green-800",
    PENDING: "bg-yellow-100 text-yellow-800",
    BLOCKING: "bg-red-100 text-red-800",
  };
  return <Badge className={variants[status] || "bg-gray-100"}>{status}</Badge>;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RunDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = decodeURIComponent(String(params.project_id));
  const initialRunId = searchParams.get("run_id");
  const { user } = useCERAuth();

  const [runDetail, setRunDetail] = useState<RunDetailResponse | null>(null);
  const [followups, setFollowups] = useState<FollowupResponse | null>(null);
  const [backflows, setBackflows] = useState<BackflowResponse | null>(null);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(initialRunId);
  const [loading, setLoading] = useState(false);
  const [fullLedger, setFullLedger] = useState<LedgerEntry[]>([]);
  const [ledgerPage, setLedgerPage] = useState(0);
  const [loadingFullLedger, setLoadingFullLedger] = useState(false);
  const LEDGER_PAGE_SIZE = 50;

  const loadRuns = useCallback(async () => {
    try {
      const data = await listRuns(projectId);
      setRuns(data.runs || []);
    } catch {
      /* ignore */
    }
  }, [projectId]);

  const loadData = useCallback(async (runId: string) => {
    setLoading(true);
    try {
      const [detail, fup, bcf] = await Promise.all([
        getRunDetail(projectId, runId),
        getFollowups(projectId).catch(() => null),
        getBackflows(projectId).catch(() => null),
      ]);
      setRunDetail(detail);
      setFollowups(fup);
      setBackflows(bcf);
    } catch {
      toast.error("Failed to load run detail");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    if (selectedRunId) {
      loadData(selectedRunId);
    }
  }, [selectedRunId, loadData]);

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
        </div>

        {/* Run selector */}
        <div className="p-2 border-b">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">SELECT RUN</div>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {runs.map((run) => (
              <button
                key={run.run_id}
                className={`w-full text-left px-2 py-1 rounded text-[11px] hover:bg-muted transition-colors ${
                  selectedRunId === run.run_id ? "bg-primary/10 border border-primary/30" : ""
                }`}
                onClick={() => setSelectedRunId(run.run_id)}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono truncate">{run.run_id}</span>
                  {run.is_stub && (
                    <Badge variant="outline" className="text-[9px]">STUB</Badge>
                  )}
                </div>
                <div className="text-muted-foreground text-[10px]">
                  {run.round_id} · {run.current_state}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Navigation */}
        <div className="p-2 space-y-1 flex-1 overflow-y-auto">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">INTAKE WORKFLOW</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/intake`}>
              Intake Status
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/intake/classification`}>
              Classification Review
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/intake/human-gate`}>
              Human Gate
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/intake/locked-pack`}>
              Locked Pack
            </Link>
          </Button>
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1 mt-3">GATE PAGES</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/gate-1${selectedRunId ? `?run_id=${encodeURIComponent(selectedRunId)}` : ""}`}>
              G1 · Route Review
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/gate-3${selectedRunId ? `?run_id=${encodeURIComponent(selectedRunId)}` : ""}`}>
              G3 · BRR Review
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/artifacts${selectedRunId ? `?run_id=${encodeURIComponent(selectedRunId)}` : ""}`}>
              Artifacts Browser
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/compare`}>
              Rework Compare
            </Link>
          </Button>
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1 mt-3">INTEGRATION</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/integration`}>
              RMF × CER Integration
            </Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {runs.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-4 max-w-md">
              <div className="text-5xl">📋</div>
              <h2 className="text-xl font-semibold">No runs yet for this project</h2>
              <p className="text-sm text-muted-foreground">
                Upload evidence to start the first CER review run.
              </p>
              <div className="flex gap-3 justify-center pt-2">
                <Button asChild>
                  <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/upload`}>
                    Upload Evidence
                  </Link>
                </Button>
                <Button variant="outline" asChild>
                  <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/intake`}>
                    View Intake Status
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        ) : !selectedRunId ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Select a run from the sidebar</p>
          </div>
        ) : null}

        {selectedRunId && loading && (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Loading...</p>
          </div>
        )}

        {selectedRunId && runDetail && (
          <div className="max-w-5xl mx-auto">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-xl font-bold font-mono">{runDetail.run_id}</h1>
                <p className="text-sm text-muted-foreground">
                  {runDetail.project_id} · {runDetail.round_id} · State: {runDetail.current_state}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  {runDetail.is_stub && (
                    <Badge variant="outline" className="text-xs">STUB MODEL</Badge>
                  )}
                  {runDetail.model && (
                    <span className="text-xs text-muted-foreground">{runDetail.model}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                {user && (
                  <Badge variant="outline" className="text-xs">
                    {user.role}
                  </Badge>
                )}
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" asChild>
                    <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/gate-1?run_id=${encodeURIComponent(selectedRunId)}`}>
                      G1 Review
                    </Link>
                  </Button>
                  <Button variant="outline" size="sm" asChild>
                    <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/gate-3?run_id=${encodeURIComponent(selectedRunId)}`}>
                      G3 Review
                    </Link>
                  </Button>
                  <Button variant="outline" size="sm" asChild>
                    <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/upload`}>
                      Upload Evidence
                    </Link>
                  </Button>
                  <Button size="sm" asChild>
                    <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/upload/start-run`}>
                      Start Run
                    </Link>
                  </Button>
                </div>
              </div>
            </div>

            <Tabs defaultValue="overview">
              <TabsList className="mb-4">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="findings">Findings</TabsTrigger>
                <TabsTrigger value="ledger">Decision Ledger</TabsTrigger>
                <TabsTrigger value="state-log">State Transitions</TabsTrigger>
                <TabsTrigger value="followups">
                  Follow-ups {runDetail.followups_open > 0 && `(${runDetail.followups_open})`}
                </TabsTrigger>
                <TabsTrigger value="backflows">Backflows</TabsTrigger>
              </TabsList>

              {/* Overview */}
              <TabsContent value="overview">
                <div className="space-y-4">
                  {/* Lane Statuses */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Lane Statuses</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-4 gap-3">
                        {Object.entries(runDetail.lane_statuses).map(([lane, status]) => (
                          <div key={lane} className="flex items-center justify-between p-2 border rounded">
                            <span className="text-xs font-mono">{lane}</span>
                            <LaneStatusBadge status={status} />
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Gate Statuses */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Gate Statuses</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-4 gap-3">
                        {Object.entries(runDetail.gate_statuses).map(([gate, status]) => (
                          <div key={gate} className="flex items-center justify-between p-2 border rounded">
                            <span className="text-xs font-mono font-medium">{gate}</span>
                            <GateStatusBadge status={status} />
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Model Info */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Run Configuration</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <div className="text-xs text-muted-foreground">Model</div>
                          <div className="font-mono text-xs">{runDetail.model || "—"}</div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Execution Mode</div>
                          <div>{runDetail.execution_mode || "—"}</div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Stub</div>
                          <div>{runDetail.is_stub ? "Yes ⚠" : "No"}</div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Round</div>
                          <div className="font-mono">{runDetail.round_id}</div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Findings Summary */}
                  {runDetail.findings_summary && runDetail.findings_summary.length > 0 && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Findings Summary</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-48">
                          {JSON.stringify(runDetail.findings_summary, null, 2)}
                        </pre>
                      </CardContent>
                    </Card>
                  )}

                  {/* Bundle Lineage Summary */}
                  {runDetail.bundle_lineage_summary && runDetail.bundle_lineage_summary.length > 0 && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Bundle Lineage</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {runDetail.bundle_lineage_summary.map((lineage, i) => (
                            <div key={i} className="p-2 border rounded text-xs space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-mono font-semibold text-primary">
                                  {lineage.bundle_id || lineage.id || `bundle-${i}`}
                                </span>
                                {lineage.relation_type && (
                                  <Badge variant="outline" className="text-[10px]">{lineage.relation_type}</Badge>
                                )}
                              </div>
                              {lineage.source_bundle && (
                                <div className="text-muted-foreground">
                                  Source: <span className="font-mono">{lineage.source_bundle}</span>
                                </div>
                              )}
                              {lineage.derived_bundle && (
                                <div className="text-muted-foreground">
                                  Derived: <span className="font-mono">{lineage.derived_bundle}</span>
                                </div>
                              )}
                              {lineage.artifact_path && (
                                <div className="text-muted-foreground text-[10px]">
                                  Path: {lineage.artifact_path}
                                </div>
                              )}
                              {lineage.hash && (
                                <div className="text-muted-foreground text-[10px] font-mono">
                                  Hash: {lineage.hash}
                                </div>
                              )}
                              {lineage.created_at && (
                                <div className="text-muted-foreground text-[10px]">
                                  Created: {new Date(lineage.created_at).toLocaleString()}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {(!runDetail.bundle_lineage_summary || runDetail.bundle_lineage_summary.length === 0) && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Bundle Lineage</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-xs text-muted-foreground">No bundle lineage data available for this run.</p>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </TabsContent>

              {/* Findings Tab */}
              <TabsContent value="findings">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Findings Detail</CardTitle>
                    <CardDescription>Full findings from all review lanes</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {!runDetail.findings_summary || runDetail.findings_summary.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No findings available for this run.</p>
                    ) : (
                      <div className="space-y-3">
                        {runDetail.findings_summary.map((finding, i) => {
                          const severity = finding.severity || null;
                          return (
                            <div key={i} className="p-3 border rounded text-xs space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-mono font-bold text-primary">
                                  {finding.finding_id || finding.id || `finding-${i}`}
                                </span>
                                <div className="flex gap-1">
                                  {severity && (
                                    <Badge
                                      className={
                                        severity === "HIGH"
                                          ? "bg-red-100 text-red-800"
                                          : severity === "MEDIUM"
                                          ? "bg-yellow-100 text-yellow-800"
                                          : "bg-blue-100 text-blue-800"
                                      }
                                    >
                                      {severity}
                                    </Badge>
                                  )}
                                  {finding.category && (
                                    <Badge variant="outline" className="text-[10px]">{finding.category}</Badge>
                                  )}
                                  {finding.actionable && <Badge variant="outline" className="text-[10px]">actionable</Badge>}
                                  {finding.human_decision_required && (
                                    <Badge variant="destructive" className="text-[10px]">human review</Badge>
                                  )}
                                </div>
                              </div>
                              {finding.title && (
                                <div className="font-medium">{finding.title}</div>
                              )}
                              {finding.description && (
                                <div className="text-muted-foreground">{finding.description}</div>
                              )}
                              {finding.source_limitation_ref && (
                                <div className="text-muted-foreground text-[10px]">
                                  Limitation refs: {finding.source_limitation_ref}
                                </div>
                              )}
                              {finding.action && (
                                <div className="text-blue-600 text-[10px]">Action: {finding.action}</div>
                              )}
                              {finding.preliminary_judgment && (
                                <div className="text-yellow-600 text-[10px]">
                                  Preliminary: {finding.preliminary_judgment}
                                </div>
                              )}
                              {finding.status && (
                                <div className="text-muted-foreground text-[10px]">Status: {finding.status}</div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Decision Ledger */}
              <TabsContent value="ledger">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Decision Ledger</CardTitle>
                    <CardDescription>
                      {runDetail.ledger_total} entries total · append-only, immutable
                      {runDetail.ledger_total > 3 && fullLedger.length === 0 && (
                        <span className="ml-2 text-yellow-600">
                          (showing last 3 — {runDetail.ledger_total - 3} more)
                        </span>
                      )}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {runDetail.ledger_total > 3 && fullLedger.length === 0 && (
                      <div className="mb-3">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={async () => {
                            setLoadingFullLedger(true);
                            try {
                              const data = await getLedger(projectId);
                              setFullLedger(data.entries);
                            } catch {
                              toast.error("Failed to load full ledger");
                            } finally {
                              setLoadingFullLedger(false);
                            }
                          }}
                          disabled={loadingFullLedger}
                        >
                          {loadingFullLedger ? "Loading..." : `View all ${runDetail.ledger_total} entries`}
                        </Button>
                      </div>
                    )}
                    {(() => {
                      const entries = fullLedger.length > 0 ? fullLedger : runDetail.ledger_summary.entries;
                      const totalEntries = fullLedger.length > 0 ? fullLedger.length : entries.length;
                      const pageSize = LEDGER_PAGE_SIZE;
                      const currentPage = ledgerPage;
                      const totalPages = Math.ceil(totalEntries / pageSize);
                      const paginatedEntries = fullLedger.length > 0
                        ? entries.slice(currentPage * pageSize, (currentPage + 1) * pageSize)
                        : entries;
                      if (entries.length === 0) {
                        return <p className="text-sm text-muted-foreground">No ledger entries</p>;
                      }
                      return (
                        <>
                          <div className="space-y-2">
                            {paginatedEntries.map((entry) => (
                              <div key={entry.entry_id} className="p-3 border rounded text-xs">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="font-mono font-bold text-primary">{entry.entry_id}</span>
                                  <div className="flex items-center gap-2">
                                    {entry.gate && <Badge variant="outline" className="text-[10px]">{entry.gate}</Badge>}
                                    <Badge variant="secondary" className="text-[10px]">{entry.entry_type}</Badge>
                                  </div>
                                </div>
                                <div className="grid grid-cols-3 gap-2 text-muted-foreground">
                                  <div>
                                    <span className="font-medium">Actor:</span> {entry.actor}
                                  </div>
                                  <div>
                                    <span className="font-medium">From→To:</span> {entry.from_state || "—"} → {entry.to_state || "—"}
                                  </div>
                                  <div>
                                    <span className="font-medium">Time:</span> {new Date(entry.timestamp).toLocaleString()}
                                  </div>
                                </div>
                                {Object.keys(entry.decision_data).length > 0 && (
                                  <pre className="mt-2 text-[10px] bg-muted p-1.5 rounded overflow-auto">
                                    {JSON.stringify(entry.decision_data, null, 2)}
                                  </pre>
                                )}
                              </div>
                            ))}
                          </div>
                          {totalPages > 1 && (
                            <div className="flex items-center justify-between mt-4">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setLedgerPage((p) => Math.max(0, p - 1))}
                                disabled={currentPage === 0}
                              >
                                Previous
                              </Button>
                              <span className="text-xs text-muted-foreground">
                                Page {currentPage + 1} of {totalPages}
                              </span>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setLedgerPage((p) => Math.min(totalPages - 1, p + 1))}
                                disabled={currentPage >= totalPages - 1}
                              >
                                Next
                              </Button>
                            </div>
                          )}
                        </>
                      );
                    })()}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* State Transitions */}
              <TabsContent value="state-log">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">State Transition Log</CardTitle>
                    <CardDescription>JSONL append-only · ST-XXX auto-increment</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {runDetail.state_log_summary.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No state transitions</p>
                    ) : (
                      <div className="space-y-2">
                        {runDetail.state_log_summary.map((entry) => (
                          <div key={entry.entry_id} className="p-3 border rounded text-xs">
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-mono font-bold text-primary">{entry.entry_id}</span>
                              <Badge variant="outline" className="text-[10px]">
                                {entry.from_state} → {entry.to_state}
                              </Badge>
                            </div>
                            <div className="grid grid-cols-3 gap-2 text-muted-foreground">
                              <div>
                                <span className="font-medium">Actor:</span> {entry.actor}
                              </div>
                              <div>
                                <span className="font-medium">Trigger:</span> {entry.trigger || "—"}
                              </div>
                              <div>
                                <span className="font-medium">Duration:</span>{" "}
                                {entry.duration_sec != null ? `${entry.duration_sec}s` : "—"}
                              </div>
                            </div>
                            <div className="text-muted-foreground mt-1">
                              {new Date(entry.timestamp).toLocaleString()}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Follow-ups */}
              <TabsContent value="followups">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Follow-up Registry</CardTitle>
                    <CardDescription>
                      {followups ? `${followups.summary.open} open · ${followups.summary.resolved} resolved` : "Loading..."}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {!followups ? (
                      <p className="text-sm text-muted-foreground">Loading...</p>
                    ) : followups.follow_ups.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No follow-ups</p>
                    ) : (
                      <div className="space-y-2">
                        {followups.follow_ups.map((f) => (
                          <div key={f.follow_up_id} className="p-3 border rounded text-xs">
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-mono font-bold text-primary">{f.follow_up_id}</span>
                              <div className="flex items-center gap-2">
                                <Badge
                                  className={
                                    f.status === "OPEN"
                                      ? "bg-yellow-100 text-yellow-800"
                                      : f.status === "RESOLVED"
                                      ? "bg-green-100 text-green-800"
                                      : "bg-gray-100 text-gray-800"
                                  }
                                >
                                  {f.status}
                                </Badge>
                                <Badge variant="outline" className="text-[10px]">{f.type}</Badge>
                              </div>
                            </div>
                            <p className="text-sm">{f.description}</p>
                            <div className="flex items-center gap-3 mt-1 text-muted-foreground text-[10px]">
                              <span>Assigned: {f.assigned_to}</span>
                              {f.due_date && <span>Due: {f.due_date}</span>}
                              <span>{new Date(f.created_at).toLocaleDateString()}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Backflows */}
              <TabsContent value="backflows">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Backflow Registry</CardTitle>
                    <CardDescription>New evidence events that triggered rework cycles</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {!backflows ? (
                      <p className="text-sm text-muted-foreground">Loading...</p>
                    ) : backflows.backflows.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No backflows</p>
                    ) : (
                      <div className="space-y-2">
                        {backflows.backflows.map((b) => (
                          <div key={b.backflow_id} className="p-3 border rounded text-xs">
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-mono font-bold text-primary">{b.backflow_id}</span>
                              <Badge variant="outline" className="text-[10px]">{b.trigger_type}</Badge>
                            </div>
                            <p className="text-sm">{b.evidence_description}</p>
                            <div className="flex items-center gap-3 mt-1 text-muted-foreground text-[10px]">
                              <span>{b.source_round} → {b.new_round}</span>
                              <span>{new Date(b.created_at).toLocaleDateString()}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        )}
      </div>
    </div>
  );
}
