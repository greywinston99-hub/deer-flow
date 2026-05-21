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

interface Gate1BundleResponse {
  project_id: string;
  run_id: string;
  gate: string;
  scope: string;
  artifacts: GateBundleArtifact[];
  lane_2c_summary: {
    predicate_device: string | null;
    assessment_status: string | null;
    key_differences: string[];
    residual_uncertainty: string | null;
    mandatory_human_review: boolean | null;
  } | null;
  route_decision_summary: unknown | null;
}

interface GateBundleArtifact {
  artifact_name: string;
  lane: string | null;
  agent_id: string | null;
  path: string;
  size_bytes: number;
  modified_at: string;
}

interface GateAuditEntry {
  gate: string;
  decision: string;
  actor: string;
  timestamp: string;
  contributions_verified: unknown | null;
  conditional: boolean | null;
  outstanding_rework: unknown | null;
  file_path: string | null;
}

interface GateAuditResponse {
  project_id: string;
  gate: string;
  audits: GateAuditEntry[];
}

interface ArtifactContent {
  schema_name?: string;
  route_decision?: string;
  decision?: string;
  predicate_device?: string;
  assessment_status?: string;
  key_differences?: string[];
  residual_uncertainty?: string;
  mandatory_human_review?: boolean;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function getGate1Bundle(projectId: string, runId: string): Promise<Gate1BundleResponse> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/gate-1/bundle?run_id=${encodeURIComponent(runId)}`
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

async function getArtifactRaw(projectId: string, path: string): Promise<ArtifactContent> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/artifacts/${encodeURIComponent(path)}`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  // May return FileResponse or JSON
  const text = await r.text();
  try {
    return JSON.parse(text);
  } catch {
    return { raw_content: text } as ArtifactContent;
  }
}

async function submitGate1Decision(
  projectId: string,
  body: {
    run_id: string;
    round_id: string;
    decision: string;
    reviewer: string;
    rationale: string;
  }
): Promise<{ success: boolean; ledger_entry_id: string | null; error: string | null }> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/gate-1/decision`,
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
// Decision options for Gate 1
// ---------------------------------------------------------------------------

const GATE1_DECISIONS = [
  { value: "APPROVE_EQUIVALENCE_ROUTE", label: "APPROVE — Approve Equivalence Route" },
  { value: "REJECT_EQUIVALENCE_ROUTE", label: "REJECT — Reject Equivalence Route" },
  { value: "REQUIRE_LITERATURE_ROUTE", label: "LITERATURE — Require Literature Route" },
  { value: "CONDITIONAL_EQUIVALENCE", label: "CONDITIONAL — Conditional Equivalence" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Gate1ReviewPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = decodeURIComponent(String(params.project_id));
  const initialRunId = searchParams.get("run_id");
  const { user, loading: authLoading, canSubmitDecision } = useCERAuth();

  const [runs, setRuns] = useState<RunItem[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(initialRunId);
  const [bundle, setBundle] = useState<Gate1BundleResponse | null>(null);
  const [audit, setAudit] = useState<GateAuditResponse | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<GateBundleArtifact | null>(null);
  const [artifactContent, setArtifactContent] = useState<ArtifactContent | null>(null);
  const [loading, setLoading] = useState(false);

  // Decision form
  const [decision, setDecision] = useState("APPROVE_EQUIVALENCE_ROUTE");
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
    setArtifactContent(null);
    setSelectedArtifact(null);
    try {
      const [bundleData, auditData] = await Promise.all([
        getGate1Bundle(projectId, runId).catch(() => null),
        getGateAudit(projectId, "GATE_1").catch(() => null),
      ]);
      setBundle(bundleData);
      setAudit(auditData);
    } catch {
      toast.error("Failed to load Gate 1 bundle");
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

  const handleArtifactClick = useCallback(async (artifact: GateBundleArtifact) => {
    setSelectedArtifact(artifact);
    try {
      // Extract relative path from full path
      const pathParts = artifact.path.split("/artifacts/");
      const relativePath = pathParts[pathParts.length - 1] ?? artifact.path;
      const content = await getArtifactRaw(projectId, relativePath);
      setArtifactContent(content);
    } catch {
      setArtifactContent({ error: "Failed to load artifact" });
    }
  }, [projectId]);

  const handleSubmit = useCallback(async () => {
    if (!selectedRunId || !reviewer.trim()) {
      toast.error("Please enter reviewer name");
      return;
    }
    setSubmitting(true);
    try {
      const run = runs.find((r) => r.run_id === selectedRunId);
      const result = await submitGate1Decision(projectId, {
        run_id: selectedRunId,
        round_id: run?.round_id || "round_001",
        decision,
        reviewer: reviewer.trim(),
        rationale: rationale.trim(),
      });
      if (result.success) {
        toast.success(`Gate 1 decision recorded: LEDGER-${result.ledger_entry_id}`);
        // Reload bundle
        await loadBundle(selectedRunId);
      } else {
        toast.error(result.error || "Submission failed");
      }
    } catch (e) {
      toast.error(`Failed to submit: ${e}`);
    } finally {
      setSubmitting(false);
    }
  }, [selectedRunId, runs, projectId, decision, reviewer, rationale, loadBundle]);

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
          <h2 className="text-sm font-semibold">GATE 1 Review</h2>
          <p className="text-xs text-muted-foreground">Equivalence Route Adjudication</p>
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

        {/* Navigation */}
        <div className="p-2 space-y-1">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">NAVIGATE</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/gate-3${selectedRunId ? `?run_id=${encodeURIComponent(selectedRunId)}` : ""}`}>
              G3 · BRR Review →
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
            <p>Loading Gate 1 bundle...</p>
          </div>
        )}

        {selectedRunId && bundle && (
          <div className="max-w-6xl mx-auto">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Badge className="bg-yellow-100 text-yellow-800">GATE 1</Badge>
                  <Badge variant="outline">{bundle.scope}</Badge>
                </div>
                <h1 className="text-xl font-bold font-mono">Equivalence Route Review</h1>
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

            {/* Gate Audit Trail */}
            {audit && audit.audits.length > 0 && (
              <Card className="mb-4 border-blue-200 bg-blue-50/50">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-blue-800">Prior Gate 1 Decisions (Audit Record)</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {audit.audits.map((a) => (
                      <div key={a.timestamp} className="p-2 border border-yellow-200 rounded text-xs">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[10px]">{a.decision}</Badge>
                          <span className="text-muted-foreground">by {a.actor}</span>
                          <span className="text-muted-foreground ml-auto">
                            {new Date(a.timestamp).toLocaleString()}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            <div className="grid grid-cols-3 gap-4">
              {/* Left: Bundle artifacts */}
              <div className="col-span-2 space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Gate 1 Input Bundle</CardTitle>
                    <CardDescription>
                      {bundle.artifacts.length} artifact(s) — click to inspect
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {bundle.artifacts.map((artifact) => (
                        <button
                          key={artifact.path}
                          className={`w-full text-left p-3 border rounded hover:bg-muted/50 transition-colors ${
                            selectedArtifact?.path === artifact.path ? "border-primary bg-primary/5" : ""
                          }`}
                          onClick={() => handleArtifactClick(artifact)}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono font-medium text-sm">{artifact.artifact_name}</span>
                            <div className="flex items-center gap-2">
                              {artifact.lane && (
                                <Badge variant="outline" className="text-[10px]">{artifact.lane}</Badge>
                              )}
                              {artifact.agent_id && (
                                <Badge variant="secondary" className="text-[10px]">{artifact.agent_id}</Badge>
                              )}
                            </div>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {(artifact.size_bytes / 1024).toFixed(1)} KB ·{" "}
                            {new Date(artifact.modified_at).toLocaleString()}
                          </div>
                        </button>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Artifact Detail */}
                {selectedArtifact && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm font-mono">{selectedArtifact.artifact_name}</CardTitle>
                      <CardDescription>{selectedArtifact.path}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      {artifactContent ? (
                        <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-96">
                          {JSON.stringify(artifactContent, null, 2)}
                        </pre>
                      ) : (
                        <p className="text-sm text-muted-foreground">Loading artifact...</p>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Lane 2C Equivalence Summary */}
                {bundle.lane_2c_summary && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Lane 2C — Equivalence Assessment</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <div className="text-xs text-muted-foreground">Predicate Device</div>
                          <div className="font-medium">{bundle.lane_2c_summary.predicate_device || "—"}</div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Assessment Status</div>
                          <div className="font-medium">{bundle.lane_2c_summary.assessment_status || "—"}</div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Mandatory Human Review</div>
                          <div className={bundle.lane_2c_summary.mandatory_human_review ? "text-red-600 font-medium" : ""}>
                            {bundle.lane_2c_summary.mandatory_human_review ? "YES — Layer 3 Required" : "No"}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">Residual Uncertainty</div>
                          <div className="text-sm">{bundle.lane_2c_summary.residual_uncertainty || "—"}</div>
                        </div>
                      </div>
                      {bundle.lane_2c_summary.key_differences && bundle.lane_2c_summary.key_differences.length > 0 && (
                        <div className="mt-3">
                          <div className="text-xs text-muted-foreground mb-1">Key Differences</div>
                          {bundle.lane_2c_summary.key_differences.map((d, i) => (
                            <div key={i} className="text-xs py-0.5">• {d}</div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}
              </div>

              {/* Right: Decision form */}
              <div className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Submit Gate 1 Decision</CardTitle>
                    <CardDescription>
                      Route adjudication decision · writes to ledger and triggers state transition
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {!user ? (
                      <div className="bg-blue-50 border border-blue-200 rounded p-3">
                        <p className="text-xs text-blue-700 font-bold mb-1">No Role Selected</p>
                        <p className="text-[10px] text-blue-600 mb-2">
                          You must select a dev role to submit Gate 1 decisions. Use the role switcher in the top-right corner to select <strong>SENIOR_REVIEWER</strong> or <strong>ADMIN</strong> role.
                        </p>
                      </div>
                    ) : !canSubmitDecision ? (
                      <div className="bg-muted rounded p-3 text-xs text-muted-foreground">
                        <p className="font-medium mb-1">Decision submission restricted</p>
                        <p>
                          Your role (<strong>{user.role}</strong>) cannot submit Gate 1 decisions.
                          Requires <strong>SENIOR_REVIEWER</strong> or <strong>ADMIN</strong> role.
                          Use the role switcher to change your role.
                        </p>
                      </div>
                    ) : (
                      <>
                        <div className="space-y-2">
                          <label className="text-xs font-medium">Decision</label>
                          <Select value={decision} onValueChange={setDecision}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {GATE1_DECISIONS.map((opt) => (
                                <SelectItem key={opt.value} value={opt.value}>
                                  {opt.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

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
                            placeholder="Decision rationale..."
                            value={rationale}
                            onChange={(e) => setRationale(e.target.value)}
                            rows={4}
                            className="text-xs"
                          />
                        </div>

                        <div className="bg-yellow-50 border border-yellow-200 rounded p-2">
                          <p className="text-[10px] text-yellow-800">
                            <strong>Scope:</strong> GATE_1 adjudicates the equivalence route — whether the device
                            proceeds via equivalence pathway or requires full literature/clinical data route.
                            RISK_BENEFIT assessment is GATE_3 only.
                          </p>
                        </div>

                        <div className="bg-amber-50 border border-amber-200 rounded p-2">
                          <div className="flex items-start gap-2">
                            <input
                              type="checkbox"
                              id="g1-confirm"
                              checked={confirmed}
                              onChange={(e) => setConfirmed(e.target.checked)}
                              className="accent-amber-600 mt-0.5"
                            />
                            <label htmlFor="g1-confirm" className="text-[10px] text-amber-800">
                              I confirm this Gate 1 equivalence route decision. This action will transition
                              state S08→{decision === "APPROVE_EQUIVALENCE_ROUTE" ? "S09" : decision === "REJECT_EQUIVALENCE_ROUTE" ? "S10" : "S10"} and is irreversible.
                            </label>
                          </div>
                        </div>

                        <Button
                          className="w-full"
                          onClick={handleSubmit}
                          disabled={submitting || !reviewer.trim() || !confirmed}
                        >
                          {submitting ? "Submitting..." : "Submit Decision"}
                        </Button>
                      </>
                    )}
                  </CardContent>
                </Card>
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
