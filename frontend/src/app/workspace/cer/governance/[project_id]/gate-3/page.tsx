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
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cerReviewFetch, useCERAuth } from "@/core/cer_auth";
import { getBackendBaseURL } from "@/core/config";
import { CERDevRoleSwitcher } from "@/components/cer/dev-role-switcher";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LaneContribution {
  agent_id: string;
  agent_name: string;
  question: string;
  contribution_artifact: string | null;
  summary: string | null;
  status: "available" | "missing";
  missing_reason?: "historical_run" | "not_generated" | null;
}

interface Gate3BundleResponse {
  project_id: string;
  run_id: string;
  gate: string;
  scope: string;
  brr_only_location: boolean;
  contributions: LaneContribution[];
  layer3_items: {
    item: string;
    type: string;
    status: string;
    requires_human_review: boolean;
  }[];
  findings_summary: unknown[];
  rework_items: { item_id: string; description: string }[];
  is_stub: boolean;
}

interface GateAuditEntry {
  gate: string;
  decision: string;
  actor: string;
  timestamp: string;
  contributions_verified: Record<string, boolean> | null;
  conditional: boolean | null;
  outstanding_rework: string[] | null;
  file_path: string | null;
}

interface GateAuditResponse {
  project_id: string;
  gate: string;
  audits: GateAuditEntry[];
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function getGate3Bundle(projectId: string, runId: string): Promise<Gate3BundleResponse> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/gate-3/bundle?run_id=${encodeURIComponent(runId)}`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getGateAudit(projectId: string, gate: string): Promise<GateAuditResponse> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/gate-audit/${encodeURIComponent(gate)}`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function submitGate3Decision(
  projectId: string,
  body: {
    run_id: string;
    round_id: string;
    decision: string;
    conditional: boolean;
    outstanding_rework: string[];
    reviewer: string;
    reauth_timestamp: string;
    rationale: string;
  }
): Promise<{ success: boolean; ledger_entry_id: string | null; error: string | null; stub_blocked: boolean }> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/gate-3/decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function listRuns(projectId: string): Promise<{ runs: RunItem[] }> {
  const r = await cerReviewFetch(`${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/runs`);
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
// BRR Decision options
// ---------------------------------------------------------------------------

const BRR_DECISIONS = [
  { value: "BRR_ACCEPTABLE", label: "BRR ACCEPTABLE — Benefit-risk ratio is acceptable" },
  { value: "BRR_UNACCEPTABLE", label: "BRR UNACCEPTABLE — Benefit-risk ratio is not acceptable" },
  { value: "BRR_MISALIGNED", label: "BRR MISALIGNED — Benefit-risk is misaligned with intended use" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Gate3ReviewPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = decodeURIComponent(String(params.project_id));
  const initialRunId = searchParams.get("run_id");
  const { user, canSubmitDecision } = useCERAuth();

  const [runs, setRuns] = useState<RunItem[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(initialRunId);
  const [bundle, setBundle] = useState<Gate3BundleResponse | null>(null);
  const [audit, setAudit] = useState<GateAuditResponse | null>(null);
  const [loading, setLoading] = useState(false);

  // Decision form
  const [decision, setDecision] = useState("BRR_ACCEPTABLE");
  const [conditional, setConditional] = useState(false);
  const [outstandingRework, setOutstandingRework] = useState<string>("");
  const [reviewer, setReviewer] = useState("");
  const [rationale, setRationale] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  const loadRuns = useCallback(async () => {
    try {
      const data = await listRuns(projectId);
      setRuns(data.runs || []);
      if (!initialRunId && data.runs && data.runs.length > 0) {
        setSelectedRunId(data.runs[0]!.run_id);
      }
    } catch {
      /* ignore */
    }
  }, [projectId, initialRunId]);

  const loadBundle = useCallback(async (runId: string) => {
    setLoading(true);
    setBundle(null);
    setAudit(null);
    try {
      const [bundleData, auditData] = await Promise.all([
        getGate3Bundle(projectId, runId).catch(() => null),
        getGateAudit(projectId, "GATE_3").catch(() => null),
      ]);
      setBundle(bundleData);
      setAudit(auditData);
    } catch {
      toast.error("Failed to load Gate 3 bundle");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    if (selectedRunId) {
      loadBundle(selectedRunId);
    }
  }, [selectedRunId, loadBundle]);

  const handleSubmit = useCallback(async () => {
    if (!selectedRunId || !reviewer.trim()) {
      toast.error("Please enter reviewer name");
      return;
    }
    if (!bundle) return;

    setSubmitting(true);
    try {
      const run = runs.find((r) => r.run_id === selectedRunId);
      const reworkItems = outstandingRework
        ? outstandingRework.split(",").map((s) => s.trim()).filter(Boolean)
        : [];

      const result = await submitGate3Decision(projectId, {
        run_id: selectedRunId,
        round_id: run?.round_id || "round_001",
        decision,
        conditional,
        outstanding_rework: reworkItems,
        reviewer: reviewer.trim(),
        reauth_timestamp: new Date().toISOString(),
        rationale: rationale.trim(),
      });

      if (result.stub_blocked) {
        toast.error(`BLOCKED: ${result.error}`);
        return;
      }

      if (result.success) {
        toast.success(`Gate 3 BRR decision recorded: LEDGER-${result.ledger_entry_id}`);
        await loadBundle(selectedRunId);
      } else {
        toast.error(result.error || "Submission failed");
      }
    } catch (e) {
      toast.error(`Failed to submit: ${e}`);
    } finally {
      setSubmitting(false);
    }
  }, [selectedRunId, runs, projectId, decision, conditional, outstandingRework, reviewer, rationale, bundle, loadBundle]);

  return (
    <>
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
          <h2 className="text-sm font-semibold">GATE 3 Review</h2>
          <p className="text-xs text-muted-foreground">Benefit-Risk Assessment (BRR)</p>
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
                <div className="text-muted-foreground text-[10px]">{run.round_id} · {run.current_state}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Stub warning */}
        {bundle?.is_stub && (
          <div className="p-3 border-b bg-red-50">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-red-600 font-bold text-xs">⚠ STUB MODEL</span>
            </div>
            <p className="text-[10px] text-red-700">
              This run used a stub model. BRR decisions are BLOCKED for stub models.
              A real model is required to issue RISK_BENEFIT terminal decisions.
            </p>
          </div>
        )}

        {/* Navigation */}
        <div className="p-2 space-y-1 flex-1 overflow-y-auto">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">NAVIGATE</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/gate-1${selectedRunId ? `?run_id=${encodeURIComponent(selectedRunId)}` : ""}`}>
              ← G1 Route Review
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
        {!selectedRunId && (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Select a run from the sidebar</p>
          </div>
        )}

        {selectedRunId && loading && (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Loading Gate 3 bundle...</p>
          </div>
        )}

        {selectedRunId && bundle && (
          <div className="max-w-6xl mx-auto">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Badge className="bg-purple-100 text-purple-800">GATE 3</Badge>
                  <Badge variant="outline">{bundle.scope}</Badge>
                  {bundle.is_stub && (
                    <Badge variant="destructive" className="text-xs">STUB BLOCKED</Badge>
                  )}
                </div>
                <h1 className="text-xl font-bold font-mono">Benefit-Risk Assessment Review</h1>
                <p className="text-sm text-muted-foreground">
                  {projectId} · Run: {selectedRunId}
                </p>
              </div>
              {user && (
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-xs">
                    {user.role}
                  </Badge>
                  <span className="text-xs text-muted-foreground">{user.name}</span>
                </div>
              )}
            </div>

            {/* Hard Constraint Banner */}
            <Card className="mb-4 border-purple-200 bg-purple-50/50">
              <CardContent className="p-3">
                <div className="flex items-start gap-2">
                  <span className="text-purple-700 font-bold text-sm mt-0.5">⚡</span>
                  <div className="text-xs text-purple-800">
                    <strong>Hard Constraint:</strong> BRR_ACCEPTABLE / BRR_UNACCEPTABLE / BRR_MISALIGNED terminal
                    decisions can ONLY be issued from this page (GATE_3). No other gate may issue a RISK_BENEFIT
                    decision. Stub model runs are blocked from issuing BRR decisions.
                    <br />
                    <strong>BRR Composite Sources:</strong> AG-003 (Claim Scope) · AG-004 (SOTA Evidence) ·
                    AG-005 (Equivalence) · AG-006 (Consistency) · AG-007 (PMCF Adequacy)
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Prior Decisions */}
            {audit && audit.audits.length > 0 && (
              <Card className="mb-4 border-purple-200">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-purple-800">Prior Gate 3 BRR Decisions</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {audit.audits.map((a) => (
                      <div key={a.timestamp} className="p-2 border border-purple-200 rounded text-xs">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="outline" className="text-[10px]">{a.decision}</Badge>
                          {a.conditional && <Badge variant="secondary" className="text-[10px]">CONDITIONAL</Badge>}
                          <span className="text-muted-foreground">by {a.actor}</span>
                          <span className="text-muted-foreground ml-auto">
                            {new Date(a.timestamp).toLocaleString()}
                          </span>
                        </div>
                        {a.contributions_verified && (
                          <div className="flex gap-1 flex-wrap">
                            {Object.entries(a.contributions_verified).map(([agent, verified]) => (
                              <Badge
                                key={agent}
                                className={`text-[9px] ${verified ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}
                              >
                                {agent}: {verified ? "✓" : "✗"}
                              </Badge>
                            ))}
                          </div>
                        )}
                        {a.outstanding_rework && a.outstanding_rework.length > 0 && (
                          <div className="text-muted-foreground mt-1">
                            Rework items: {a.outstanding_rework.join(", ")}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            <div className="grid grid-cols-3 gap-4">
              {/* Left: BRR Contributions */}
              <div className="col-span-2 space-y-4">
                {/* 5-Agent BRR Composite */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">BRR Composite — 5-Agent Contributions</CardTitle>
                    <CardDescription>
                      GATE_3-only RISK_BENEFIT composite · AG-003 through AG-007
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {bundle.contributions.map((contrib) => (
                        <div
                          key={contrib.agent_id}
                          className={`p-3 border rounded ${
                            contrib.status === "missing" ? "bg-muted/30 opacity-75" : ""
                          }`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <Badge
                                className={
                                  contrib.agent_id === "AG-007"
                                    ? "bg-purple-100 text-purple-800"
                                    : "bg-blue-100 text-blue-800"
                                }
                              >
                                {contrib.agent_id}
                              </Badge>
                              <span className="text-sm font-medium">{contrib.agent_name}</span>
                              {contrib.status === "missing" && contrib.missing_reason === "historical_run" && (
                                <Badge variant="outline" className="text-[9px] border-yellow-300 text-yellow-700">HISTORICAL</Badge>
                              )}
                              {contrib.status === "missing" && contrib.missing_reason !== "historical_run" && (
                                <Badge variant="destructive" className="text-[9px]">MISSING</Badge>
                              )}
                              {contrib.status === "available" && (
                                <Badge className="text-[9px] bg-green-100 text-green-800">AVAILABLE</Badge>
                              )}
                            </div>
                            <Badge variant="outline" className="text-[10px]">{contrib.question}</Badge>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Artifact:{" "}
                            <span className="font-mono">
                              {contrib.contribution_artifact ?? "(not generated)"}
                            </span>
                          </div>
                          {contrib.status === "missing" && contrib.missing_reason === "historical_run" && (
                            <p className="text-xs mt-1 text-yellow-700 bg-yellow-50 p-2 rounded">
                              Historical run — BRR contributions incomplete. This artifact was not part of the original run.
                            </p>
                          )}
                          {contrib.status === "missing" && contrib.missing_reason === "not_generated" && (
                            <p className="text-xs mt-1 text-red-600 bg-red-50 p-2 rounded">
                              MISSING — expected artifact not generated. This may indicate a pipeline issue.
                            </p>
                          )}
                          {contrib.summary && (
                            <p className="text-xs mt-1 bg-muted p-2 rounded">{contrib.summary}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Layer 3 Items */}
                {bundle.layer3_items.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Layer 3 Items — Human Judgment Required</CardTitle>
                      <CardDescription>
                        Items flagged for mandatory human review at equivalence/data-sufficiency/benefit-risk
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {bundle.layer3_items.map((item, i) => (
                          <div key={i} className="p-3 border border-purple-200 rounded bg-purple-50/50">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge variant="outline" className="text-[10px]">{item.type}</Badge>
                              <Badge className="text-[10px] bg-purple-100 text-purple-800">L3</Badge>
                            </div>
                            <div className="text-sm font-medium">{item.item}</div>
                            <div className="text-xs text-muted-foreground mt-1">Status: {item.status}</div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Rework Items */}
                {bundle.rework_items.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Rework Items</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-1">
                        {bundle.rework_items.map((item) => (
                          <div key={item.item_id} className="text-xs py-1 border-b last:border-0">
                            <span className="font-mono font-bold">{item.item_id}:</span>{" "}
                            {item.description}
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Findings */}
                {bundle.findings_summary && bundle.findings_summary.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Findings</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-48">
                        {JSON.stringify(bundle.findings_summary, null, 2)}
                      </pre>
                    </CardContent>
                  </Card>
                )}
              </div>

              {/* Right: Decision form */}
              <div className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Submit BRR Terminal Decision</CardTitle>
                    <CardDescription>
                      RISK_BENEFIT decision · GATE_3 only · writes to immutable ledger
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Stub Block — fires BEFORE role check (hard constraint) */}
                    {bundle.is_stub ? (
                      <div className="bg-red-100 border border-red-300 rounded p-3">
                        <p className="text-xs text-red-700 font-bold mb-1">BRR Decision Blocked</p>
                        <p className="text-[10px] text-red-600">
                          This run used a stub model. Stub models cannot issue RISK_BENEFIT terminal decisions.
                          Only real model runs may submit BRR decisions.
                        </p>
                      </div>
                    ) : !user ? (
                      <div className="bg-blue-50 border border-blue-200 rounded p-3">
                        <p className="text-xs text-blue-700 font-bold mb-1">No Role Selected</p>
                        <p className="text-[10px] text-blue-600 mb-2">
                          You must select a dev role to submit BRR decisions. Use the role switcher in the top-right corner to select <strong>SENIOR_REVIEWER</strong> or <strong>ADMIN</strong> role.
                        </p>
                      </div>
                    ) : !canSubmitDecision ? (
                      <div className="bg-muted rounded p-3 text-xs text-muted-foreground">
                        <p className="font-medium mb-1">Decision submission restricted</p>
                        <p>
                          Your role (<strong>{user.role}</strong>) cannot submit Gate 3 BRR decisions.
                          BRR terminal decisions (ACCEPTABLE/UNACCEPTABLE/MISALIGNED) require
                          <strong>SENIOR_REVIEWER</strong> or <strong>ADMIN</strong> role.
                          Use the role switcher to change your role.
                        </p>
                      </div>
                    ) : (
                      <>
                        <div className="space-y-2">
                          <label className="text-xs font-medium">BRR Decision</label>
                          <Select value={decision} onValueChange={setDecision}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {BRR_DECISIONS.map((opt) => (
                                <SelectItem key={opt.value} value={opt.value}>
                                  {opt.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            id="conditional"
                            checked={conditional}
                            onChange={(e) => setConditional(e.target.checked)}
                            className="accent-purple-600"
                          />
                          <label htmlFor="conditional" className="text-xs">
                            Conditional pass (outstanding rework items)
                          </label>
                        </div>

                        {conditional && (
                          <div className="space-y-2">
                            <label className="text-xs font-medium">Outstanding Rework Items</label>
                            <Textarea
                              placeholder="R-001, R-002, ..."
                              value={outstandingRework}
                              onChange={(e) => setOutstandingRework(e.target.value)}
                              rows={2}
                              className="text-xs"
                            />
                          </div>
                        )}

                        <div className="space-y-2">
                          <label className="text-xs font-medium">Reviewer</label>
                          <Input
                            placeholder="Reviewer name or ID"
                            value={reviewer}
                            onChange={(e) => setReviewer(e.target.value)}
                            className="text-xs"
                          />
                        </div>

                        <div className="space-y-2">
                          <label className="text-xs font-medium">Rationale</label>
                          <Textarea
                            placeholder="BRR decision rationale..."
                            value={rationale}
                            onChange={(e) => setRationale(e.target.value)}
                            rows={4}
                            className="text-xs"
                          />
                        </div>

                        <div className="bg-red-50 border border-red-200 rounded p-2">
                          <div className="flex items-start gap-2">
                            <input
                              type="checkbox"
                              id="g3-confirm"
                              checked={confirmed}
                              onChange={(e) => setConfirmed(e.target.checked)}
                              className="accent-red-600 mt-0.5"
                            />
                            <label htmlFor="g3-confirm" className="text-[10px] text-red-800">
                              I confirm this BRR terminal decision: <strong>{decision}</strong>.
                              This will transition state S11→{decision === "BRR_ACCEPTABLE" ? "S12" : "S17"} and is irreversible.
                            </label>
                          </div>
                        </div>

                        <Button
                          className="w-full"
                          variant="destructive"
                          onClick={handleSubmit}
                          disabled={submitting || !reviewer.trim() || !confirmed}
                        >
                          {submitting ? "Submitting..." : "Issue BRR Terminal Decision"}
                        </Button>
                      </>
                    )}
                  </CardContent>
                </Card>

                {/* Contribution Verification */}
                {!bundle.is_stub && canSubmitDecision && bundle.contributions.length > 0 && (
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-xs">5-Agent BRR Composite</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-1">
                        {bundle.contributions.map((contrib) => (
                          <div key={contrib.agent_id} className="flex items-center justify-between text-xs">
                            <span className="font-mono">{contrib.agent_id}</span>
                            <Badge
                              className={`text-[9px] ${
                                contrib.status === "available"
                                  ? "bg-green-100 text-green-800"
                                  : "bg-red-100 text-red-800"
                              }`}
                            >
                              {contrib.status === "available" ? `${contrib.agent_name} ✓` : "MISSING ✗"}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>

    {/* Dev-only role switcher overlay */}
    <CERDevRoleSwitcher />
    </>
  );
}
