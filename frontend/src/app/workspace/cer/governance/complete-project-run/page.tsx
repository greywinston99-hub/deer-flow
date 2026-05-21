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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { cerReviewFetch } from "@/core/cer_auth/api";
import { getBackendBaseURL } from "@/core/config";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types (reused from available-source)
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
// Run Mode Types
// ---------------------------------------------------------------------------

type RunMode = "COMPLETE_PROJECT_CONTROLLED_REVIEW" | "AVAILABLE_SOURCE_LIMITED" | "INVENTORY_ONLY_HOLD";

// ---------------------------------------------------------------------------
// Entry Gate Definitions (C1-C15)
// ---------------------------------------------------------------------------

const ENTRY_GATES = [
  { id: "c1", label: "C1: Source Package Folder Exists", description: "Verify the source package folder exists at the specified path" },
  { id: "c2", label: "C2: IFU Present", description: "Instructions for Use document is available" },
  { id: "c3", label: "C3: CER/CEP Present", description: "Clinical Evaluation Report or CEP is available" },
  { id: "c4", label: "C4: RMF Package Present", description: "ISO 14971 Risk Management File is available" },
  { id: "c5", label: "C5: PMS/PMCF Present or Justified Unavailable", description: "Post-market surveillance data or justification is documented" },
  { id: "c6", label: "C6: GSPR Present", description: "General Safety and Performance Requirements checklist is available" },
  { id: "c7", label: "C7: SSCP Present or Applicability Resolved", description: "Summary of Safety and Clinical Performance is available or applicability is formally resolved" },
  { id: "c8", label: "C8: Equivalence Evidence Present or Not Used", description: "Equivalence comparison table is available, or equivalence route is not claimed" },
  { id: "c9", label: "C9: Literature/SOTA Present", description: "State of the art literature review is available" },
  { id: "c10", label: "C10: Human Reviewer Assigned", description: "A qualified human reviewer has been assigned to this review" },
  { id: "c11", label: "C11: Non-claims Boundary Acknowledged", description: "Team acknowledges the non-claims boundary constraints" },
  { id: "c12", label: "C12: Backflow Disabled Unless Explicitly Approved", description: "Automatic backflow is disabled unless explicitly approved" },
  { id: "c13", label: "C13: Run Mode Selected", description: "A run mode has been selected" },
  { id: "c14", label: "C14: Output Folder Prepared", description: "Output folder for review artifacts has been prepared" },
  { id: "c15", label: "C15: QA Observer Assigned If Possible", description: "A QA observer has been assigned where possible" },
] as const;

// ---------------------------------------------------------------------------
// Document Type Options for Human Confirmation
// ---------------------------------------------------------------------------

const DOCUMENT_TYPES = [
  "IFU", "CER", "CEP", "RMF", "RISK_ANALYSIS",
  "PMCF", "PMS", "GSPR", "SSCP", "EQUIVALENCE", "LITERATURE/SOTA",
] as const;


// ---------------------------------------------------------------------------
// Human Decision Types (UI_STAGED_DECISION_ONLY)
// ---------------------------------------------------------------------------

interface HumanDecisionState {
  finding_ids: string[];
  decision: "approve" | "reject" | "park" | "request_rework" | null;
  severity_confirmed: boolean;
  rationale: string;
  required_followup: string;
  allow_obsidian_backflow: boolean;
  allow_nocodb_machine_asset: boolean;
  allow_future_reuse: boolean;
  signed_at: string | null;
}

// ---------------------------------------------------------------------------
// Source Confirmation State (UI_LOCAL_CONFIRMATION_ONLY)
// ---------------------------------------------------------------------------

interface ConfirmState {
  confirmedType: string | null;
  excluded: boolean;
  unknown: boolean;
  needsOpenFileCheck: boolean;
}

// ---------------------------------------------------------------------------
// API Functions (copied from available-source)
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
// Badge Helpers
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
// Source Toggle Component
// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CompleteProjectRunPage() {
  // Project fields
  const [projectId, setProjectId] = useState("");
  const [projectName, setProjectName] = useState("");
  const [sourcePackagePath, setSourcePackagePath] = useState("");
  const [runMode, setRunMode] = useState<RunMode>("AVAILABLE_SOURCE_LIMITED");

  // C1-C15 Gate state
  const [gates, setGates] = useState<Record<string, boolean>>({});

  // Bridge/scan state
  const [bridgeResponse, setBridgeResponse] = useState<SourcePackagePrepareResponse | null>(null);
  const [bridgeError, setBridgeError] = useState<string | null>(null);
  const [bridgeLoading, setBridgeLoading] = useState(false);

  // Workflow state
  const [response, setResponse] = useState<AvailableSourceWorkflowResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Human source confirmation state (UI_LOCAL_CONFIRMATION_ONLY)
  const [confirmState, setConfirmState] = useState<Record<string, ConfirmState>>({});

  // Human decision state (UI_STAGED_DECISION_ONLY)
  const [decisionState, setDecisionState] = useState<HumanDecisionState>({
    finding_ids: [],
    decision: null,
    severity_confirmed: false,
    rationale: "",
    required_followup: "",
    allow_obsidian_backflow: false,
    allow_nocodb_machine_asset: false,
    allow_future_reuse: false,
    signed_at: null,
  });

  // Gate toggle
  const toggleGate = useCallback((id: string, value: boolean) => {
    setGates(prev => ({ ...prev, [id]: value }));
  }, []);

  // Scan package
  const handleScanPackage = useCallback(async () => {
    if (!projectId.trim()) { toast.error("Project ID is required"); return; }
    if (!projectName.trim()) { toast.error("Project Name is required"); return; }
    if (!sourcePackagePath.trim()) { toast.error("Source package path is required"); return; }

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

      // Auto-check C1-C15 gates from scan results
      const ss = result.source_status;
      const newGates: Record<string, boolean> = {};
      newGates.c1 = true; // source package path exists
      newGates.c2 = ss.ifu_available;
      newGates.c3 = ss.cer_available;
      newGates.c4 = ss.rmf_available;
      newGates.c5 = ss.pmcf_available || ss.pms_available;
      newGates.c6 = ss.gspr_available;
      newGates.c7 = ss.sscp_available;
      newGates.c8 = ss.equivalence_available;
      newGates.c13 = true; // run mode selected
      setGates(prev => ({ ...prev, ...newGates }));

      // Initialize confirmation state for each candidate
      const initConfirm: Record<string, ConfirmState> = {};
      result.human_confirmation_packet.classification_candidates.forEach(c => {
        initConfirm[c.file_name] = {
          confirmedType: c.is_true_source_candidate ? c.document_type : null,
          excluded: false,
          unknown: false,
          needsOpenFileCheck: c.requires_human_confirmation,
        };
      });
      setConfirmState(initConfirm);

      toast.success(`Scan complete: ${result.scanned_files_count} files, ${result.classification_candidates_count} candidates`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setBridgeError(msg);
      toast.error(`Scan failed: ${msg}`);
    } finally {
      setBridgeLoading(false);
    }
  }, [projectId, projectName, sourcePackagePath]);

  // Run workflow from bridge response
  const handleRunFromBridge = useCallback(async () => {
    if (!bridgeResponse?.available_source_request) {
      toast.error("No available-source request generated. Please scan first.");
      return;
    }

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
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

  // Run workflow in INVENTORY_ONLY_HOLD mode
  const handleRunInventoryHold = useCallback(async () => {
    if (!projectId.trim()) { toast.error("Project ID is required"); return; }
    if (!projectName.trim()) { toast.error("Project Name is required"); return; }
    if (!sourcePackagePath.trim()) { toast.error("Source package path is required"); return; }

    setLoading(true);
    setError(null);
    setResponse(null);

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
      // For INVENTORY_ONLY_HOLD, we just show the scan results, not a full workflow
      setBridgeResponse(result);
      toast.success(`Inventory scan complete: ${result.scanned_files_count} files`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(`Scan failed: ${msg}`);
    } finally {
      setLoading(false);
    }
  }, [projectId, projectName, sourcePackagePath]);

  // Update confirmation state
  const updateConfirm = useCallback((fileName: string, field: keyof ConfirmState, value: ConfirmState[keyof ConfirmState]) => {
    setConfirmState(prev => ({
      ...prev,
      [fileName]: { ...prev[fileName], [field]: value } as ConfirmState,
    }));
  }, []);

  // Update decision state
  const updateDecision = useCallback(<K extends keyof HumanDecisionState>(field: K, value: HumanDecisionState[K]) => {
    setDecisionState(prev => ({ ...prev, [field]: value }));
  }, []);

  // Toggle finding in decision
  const toggleFinding = useCallback((findingId: string) => {
    setDecisionState(prev => ({
      ...prev,
      finding_ids: prev.finding_ids.includes(findingId)
        ? prev.finding_ids.filter(id => id !== findingId)
        : [...prev.finding_ids, findingId],
    }));
  }, []);

  // Check if all critical gates are passed
  const criticalGatesPassed = gates.c1 && gates.c2 && gates.c3 && gates.c11 && gates.c12 && gates.c13;

  // Gate pass count
  const gatesPassed = Object.values(gates).filter(Boolean).length;

  const isMissingIFU = response?.source_inventory.some(
    s => s.source_id === "ifu" && (s.status === "SOURCE_UNAVAILABLE" || s.status === "SOURCE_NOT_FOUND")
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
          <h2 className="text-sm font-semibold">Complete Project Run</h2>
          <p className="text-xs text-muted-foreground mt-1">Full controlled CER/RMF review</p>
        </div>

        {/* Navigation */}
        <div className="p-2 space-y-1 flex-1 overflow-y-auto">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">WORKFLOWS</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href="/workspace/cer/governance/run-home">Run Home</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href="/workspace/cer/governance/available-source">Available Source Workflow</Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-6xl mx-auto space-y-6">
          {/* Header */}
          <div>
            <h1 className="text-xl font-bold">Complete Project Controlled Run</h1>
            <p className="text-sm text-muted-foreground">
              Full CER/RMF controlled review — entry gate checklist, source confirmation, and human decision intake.
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
                    <li>No automatic backflow — human reviewer required</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* C1-C15 Entry Gate Panel */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Entry Gate Checklist (C1-C15)</CardTitle>
              <CardDescription>
                Verify all required conditions before running the review. Gates {gatesPassed}/15 passed.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                {ENTRY_GATES.map(gate => (
                  <label
                    key={gate.id}
                    className={cn(
                      "flex items-start gap-2 p-2 border rounded cursor-pointer transition-colors text-xs",
                      gates[gate.id]
                        ? "border-green-300 bg-green-50"
                        : "border-gray-200 bg-white hover:bg-gray-50"
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={!!gates[gate.id]}
                      onChange={e => toggleGate(gate.id, e.target.checked)}
                      className="mt-0.5 rounded"
                    />
                    <div className="flex-1 min-w-0">
                      <div className={cn(
                        "font-medium text-xs",
                        gates[gate.id] ? "text-green-800" : "text-gray-700"
                      )}>
                        {gate.label}
                      </div>
                      <div className="text-[10px] text-muted-foreground mt-0.5">{gate.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Project Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Project Configuration</CardTitle>
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
                  <Label htmlFor="source_package_path">Source Package Path *</Label>
                  <Input
                    id="source_package_path"
                    value={sourcePackagePath}
                    onChange={e => setSourcePackagePath(e.target.value)}
                    placeholder="/path/to/source/package"
                    className="text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="run_mode">Run Mode *</Label>
                  <Select value={runMode} onValueChange={(v: RunMode) => setRunMode(v)}>
                    <SelectTrigger id="run_mode" className="text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="COMPLETE_PROJECT_CONTROLLED_REVIEW">COMPLETE_PROJECT_CONTROLLED_REVIEW</SelectItem>
                      <SelectItem value="AVAILABLE_SOURCE_LIMITED">AVAILABLE_SOURCE_LIMITED</SelectItem>
                      <SelectItem value="INVENTORY_ONLY_HOLD">INVENTORY_ONLY_HOLD</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
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
                {runMode === "INVENTORY_ONLY_HOLD" ? (
                  <Button
                    onClick={handleRunInventoryHold}
                    disabled={loading || !bridgeResponse}
                    size="lg"
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    {loading ? "Running..." : "▶ Run Inventory Scan (HOLD Mode)"}
                  </Button>
                ) : (
                  <Button
                    onClick={handleRunFromBridge}
                    disabled={loading || !bridgeResponse || !criticalGatesPassed}
                    size="lg"
                    className="bg-green-600 hover:bg-green-700"
                  >
                    {loading ? "Running..." : "▶ Run Workflow"}
                  </Button>
                )}
              </div>

              {!criticalGatesPassed && (
                <div className="text-xs text-orange-600 bg-orange-50 border border-orange-200 rounded p-2">
                  ⚠️ Critical gates not passed. Please check C1, C2, C3, C11, C12, C13.
                </div>
              )}
            </CardContent>
          </Card>

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
                  <CardTitle className="text-sm">Source Availability (auto-filled from scan)</CardTitle>
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

              {/* Human Source Confirmation UI (UI_LOCAL_CONFIRMATION_ONLY) */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Human Source Confirmation (UI_LOCAL_ONLY)</CardTitle>
                  <CardDescription className="text-orange-600 text-xs">
                    ⚠️ This confirmation is held in local UI state only. No backend persistence.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {bridgeResponse.human_confirmation_packet.classification_candidates.map((c, i) => {
                      const state = confirmState[c.file_name] ?? {
                        confirmedType: null, excluded: false, unknown: false, needsOpenFileCheck: false,
                      };
                      return (
                        <div key={i} className={cn(
                          "p-3 border rounded text-xs space-y-2",
                          c.requires_human_confirmation ? "border-yellow-200 bg-yellow-50" : "border-gray-100"
                        )}>
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="font-medium truncate">{c.file_name}</div>
                              <div className="text-muted-foreground text-[10px]">
                                Auto-classified as: {c.document_type}
                              </div>
                            </div>
                            <div className="flex flex-col items-end gap-1">
                              <Badge variant="outline" className="text-[10px]">{c.confidence.toFixed(2)}</Badge>
                              {c.is_true_source_candidate && (
                                <Badge className="bg-green-100 text-green-800 text-[10px]">true source</Badge>
                              )}
                            </div>
                          </div>

                          {/* Confirmation controls */}
                          <div className="flex flex-wrap gap-2 items-center">
                            <Select
                              value={state.confirmedType ?? ""}
                              onValueChange={v => updateConfirm(c.file_name, "confirmedType", v)}
                            >
                              <SelectTrigger className="text-xs h-7 w-40">
                                <SelectValue placeholder="Confirm type..." />
                              </SelectTrigger>
                              <SelectContent>
                                {DOCUMENT_TYPES.map(dt => (
                                  <SelectItem key={dt} value={dt}>{dt}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>

                            <label className="flex items-center gap-1 text-[10px]">
                              <input
                                type="checkbox"
                                checked={state.excluded}
                                onChange={e => updateConfirm(c.file_name, "excluded", e.target.checked)}
                                className="rounded"
                              />
                              Exclude
                            </label>
                            <label className="flex items-center gap-1 text-[10px]">
                              <input
                                type="checkbox"
                                checked={state.unknown}
                                onChange={e => updateConfirm(c.file_name, "unknown", e.target.checked)}
                                className="rounded"
                              />
                              Unknown
                            </label>
                            <label className="flex items-center gap-1 text-[10px]">
                              <input
                                type="checkbox"
                                checked={state.needsOpenFileCheck}
                                onChange={e => updateConfirm(c.file_name, "needsOpenFileCheck", e.target.checked)}
                                className="rounded"
                              />
                              Needs Open-File Check
                            </label>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

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

          {/* Workflow Results */}
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
                        <p className="text-sm text-muted-foreground">Not generated or not in scope</p>
                      ) : (
                        <div className="space-y-3">
                          {response.equivalence_workbench.map(item => (
                            <div key={item.item_id} className="p-3 border rounded text-xs space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-mono font-bold text-primary">{item.item_id}</span>
                                <Badge variant="outline" className="text-[10px]">{item.dimension}</Badge>
                              </div>
                              <div className="font-medium">{item.aspect}</div>
                              {item.baxter_evidence && <div className="text-muted-foreground">Baxter: {item.baxter_evidence}</div>}
                              {item.nipro_evidence && <div className="text-muted-foreground">Nipro: {item.nipro_evidence}</div>}
                              {item.gap_description && <div className="text-orange-600">Gap: {item.gap_description}</div>}
                              {item.reviewer_question && <div className="text-blue-600 mt-1">❓ {item.reviewer_question}</div>}
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
                        <p className="text-sm text-muted-foreground">Not generated or not in scope</p>
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
                              {item.action && <div className="text-blue-600 text-[10px]">Action: {item.action}</div>}
                              {item.preliminary_judgment && <div className="text-yellow-600 text-[10px]">Preliminary: {item.preliminary_judgment}</div>}
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
                      <CardDescription>These claims are explicitly NOT made by this workflow.</CardDescription>
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

              {/* Human Decision UI (UI_STAGED_DECISION_ONLY) */}
              {response.reviewer_findings.length > 0 && (
                <Card className="border-purple-200 bg-purple-50/30">
                  <CardHeader>
                    <CardTitle className="text-base text-purple-800">Human Decision Intake (UI_STAGED_ONLY)</CardTitle>
                    <CardDescription className="text-purple-600 text-xs">
                      ⚠️ No backend persistence. This is a staged placeholder. No backflow will be executed.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <div className="text-xs font-semibold mb-2">Findings to Address:</div>
                      <div className="flex flex-wrap gap-2">
                        {response.reviewer_findings.map(f => (
                          <label
                            key={f.finding_id}
                            className={cn(
                              "flex items-center gap-1 p-2 border rounded cursor-pointer text-xs",
                              decisionState.finding_ids.includes(f.finding_id)
                                ? "border-purple-300 bg-purple-100"
                                : "border-gray-200 bg-white hover:bg-gray-50"
                            )}
                          >
                            <input
                              type="checkbox"
                              checked={decisionState.finding_ids.includes(f.finding_id)}
                              onChange={() => toggleFinding(f.finding_id)}
                              className="rounded"
                            />
                            <span className="font-mono">{f.finding_id}</span>
                            <SeverityBadge severity={f.severity} />
                          </label>
                        ))}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1">
                        <Label htmlFor="decision">Decision *</Label>
                        <Select
                          value={decisionState.decision ?? ""}
                          onValueChange={v => updateDecision("decision", v as HumanDecisionState["decision"])}
                        >
                          <SelectTrigger id="decision">
                            <SelectValue placeholder="Select decision..." />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="approve">Approve</SelectItem>
                            <SelectItem value="reject">Reject</SelectItem>
                            <SelectItem value="park">Park</SelectItem>
                            <SelectItem value="request_rework">Request Rework</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="severity_confirmed">Severity Confirmed</Label>
                        <div className="flex items-center gap-2 h-10">
                          <input
                            type="checkbox"
                            checked={decisionState.severity_confirmed}
                            onChange={e => updateDecision("severity_confirmed", e.target.checked)}
                            className="rounded"
                          />
                          <span className="text-xs text-muted-foreground">
                            {decisionState.severity_confirmed ? "Severity confirmed by reviewer" : "Severity not yet confirmed"}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-1">
                      <Label htmlFor="rationale">Rationale *</Label>
                      <Textarea
                        id="rationale"
                        value={decisionState.rationale}
                        onChange={e => updateDecision("rationale", e.target.value)}
                        placeholder="Enter decision rationale..."
                        className="text-xs"
                        rows={3}
                      />
                    </div>

                    <div className="space-y-1">
                      <Label htmlFor="required_followup">Required Follow-up</Label>
                      <Textarea
                        id="required_followup"
                        value={decisionState.required_followup}
                        onChange={e => updateDecision("required_followup", e.target.value)}
                        placeholder="Enter required follow-up actions..."
                        className="text-xs"
                        rows={2}
                      />
                    </div>

                    <div className="space-y-2">
                      <div className="text-xs font-semibold">Backflow & Asset Flags (all default to false):</div>
                      <div className="flex flex-col gap-2">
                        <label className="flex items-center gap-2 text-xs">
                          <input
                            type="checkbox"
                            checked={decisionState.allow_obsidian_backflow}
                            onChange={e => updateDecision("allow_obsidian_backflow", e.target.checked)}
                            className="rounded"
                            disabled
                          />
                          <span>allow_obsidian_backflow (default: false)</span>
                          <span className="text-red-500 text-[10px]">🔒 Always false — no automatic backflow</span>
                        </label>
                        <label className="flex items-center gap-2 text-xs">
                          <input
                            type="checkbox"
                            checked={decisionState.allow_nocodb_machine_asset}
                            onChange={e => updateDecision("allow_nocodb_machine_asset", e.target.checked)}
                            className="rounded"
                            disabled
                          />
                          <span>allow_nocodb_machine_asset (default: false)</span>
                          <span className="text-red-500 text-[10px]">🔒 Always false — no machine asset creation</span>
                        </label>
                        <label className="flex items-center gap-2 text-xs">
                          <input
                            type="checkbox"
                            checked={decisionState.allow_future_reuse}
                            onChange={e => updateDecision("allow_future_reuse", e.target.checked)}
                            className="rounded"
                            disabled
                          />
                          <span>allow_future_reuse (default: false)</span>
                          <span className="text-red-500 text-[10px]">🔒 Always false — no reuse allowed</span>
                        </label>
                      </div>
                    </div>

                    <div className="flex gap-3 items-center">
                      <Button
                        disabled
                        className="bg-purple-600 hover:bg-purple-700"
                      >
                        Sign & Submit (UI_STAGED_ONLY — no backend)
                      </Button>
                      <span className="text-xs text-muted-foreground">
                        Signed at: {decisionState.signed_at ?? "Not signed"}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
