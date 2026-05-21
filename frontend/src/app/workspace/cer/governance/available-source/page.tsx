"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
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
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cerReviewFetch } from "@/core/cer_auth/api";
import { getBackendBaseURL } from "@/core/config";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SourceInventoryItem {
  source_id: string;
  source_name: string;
  source_path: string | null;
  status: string;
  availability_note: string | null;
}

interface SourceLimitationItem {
  limitation_id: string;
  category: string;
  source_gap: string;
  impact: string;
  allowed_workflow: string[];
  prohibited_claim: string;
  blocks_full_review: boolean;
  blocks_limited_workflow: boolean;
  human_caution: string | null;
}

interface EquivalenceWorkbenchItem {
  item_id: string;
  dimension: string;
  aspect: string;
  baxter_evidence: string | null;
  nipro_evidence: string | null;
  gap_description: string | null;
  reviewer_question: string | null;
  limitation_ref: string | null;
}

interface PMCFLinkageItem {
  item_id: string;
  dimension: string;
  cer_claim: string | null;
  pmcf_plan_claim: string | null;
  linkage_status: string;
  gap_description: string | null;
  reviewer_question: string | null;
  limitation_ref: string | null;
}

interface ReviewerFindingItem {
  finding_id: string;
  category: string;
  title: string;
  description: string;
  source_limitation_ref: string | null;
  severity: string | null;
  actionable: boolean;
  action: string | null;
  human_decision_required: boolean;
  preliminary_judgment: string | null;
}

interface NonClaimItem {
  claim_type: string;
  non_claim: string;
  reason: string;
}

interface DowngradeDecision {
  original_mode: string;
  assigned_mode: string;
  downgrade_reason: string;
  blocking_limitations: string[];
  can_claim_full_review: boolean;
  can_claim_limited_review: boolean;
  can_claim_available_source_review: boolean;
}

interface AvailableSourceWorkflowResponse {
  workflow_run_id: string;
  project_id: string;
  project_name: string;
  status: string;
  workflow_mode: string;
  downgrade_decision: DowngradeDecision | null;
  source_inventory: SourceInventoryItem[];
  source_limitation_register: SourceLimitationItem[];
  equivalence_workbench: EquivalenceWorkbenchItem[] | null;
  pmcf_linkage_workbench: PMCFLinkageItem[] | null;
  reviewer_findings: ReviewerFindingItem[];
  non_claims: NonClaimItem[];
  next_state: string;
  boundaries_applied: Record<string, boolean>;
  generated_at: string;
}

// ---------------------------------------------------------------------------
// Source Package Intake Bridge Types
// ---------------------------------------------------------------------------

// Note: prepare endpoint only returns scanned_files_count, not full file list
// ClassificationCandidate is defined for type documentation

interface ClassificationCandidate {
  file_name: string;
  document_type: string;
  confidence: number;
  matched_keywords: string[];
  reason: string;
  requires_human_confirmation: boolean;
  is_true_source_candidate: boolean;
}

interface SourceDocumentOut {
  document_id: string;
  document_type: string;
  file_name: string;
  version_status: string;
  availability: string;
  classification_confidence: number;
  is_true_source: boolean;
  requires_human_confirmation: boolean;
  notes?: string;
}

interface SourceStatusOut {
  ifu_available: boolean;
  cer_available: boolean;
  rmf_available: boolean;
  risk_related_source_available: boolean;
  equivalence_available: boolean;
  pmcf_available: boolean;
  pms_available: boolean;
  gspr_available: boolean;
  sscp_available: boolean;
}

interface AvailableSourceRequestPreview {
  project_id: string;
  project_name: string;
  workflow_mode: string;
  source_package_ref: string | null;
  review_scope: string[];
  official_cear_allowed: boolean;
  final_regulatory_decision_allowed: boolean;
  production_claim_allowed: boolean;
  source_status: SourceStatusOut;
  source_documents_count: number;
  human_confirmation_required: boolean;
}

interface HumanConfirmationPacket {
  status: string;
  project_id: string;
  project_name: string;
  source_package_path: string;
  scanned_files_count: number;
  high_confidence_count: number;
  low_confidence_count: number;
  classification_candidates: ClassificationCandidate[];
  source_status: SourceStatusOut;
  source_documents_preview: SourceDocumentOut[];
  available_source_request_preview: AvailableSourceRequestPreview;
  warnings: string[];
  recommended_actions: string[];
}

interface SourcePackagePrepareResponse {
  prepare_id: string;
  project_id: string;
  project_name: string;
  source_package_path: string;
  status: string;
  scanned_files_count: number;
  classification_candidates_count: number;
  source_documents_count: number;
  source_status: SourceStatusOut;
  available_source_request: Record<string, unknown> | null;
  human_confirmation_packet: HumanConfirmationPacket;
  warnings: string[];
  generated_at: string;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

async function runAvailableSourceWorkflow(request: {
  project_id: string;
  project_name: string;
  workflow_mode: string;
  source_package_ref: string | null;
  known_limitations_ref: string | null;
  review_scope: string[];
  official_cear_allowed: boolean;
  final_regulatory_decision_allowed: boolean;
  production_claim_allowed: boolean;
  ifu_available: boolean;
  cer_available: boolean;
  rmf_available: boolean;
  risk_related_available: boolean;
  equivalence_available: boolean;
  pmcf_available: boolean;
  pms_available: boolean;
  gspr_available: boolean;
  sscp_available: boolean;
}): Promise<AvailableSourceWorkflowResponse> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/workflows/available-source/run`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }
  );
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
    throw new Error(err.detail ?? `HTTP ${r.status}`);
  }
  return r.json() as Promise<AvailableSourceWorkflowResponse>;
}

async function scanSourcePackage(request: {
  project_id: string;
  project_name: string;
  source_package_path: string;
  recursive?: boolean;
  max_files?: number;
  scan_mode?: string;
  human_confirmation_required?: boolean;
}): Promise<SourcePackagePrepareResponse> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/intake/source-package/prepare`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }
  );
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
    throw new Error(err.detail ?? `HTTP ${r.status}`);
  }
  return r.json() as Promise<SourcePackagePrepareResponse>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function SourceStatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    TRUE_SOURCE: "bg-green-100 text-green-800",
    PARTIAL_SOURCE: "bg-yellow-100 text-yellow-800",
    SOURCE_UNAVAILABLE: "bg-red-100 text-red-800",
    SOURCE_NOT_FOUND: "bg-gray-100 text-gray-800",
  };
  return <Badge className={variants[status] ?? "bg-gray-100"}>{status}</Badge>;
}

function SeverityBadge({ severity }: { severity: string | null }) {
  if (!severity) return null;
  const variants: Record<string, string> = {
    HIGH: "bg-red-100 text-red-800",
    MEDIUM: "bg-yellow-100 text-yellow-800",
    LOW: "bg-blue-100 text-blue-800",
  };
  return <Badge className={variants[severity] ?? "bg-gray-100"}>{severity}</Badge>;
}

function LinkageStatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    linked: "bg-green-100 text-green-800",
    partial: "bg-yellow-100 text-yellow-800",
    missing: "bg-red-100 text-red-800",
    not_applicable: "bg-gray-100 text-gray-800",
  };
  return <Badge className={variants[status] ?? "bg-gray-100"}>{status}</Badge>;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AvailableSourceWorkflowPage() {
  // Project fields
  const [projectId, setProjectId] = useState("");
  const [projectName, setProjectName] = useState("");
  const [sourcePackageRef, setSourcePackageRef] = useState("");
  const [knownLimitationsRef, setKnownLimitationsRef] = useState("");

  // Source status fields
  const [ifuAvailable, setIfuAvailable] = useState(true);
  const [cerAvailable, setCerAvailable] = useState(true);
  const [rmfAvailable, setRmfAvailable] = useState(false);
  const [riskRelatedAvailable, setRiskRelatedAvailable] = useState(false);
  const [equivalenceAvailable, setEquivalenceAvailable] = useState(true);
  const [pmcfAvailable, setPmcfAvailable] = useState(true);
  const [pmsAvailable, setPmsAvailable] = useState(false);
  const [gsprAvailable, setGsprAvailable] = useState(false);
  const [sscpAvailable, setSscpAvailable] = useState(false);

  // Review scope
  const [reviewScope, setReviewScope] = useState<string[]>([
    "source_inventory",
    "ifu_cer_linkage",
    "rmf_gap_impact",
    "equivalence_workbench",
    "pmcf_linkage_workbench",
    "reviewer_packet",
  ]);

  // Response state
  const [response, setResponse] = useState<AvailableSourceWorkflowResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Source Package Intake Bridge state
  const [inputMode, setInputMode] = useState<"manual" | "bridge">("manual");
  const [sourcePackagePath, setSourcePackagePath] = useState("");
  const [bridgeResponse, setBridgeResponse] = useState<SourcePackagePrepareResponse | null>(null);
  const [bridgeError, setBridgeError] = useState<string | null>(null);
  const [bridgeLoading, setBridgeLoading] = useState(false);

  const handleScanPackage = useCallback(async () => {
    if (!projectId.trim()) {
      toast.error("Project ID is required before scanning");
      return;
    }
    if (!projectName.trim()) {
      toast.error("Project Name is required before scanning");
      return;
    }
    if (!sourcePackagePath.trim()) {
      toast.error("Source package path is required");
      return;
    }

    setBridgeLoading(true);
    setBridgeError(null);
    setBridgeResponse(null);

    try {
      const result = await scanSourcePackage({
        project_id: projectId.trim(),
        project_name: projectName.trim(),
        source_package_path: sourcePackagePath.trim(),
        recursive: true,
        max_files: 200,
        scan_mode: "metadata_only",
        human_confirmation_required: true,
      });
      setBridgeResponse(result);
      toast.success(`Scan complete: ${result.scanned_files_count} files, ${result.classification_candidates_count} candidates`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setBridgeError(msg);
      toast.error(`Scan failed: ${msg}`);
    } finally {
      setBridgeLoading(false);
    }
  }, [projectId, projectName, sourcePackagePath]);

  const handleRunFromBridge = useCallback(async () => {
    if (!bridgeResponse?.available_source_request) {
      toast.error("No available-source request generated. Please scan first.");
      return;
    }

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      // Use the available_source_request directly from bridge response
      const request = bridgeResponse.available_source_request as unknown as Parameters<typeof runAvailableSourceWorkflow>[0];
      const result = await runAvailableSourceWorkflow(request);
      setResponse(result);
      toast.success(`Workflow completed: ${result.workflow_run_id}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(`Workflow failed: ${msg}`);
    } finally {
      setLoading(false);
    }
  }, [bridgeResponse]);

  const handleRun = useCallback(async () => {
    if (!projectId.trim() || !projectName.trim()) {
      toast.error("Project ID and Project Name are required");
      return;
    }

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const result = await runAvailableSourceWorkflow({
        project_id: projectId.trim(),
        project_name: projectName.trim(),
        workflow_mode: "AVAILABLE_SOURCE_LIMITED",
        source_package_ref: sourcePackageRef.trim() || null,
        known_limitations_ref: knownLimitationsRef.trim() || null,
        review_scope: reviewScope,
        official_cear_allowed: false,
        final_regulatory_decision_allowed: false,
        production_claim_allowed: false,
        ifu_available: ifuAvailable,
        cer_available: cerAvailable,
        rmf_available: rmfAvailable,
        risk_related_available: riskRelatedAvailable,
        equivalence_available: equivalenceAvailable,
        pmcf_available: pmcfAvailable,
        pms_available: pmsAvailable,
        gspr_available: gsprAvailable,
        sscp_available: sscpAvailable,
      });
      setResponse(result);
      toast.success(`Workflow completed: ${result.workflow_run_id}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(`Workflow failed: ${msg}`);
    } finally {
      setLoading(false);
    }
  }, [projectId, projectName, sourcePackageRef, knownLimitationsRef, reviewScope,
      ifuAvailable, cerAvailable, rmfAvailable, riskRelatedAvailable,
      equivalenceAvailable, pmcfAvailable, pmsAvailable, gsprAvailable, sscpAvailable]);

  const toggleScope = useCallback((item: string) => {
    setReviewScope(prev =>
      prev.includes(item) ? prev.filter(s => s !== item) : [...prev, item]
    );
  }, []);

  const isMissingIFU = response?.source_inventory.some(
    s => s.source_id === "ifu" && (s.status === "SOURCE_UNAVAILABLE" || s.status === "SOURCE_NOT_FOUND")
  ) ?? false;

  const isMissingRMF = response?.source_inventory.some(
    s => s.source_id === "rmf" && (s.status === "SOURCE_UNAVAILABLE" || s.status === "SOURCE_NOT_FOUND")
  ) ?? false;

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
          <h2 className="text-sm font-semibold">Available Source Workflow</h2>
          <p className="text-xs text-muted-foreground mt-1">CER/RMF Source-Bounded Review</p>
        </div>

        {/* Navigation */}
        <div className="p-2 space-y-1 flex-1 overflow-y-auto">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">WORKFLOWS</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href="/workspace/cer/governance/run-home">Run Home</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href="/workspace/cer/governance/new-project">New Project</Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-6xl mx-auto space-y-6">
          {/* Header */}
          <div>
            <h1 className="text-xl font-bold">Available Source Workflow</h1>
            <p className="text-sm text-muted-foreground">
              Source-bounded CER/RMF review — generates source inventory, workbenches, and reviewer findings.
              This is NOT an official CEAR. This is NOT a regulatory submission.
            </p>
          </div>

          {/* Non-claims banner */}
          <Card className="border-red-200 bg-red-50/50">
            <CardContent className="pt-4">
              <div className="flex items-start gap-3">
                <span className="text-2xl">⚠️</span>
                <div className="space-y-1 text-sm">
                  <p className="font-semibold text-red-800">Boundary Constraints — Always Active</p>
                  <ul className="space-y-0.5 text-xs text-red-700 list-disc list-inside">
                    <li>Official CEAR has NOT been generated</li>
                    <li>No final clinical/regulatory decision has been made</li>
                    <li>No production-ready claim is made</li>
                    <li>No approved/active/reusable asset has been created</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Source Package Path Intake */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Source Package Path Intake</CardTitle>
              <CardDescription>
                Scan a source package folder to auto-classify documents and derive source availability.
                An alternative to manual source status toggles.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Input Mode Toggle */}
              <div className="flex gap-2 border-b pb-3">
                <Button
                  variant={inputMode === "bridge" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setInputMode("bridge")}
                >
                  Scan Package Path
                </Button>
                <Button
                  variant={inputMode === "manual" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setInputMode("manual")}
                >
                  Manual Source Status
                </Button>
              </div>

              {inputMode === "bridge" && (
                <div className="space-y-4">
                  {/* Project and Path Fields */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="space-y-1">
                      <Label htmlFor="bridge_project_id">Project ID *</Label>
                      <Input
                        id="bridge_project_id"
                        value={projectId}
                        onChange={e => setProjectId(e.target.value)}
                        placeholder="e.g. seed_project_07"
                        className="font-mono text-xs"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="bridge_project_name">Project Name *</Label>
                      <Input
                        id="bridge_project_name"
                        value={projectName}
                        onChange={e => setProjectName(e.target.value)}
                        placeholder="e.g. CER Review Phase C"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="source_package_path">Source Package Path *</Label>
                      <Input
                        id="source_package_path"
                        value={sourcePackagePath}
                        onChange={e => setSourcePackagePath(e.target.value)}
                        placeholder="/path/to/source/package"
                        className="text-xs"
                      />
                    </div>
                  </div>

                  {/* Scan Options */}
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span>recursive: true</span>
                    <span>max_files: 200</span>
                    <span>scan_mode: metadata_only</span>
                    <span>human_confirmation_required: true</span>
                  </div>

                  {/* Scan Button */}
                  <div className="flex gap-3">
                    <Button
                      onClick={handleScanPackage}
                      disabled={bridgeLoading}
                      variant="default"
                    >
                      {bridgeLoading ? "Scanning..." : "🔍 Scan & Classify Source Package"}
                    </Button>
                    {bridgeResponse && (
                      <Button
                        onClick={handleRunFromBridge}
                        disabled={loading}
                        variant="default"
                        size="lg"
                        className="bg-green-600 hover:bg-green-700"
                      >
                        {loading ? "Running..." : "▶ Run Available-Source Workflow (from Bridge)"}
                      </Button>
                    )}
                  </div>

                  {/* Bridge Error */}
                  {bridgeError && (
                    <Card className="border-red-300 bg-red-50">
                      <CardContent className="pt-4">
                        <div className="text-sm text-red-700">
                          <span className="font-semibold">Scan Error:</span> {bridgeError}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Bridge Response Preview */}
                  {bridgeResponse && (
                    <div className="space-y-4">
                      {/* Scan Summary */}
                      <Card className="border-blue-200 bg-blue-50/30">
                        <CardContent className="pt-4">
                          <div className="flex items-center gap-3 text-sm">
                            <Badge className="bg-blue-100 text-blue-800">{bridgeResponse.status}</Badge>
                            <span className="text-muted-foreground">
                              {bridgeResponse.scanned_files_count} files scanned,{" "}
                              {bridgeResponse.classification_candidates_count} candidates,{" "}
                              {bridgeResponse.source_documents_count} documents
                            </span>
                          </div>
                        </CardContent>
                      </Card>

                      {/* Bridge Warnings */}
                      {bridgeResponse.warnings.length > 0 && (
                        <Card className="border-yellow-200 bg-yellow-50/30">
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm text-yellow-800">⚠️ Warnings</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <ul className="text-xs text-yellow-700 list-disc list-inside space-y-0.5">
                              {bridgeResponse.warnings.map((w, i) => (
                                <li key={i}>{w}</li>
                              ))}
                            </ul>
                          </CardContent>
                        </Card>
                      )}

                      {/* Human Confirmation Panel */}
                      <Card className="border-orange-200 bg-orange-50/30">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm text-orange-800">
                            Human Confirmation Required
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                          <div className="text-xs text-orange-700">
                            Status: <span className="font-semibold">{bridgeResponse.human_confirmation_packet.status}</span>
                          </div>
                          <div className="text-xs text-orange-700">
                            Classification is NOT human-confirmed yet. Review before running workflow.
                          </div>
                          {bridgeResponse.human_confirmation_packet.low_confidence_count > 0 && (
                            <div className="text-xs text-red-600">
                              ⚠️ {bridgeResponse.human_confirmation_packet.low_confidence_count} low-confidence items need review
                            </div>
                          )}
                          {bridgeResponse.human_confirmation_packet.recommended_actions.length > 0 && (
                            <div className="space-y-1">
                              <div className="text-xs font-semibold text-orange-800">Recommended Actions:</div>
                              <ul className="text-xs text-orange-700 list-disc list-inside">
                                {bridgeResponse.human_confirmation_packet.recommended_actions.map((a, i) => (
                                  <li key={i}>{a}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </CardContent>
                      </Card>

                      {/* Source Status Preview */}
                      <Card>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm">Source Availability Preview</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            {[
                              { key: "ifu_available", label: "IFU" },
                              { key: "cer_available", label: "CER/CEP" },
                              { key: "rmf_available", label: "ISO 14971 RMF" },
                              { key: "risk_related_source_available", label: "Risk-Related" },
                              { key: "equivalence_available", label: "Equivalence" },
                              { key: "pmcf_available", label: "PMCF" },
                              { key: "pms_available", label: "PMS" },
                              { key: "gspr_available", label: "GSPR" },
                              { key: "sscp_available", label: "SSCP" },
                            ].map(item => {
                              const value = bridgeResponse.source_status[item.key as keyof SourceStatusOut];
                              return (
                                <div
                                  key={item.key}
                                  className={`p-2 border rounded ${
                                    value ? "border-green-300 bg-green-50" : "border-red-200 bg-red-50"
                                  }`}
                                >
                                  <span className="font-medium">{item.label}: </span>
                                  <span className={value ? "text-green-700" : "text-red-600"}>
                                    {value ? "✓ Available" : "✗ Unavailable"}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        </CardContent>
                      </Card>

                      {/* Classification Candidates Preview */}
                      {bridgeResponse.human_confirmation_packet.classification_candidates.length > 0 && (
                        <Card>
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm">
                              Classification Candidates ({bridgeResponse.human_confirmation_packet.classification_candidates.length})
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            <div className="space-y-2 max-h-64 overflow-y-auto">
                              {bridgeResponse.human_confirmation_packet.classification_candidates.map((c, i) => (
                                <div key={i} className={cn(
                                  "p-2 border rounded text-xs",
                                  c.requires_human_confirmation ? "border-yellow-200 bg-yellow-50" : "border-gray-100"
                                )}>
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="flex-1 min-w-0">
                                      <div className="font-medium truncate">{c.file_name}</div>
                                      <div className="text-muted-foreground text-[10px]">{c.document_type}</div>
                                    </div>
                                    <div className="flex flex-col items-end gap-1">
                                      <Badge variant="outline" className="text-[10px]">{c.confidence.toFixed(2)}</Badge>
                                      {c.is_true_source_candidate && (
                                        <Badge className="bg-green-100 text-green-800 text-[10px]">true source</Badge>
                                      )}
                                      {c.requires_human_confirmation && (
                                        <Badge className="bg-yellow-100 text-yellow-800 text-[10px]">needs review</Badge>
                                      )}
                                    </div>
                                  </div>
                                  {c.matched_keywords.length > 0 && (
                                    <div className="text-[10px] text-muted-foreground mt-1">
                                      Keywords: {c.matched_keywords.join(", ")}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                      )}

                      {/* source_documents Preview */}
                      {bridgeResponse.human_confirmation_packet.source_documents_preview.length > 0 && (
                        <Card>
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm">
                              source_documents Preview ({bridgeResponse.human_confirmation_packet.source_documents_preview.length})
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            <div className="space-y-2 max-h-64 overflow-y-auto">
                              {bridgeResponse.human_confirmation_packet.source_documents_preview.map((d, i) => (
                                <div key={i} className="p-2 border border-gray-100 rounded text-xs">
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="flex-1 min-w-0">
                                      <div className="font-medium truncate">{d.file_name}</div>
                                      <div className="text-muted-foreground text-[10px]">
                                        {d.document_type} — {d.version_status}
                                      </div>
                                    </div>
                                    <div className="flex flex-col items-end gap-1">
                                      <Badge variant="outline" className="text-[10px]">{d.availability}</Badge>
                                      {d.is_true_source && (
                                        <Badge className="bg-green-100 text-green-800 text-[10px]">true source</Badge>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                      )}

                      {/* Non-Claims Reminder */}
                      <Card className="border-red-200 bg-red-50/50">
                        <CardContent className="pt-4">
                          <div className="flex items-start gap-3 text-xs text-red-700">
                            <span className="text-lg">⚠️</span>
                            <div>
                              <div className="font-semibold">Boundary Constraints — Always Active</div>
                              <ul className="list-disc list-inside mt-1 space-y-0.5">
                                <li>Official CEAR has NOT been generated</li>
                                <li>No final clinical/regulatory decision has been made</li>
                                <li>No production-ready claim is made</li>
                                <li>No approved/active/reusable asset has been created</li>
                              </ul>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Input Form */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Project Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label htmlFor="project_id">Project ID *</Label>
                  <Input
                    id="project_id"
                    value={projectId}
                    onChange={e => setProjectId(e.target.value)}
                    placeholder="e.g. seed_project_07"
                    className="font-mono text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="project_name">Project Name *</Label>
                  <Input
                    id="project_name"
                    value={projectName}
                    onChange={e => setProjectName(e.target.value)}
                    placeholder="e.g. CER Review Phase C"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="source_package_ref">Source Package Ref</Label>
                  <Input
                    id="source_package_ref"
                    value={sourcePackageRef}
                    onChange={e => setSourcePackageRef(e.target.value)}
                    placeholder="Optional path to source boundary doc"
                    className="text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="known_limitations_ref">Known Limitations Ref</Label>
                  <Input
                    id="known_limitations_ref"
                    value={knownLimitationsRef}
                    onChange={e => setKnownLimitationsRef(e.target.value)}
                    placeholder="Optional path to limitations register"
                    className="text-xs"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Source Status */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Source Availability</CardTitle>
              <CardDescription>
                Set source availability flags. These determine the workflow mode and generate the source inventory.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <SourceToggle label="IFU" checked={ifuAvailable} onChange={setIfuAvailable} description="Instructions for Use" />
                <SourceToggle label="CER/CEP" checked={cerAvailable} onChange={setCerAvailable} description="Clinical Evaluation Report" />
                <SourceToggle label="ISO 14971 RMF" checked={rmfAvailable} onChange={setRmfAvailable} description="Risk Management File" />
                <SourceToggle label="Risk-Related" checked={riskRelatedAvailable} onChange={setRiskRelatedAvailable} description="Risk supplementary source" />
                <SourceToggle label="Equivalence" checked={equivalenceAvailable} onChange={setEquivalenceAvailable} description="Equivalence comparison table" />
                <SourceToggle label="PMCF" checked={pmcfAvailable} onChange={setPmcfAvailable} description="Post-Market Clinical Follow-up plan" />
                <SourceToggle label="PMS" checked={pmsAvailable} onChange={setPmsAvailable} description="Post-Market Surveillance data" />
                <SourceToggle label="GSPR" checked={gsprAvailable} onChange={setGsprAvailable} description="GSPR checklist" />
                <SourceToggle label="SSCP" checked={sscpAvailable} onChange={setSscpAvailable} description="Summary of Safety and Clinical Performance" />
              </div>
            </CardContent>
          </Card>

          {/* Boundary Flags (fixed) */}
          <Card className="border-orange-200 bg-orange-50/30">
            <CardHeader>
              <CardTitle className="text-base text-orange-800">Boundary Flags — Fixed Constraints</CardTitle>
              <CardDescription className="text-orange-700">
                These flags are locked. The backend will reject any request that attempts to set these to true.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-3">
                <div className="flex items-center gap-2 p-2 border border-orange-200 rounded bg-white/50">
                  <span className="text-red-600 text-sm">🔒</span>
                  <div>
                    <div className="text-xs font-semibold text-orange-800">official_cear_allowed</div>
                    <div className="text-xs text-red-600 font-mono">false</div>
                  </div>
                </div>
                <div className="flex items-center gap-2 p-2 border border-orange-200 rounded bg-white/50">
                  <span className="text-red-600 text-sm">🔒</span>
                  <div>
                    <div className="text-xs font-semibold text-orange-800">final_regulatory_decision_allowed</div>
                    <div className="text-xs text-red-600 font-mono">false</div>
                  </div>
                </div>
                <div className="flex items-center gap-2 p-2 border border-orange-200 rounded bg-white/50">
                  <span className="text-red-600 text-sm">🔒</span>
                  <div>
                    <div className="text-xs font-semibold text-orange-800">production_claim_allowed</div>
                    <div className="text-xs text-red-600 font-mono">false</div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Review Scope */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Review Scope</CardTitle>
              <CardDescription>Select which review components to execute</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: "source_inventory", label: "Source Inventory" },
                  { id: "ifu_cer_linkage", label: "IFU-CER Linkage" },
                  { id: "rmf_gap_impact", label: "RMF Gap Impact" },
                  { id: "equivalence_workbench", label: "Equivalence Workbench" },
                  { id: "pmcf_linkage_workbench", label: "PMCF Linkage Workbench" },
                  { id: "reviewer_packet", label: "Reviewer Packet" },
                ].map(item => (
                  <label
                    key={item.id}
                    className={cn(
                      "flex items-center gap-2 p-2 border rounded cursor-pointer transition-colors text-xs",
                      reviewScope.includes(item.id)
                        ? "border-primary bg-primary/5"
                        : "border-gray-200 hover:bg-gray-50"
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={reviewScope.includes(item.id)}
                      onChange={() => toggleScope(item.id)}
                      className="rounded"
                    />
                    {item.label}
                  </label>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Run Button */}
          <div className="flex justify-end gap-3">
            <Button
              onClick={handleRun}
              disabled={loading}
              size="lg"
            >
              {loading ? "Running..." : "▶ Run Available Source Workflow"}
            </Button>
          </div>

          {/* Error */}
          {error && (
            <Card className="border-red-300 bg-red-50">
              <CardContent className="pt-4">
                <div className="text-sm text-red-700">
                  <span className="font-semibold">Error:</span> {error}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Results */}
          {response && (
            <div className="space-y-6">
              {/* Workflow Status Header */}
              <Card className="border-primary/30 bg-primary/5">
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Badge className="bg-blue-100 text-blue-800 text-sm">{response.status}</Badge>
                      <Badge className="bg-purple-100 text-purple-800 text-sm font-mono">{response.workflow_mode}</Badge>
                      <span className="text-xs text-muted-foreground font-mono">{response.workflow_run_id}</span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Generated: {new Date(response.generated_at).toLocaleString()}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Missing IFU Warning */}
              {isMissingIFU && (
                <Card className="border-red-300 bg-red-50">
                  <CardContent className="pt-4">
                    <div className="flex items-start gap-3">
                      <span className="text-2xl">🚫</span>
                      <div className="space-y-1">
                        <p className="font-semibold text-red-800">Missing IFU — CER_ONLY_LIMITED_WITH_IFU_GAP Mode</p>
                        <ul className="space-y-0.5 text-sm text-red-700 list-disc list-inside">
                          <li>CER_ONLY_LIMITED_WITH_IFU_GAP workflow mode assigned</li>
                          <li>KSL-016 (IFU missing limitation) is in blocking_limitations</li>
                          <li>IFU-CER intended purpose linkage has NOT been executed</li>
                          <li>IFU-CER linkage review is BLOCKED</li>
                        </ul>
                        <p className="text-xs text-red-600 mt-2 font-semibold">
                          The following claims are NOT valid for this workflow:
                        </p>
                        <ul className="space-y-0.5 text-xs text-red-600 list-disc list-inside">
                          <li>IFU-CER intended purpose linkage confirmed</li>
                          <li>IFU reviewed and verified</li>
                          <li>Risk linkage confirmed based on IFU</li>
                        </ul>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Missing RMF Warning */}
              {isMissingRMF && !isMissingIFU && (
                <Card className="border-orange-300 bg-orange-50">
                  <CardContent className="pt-4">
                    <div className="flex items-start gap-3">
                      <span className="text-2xl">⚠️</span>
                      <div className="space-y-1">
                        <p className="font-semibold text-orange-800">Limited Workflow with RMF Gap</p>
                        <ul className="space-y-0.5 text-sm text-orange-700 list-disc list-inside">
                          <li>ISO 14971 RMF not available — full review blocked</li>
                          <li>Official CEAR generation blocked</li>
                          <li>RMF-source limitations (KSL-001 through KSL-007) apply</li>
                        </ul>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Downgrade Decision */}
              {response.downgrade_decision && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Downgrade Decision</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <span className="text-muted-foreground">Original Mode:</span>
                        <div className="font-mono text-xs">{response.downgrade_decision.original_mode}</div>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Assigned Mode:</span>
                        <div className="font-mono text-xs font-bold text-primary">{response.downgrade_decision.assigned_mode}</div>
                      </div>
                    </div>
                    <div className="text-sm">
                      <span className="text-muted-foreground">Reason:</span>
                      <div>{response.downgrade_decision.downgrade_reason}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground text-sm">Blocking Limitations:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {response.downgrade_decision.blocking_limitations.map(l => (
                          <Badge key={l} variant="outline" className="text-xs font-mono">{l}</Badge>
                        ))}
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div className={response.downgrade_decision.can_claim_full_review ? "text-red-600" : "text-gray-400"}>
                        Full Review: {response.downgrade_decision.can_claim_full_review ? "✓ YES" : "✗ NO"}
                      </div>
                      <div className={response.downgrade_decision.can_claim_limited_review ? "text-green-600" : "text-gray-400"}>
                        Limited Review: {response.downgrade_decision.can_claim_limited_review ? "✓ YES" : "✗ NO"}
                      </div>
                      <div className={response.downgrade_decision.can_claim_available_source_review ? "text-green-600" : "text-gray-400"}>
                        Available-Source Review: {response.downgrade_decision.can_claim_available_source_review ? "✓ YES" : "✗ NO"}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Results Tabs */}
              <Tabs defaultValue="inventory">
                <TabsList>
                  <TabsTrigger value="inventory">Source Inventory</TabsTrigger>
                  <TabsTrigger value="limitations">Limitations Register</TabsTrigger>
                  <TabsTrigger value="equivalence">Equivalence Workbench</TabsTrigger>
                  <TabsTrigger value="pmcf">PMCF Workbench</TabsTrigger>
                  <TabsTrigger value="findings">Findings</TabsTrigger>
                  <TabsTrigger value="non-claims">Non-Claims</TabsTrigger>
                  <TabsTrigger value="raw">Raw JSON</TabsTrigger>
                </TabsList>

                {/* Source Inventory */}
                <TabsContent value="inventory">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Source Inventory ({response.source_inventory.length} items)</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {response.source_inventory.map(item => (
                          <div key={item.source_id} className="flex items-start gap-3 p-2 border rounded text-xs">
                            <SourceStatusBadge status={item.status} />
                            <div className="flex-1">
                              <div className="font-mono font-semibold">{item.source_id}</div>
                              <div className="text-muted-foreground">{item.source_name}</div>
                              {item.source_path && (
                                <div className="text-muted-foreground text-[10px] mt-0.5">Path: {item.source_path}</div>
                              )}
                              {item.availability_note && (
                                <div className="text-orange-600 text-[10px] mt-0.5">{item.availability_note}</div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>

                {/* Source Limitations */}
                <TabsContent value="limitations">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Source Limitation Register ({response.source_limitation_register.length} items)</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {response.source_limitation_register.map(item => (
                          <div key={item.limitation_id} className="p-3 border rounded text-xs space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-bold text-primary">{item.limitation_id}</span>
                              <div className="flex gap-1">
                                <Badge variant="outline" className="text-[10px]">{item.category}</Badge>
                                {item.blocks_full_review && <Badge variant="destructive" className="text-[10px]">blocks full</Badge>}
                                {item.blocks_limited_workflow && <Badge variant="destructive" className="text-[10px]">blocks limited</Badge>}
                              </div>
                            </div>
                            <div className="text-muted-foreground">Gap: {item.source_gap}</div>
                            <div className="text-muted-foreground">Impact: {item.impact}</div>
                            <div className="text-orange-600">Prohibited claim: {item.prohibited_claim}</div>
                            <div className="flex flex-wrap gap-1 mt-1">
                              <span className="text-muted-foreground text-[10px]">Allowed:</span>
                              {item.allowed_workflow.map(w => (
                                <Badge key={w} variant="outline" className="text-[10px] font-mono">{w}</Badge>
                              ))}
                            </div>
                            {item.human_caution && (
                              <div className="text-yellow-600 text-[10px] mt-1">⚠️ {item.human_caution}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>

                {/* Equivalence Workbench */}
                <TabsContent value="equivalence">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Equivalence Workbench</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {!response.equivalence_workbench || response.equivalence_workbench.length === 0 ? (
                        <p className="text-sm text-muted-foreground">Equivalence workbench not generated (not in review scope)</p>
                      ) : (
                        <div className="space-y-3">
                          {response.equivalence_workbench.map(item => (
                            <div key={item.item_id} className="p-3 border rounded text-xs space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-mono font-bold text-primary">{item.item_id}</span>
                                <Badge variant="outline" className="text-[10px]">{item.dimension}</Badge>
                              </div>
                              <div className="font-medium">{item.aspect}</div>
                              {item.baxter_evidence && (
                                <div className="text-muted-foreground">Baxter: {item.baxter_evidence}</div>
                              )}
                              {item.nipro_evidence && (
                                <div className="text-muted-foreground">Nipro: {item.nipro_evidence}</div>
                              )}
                              {item.gap_description && (
                                <div className="text-orange-600">Gap: {item.gap_description}</div>
                              )}
                              {item.reviewer_question && (
                                <div className="text-blue-600 mt-1">❓ {item.reviewer_question}</div>
                              )}
                              {item.limitation_ref && (
                                <div className="text-muted-foreground text-[10px]">Limitation ref: {item.limitation_ref}</div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                {/* PMCF Workbench */}
                <TabsContent value="pmcf">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">PMCF Linkage Workbench</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {!response.pmcf_linkage_workbench || response.pmcf_linkage_workbench.length === 0 ? (
                        <p className="text-sm text-muted-foreground">PMCF workbench not generated (not in review scope)</p>
                      ) : (
                        <div className="space-y-3">
                          {response.pmcf_linkage_workbench.map(item => (
                            <div key={item.item_id} className="p-3 border rounded text-xs space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-mono font-bold text-primary">{item.item_id}</span>
                                <div className="flex items-center gap-2">
                                  <Badge variant="outline" className="text-[10px]">{item.dimension}</Badge>
                                  <LinkageStatusBadge status={item.linkage_status} />
                                </div>
                              </div>
                              {item.cer_claim && <div className="text-muted-foreground">CER claim: {item.cer_claim}</div>}
                              {item.pmcf_plan_claim && <div className="text-muted-foreground">PMCF claim: {item.pmcf_plan_claim}</div>}
                              {item.gap_description && <div className="text-orange-600">Gap: {item.gap_description}</div>}
                              {item.reviewer_question && <div className="text-blue-600">❓ {item.reviewer_question}</div>}
                              {item.limitation_ref && <div className="text-muted-foreground text-[10px]">Limitation ref: {item.limitation_ref}</div>}
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                {/* Findings */}
                <TabsContent value="findings">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Reviewer Findings ({response.reviewer_findings.length} items)</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {response.reviewer_findings.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No findings generated</p>
                      ) : (
                        <div className="space-y-3">
                          {response.reviewer_findings.map(item => (
                            <div key={item.finding_id} className="p-3 border rounded text-xs space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-mono font-bold text-primary">{item.finding_id}</span>
                                <div className="flex gap-1">
                                  <SeverityBadge severity={item.severity} />
                                  {item.actionable && <Badge variant="outline" className="text-[10px]">actionable</Badge>}
                                  {item.human_decision_required && <Badge variant="destructive" className="text-[10px]">human review</Badge>}
                                </div>
                              </div>
                              <div className="font-medium">{item.title}</div>
                              <div className="text-muted-foreground">{item.description}</div>
                              {item.source_limitation_ref && (
                                <div className="text-muted-foreground text-[10px]">Limitation refs: {item.source_limitation_ref}</div>
                              )}
                              {item.action && (
                                <div className="text-blue-600 text-[10px]">Action: {item.action}</div>
                              )}
                              {item.preliminary_judgment && (
                                <div className="text-yellow-600 text-[10px]">Preliminary: {item.preliminary_judgment}</div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                {/* Non-Claims */}
                <TabsContent value="non-claims">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Non-Claims ({response.non_claims.length} items)</CardTitle>
                      <CardDescription>
                        These claims are explicitly NOT made by this workflow.
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {response.non_claims.map((item, i) => (
                          <div key={i} className="p-3 border border-red-200 rounded text-xs bg-red-50/50 space-y-1">
                            <div className="flex items-start gap-2">
                              <span className="text-red-500 mt-0.5">✗</span>
                              <div>
                                <div className="font-semibold text-red-800">{item.non_claim}</div>
                                <div className="text-muted-foreground mt-0.5">Reason: {item.reason}</div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>

                {/* Raw JSON */}
                <TabsContent value="raw">
                  <Card>
                    <CardContent className="pt-4">
                      <pre className="text-xs bg-muted p-4 rounded overflow-auto max-h-96">
                        {JSON.stringify(response, null, 2)}
                      </pre>
                    </CardContent>
                  </Card>
                </TabsContent>
              </Tabs>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SourceToggle({
  label,
  checked,
  onChange,
  description,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  description: string;
}) {
  return (
    <label className={cn(
      "flex items-center gap-2 p-2 border rounded cursor-pointer transition-colors",
      checked ? "border-green-300 bg-green-50" : "border-gray-200 bg-white hover:bg-gray-50"
    )}>
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        className="rounded"
      />
      <div className="flex-1 min-w-0">
        <div className={cn("text-xs font-medium", checked ? "text-green-800" : "text-gray-700")}>{label}</div>
        <div className="text-[10px] text-muted-foreground truncate">{description}</div>
      </div>
    </label>
  );
}
