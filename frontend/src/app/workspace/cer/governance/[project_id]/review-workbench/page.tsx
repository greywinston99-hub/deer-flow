"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { ConfidenceHeatmap } from "@/components/cer/confidence-heatmap";
import { GapPointPanel } from "@/components/cer/gap-point-panel";
import { ReviewCopilotDrawer } from "@/components/cer/review-copilot-drawer";
import { ReviewFeedbackPanel } from "@/components/cer/review-feedback-panel";
import type { FeedbackAction } from "@/components/cer/review-feedback-panel";
import { ReviewFlavorSelector } from "@/components/cer/review-flavor-selector";
import { SourceSlotWorkbench } from "@/components/cer/source-slot-workbench";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  analyzeGaps,
  draftBatchOperation,
  draftCopilotSuggestions,
  getLatestWorkbench,
  runShadowBacktest,
} from "@/core/cer_auth/v5_api";
import type {
  ConfidenceHeatmapItem,
  CopilotSuggestion,
  GPointItem,
  ReviewFeedbackPayload,
} from "@/core/cer_auth/v5_types";
import { useSourceSlotWorkbench } from "@/hooks/use_source_slot_workbench";

const LOCAL_BRIDGE_KEY = "cer_complete_project_bridge";

interface BridgeCandidate {
  file_id: string;
  file_name: string;
  relative_path?: string;
  auto_classified_type?: string;
  ranking_score?: number;
  readability_status?: string;
  size_bytes?: number;
  file_hash_sha256?: string | null;
  negative_signals?: string[];
}

interface SourceFamilyGroup {
  group_id: string;
  source_type: string;
  confidence: number;
  group_status: string;
  recommended_canonical_file_id: string | null;
  recommended_canonical_reason: string;
  candidates: BridgeCandidate[];
  alternatives: BridgeCandidate[];
  companion_files: BridgeCandidate[];
  duplicate_files: BridgeCandidate[];
  open_file_required: BridgeCandidate[];
  missing_reason: string | null;
}

interface BridgePayload {
  project_id: string;
  project_name: string;
  source_package_path: string;
  human_confirmation_packet?: {
    source_family_groups?: SourceFamilyGroup[];
    unscanned_file_register?: Record<string, unknown>;
  };
}

function loadBridgePayload(): BridgePayload | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(LOCAL_BRIDGE_KEY);
    return raw ? (JSON.parse(raw) as BridgePayload) : null;
  } catch {
    return null;
  }
}

function buildFallbackFamilyGroups(): SourceFamilyGroup[] {
  // MOCK_ONLY: strictly gated behind dev flag; never used in production.
  if (process.env.NODE_ENV !== "development" || !process.env.NEXT_PUBLIC_ENABLE_MOCK_FALLBACK) {
    return [];
  }
  return [
    {
      group_id: "SF-IFU",
      source_type: "ifu",
      confidence: 0.95,
      group_status: "RECOMMENDED_READY_FOR_CONFIRMATION",
      recommended_canonical_file_id: "f-001",
      recommended_canonical_reason: "IFU release copy selected from canonical source family.",
      candidates: [
        {
          file_id: "f-001",
          file_name: "IFU_HeartPump_v2.1.pdf",
          relative_path: "/docs/IFU_HeartPump_v2.1.pdf",
          auto_classified_type: "ifu",
          ranking_score: 0.95,
          readability_status: "PASS",
          size_bytes: 125000,
          file_hash_sha256: "demo-hash-001",
        },
      ],
      alternatives: [],
      companion_files: [],
      duplicate_files: [],
      open_file_required: [],
      missing_reason: null,
    },
    {
      group_id: "SF-CER",
      source_type: "cer",
      confidence: 0.84,
      group_status: "MULTIPLE_CANDIDATES_NEED_REVIEW",
      recommended_canonical_file_id: "f-002",
      recommended_canonical_reason: "CER candidate selected, but alternatives remain available for reviewer comparison.",
      candidates: [
        {
          file_id: "f-002",
          file_name: "CER_HeartPump_2024.pdf",
          relative_path: "/docs/CER_HeartPump_2024.pdf",
          auto_classified_type: "cer",
          ranking_score: 0.84,
          readability_status: "PASS",
          size_bytes: 300000,
        },
      ],
      alternatives: [
        {
          file_id: "f-012",
          file_name: "CER_HeartPump_2023.pdf",
          relative_path: "/docs/archive/CER_HeartPump_2023.pdf",
          auto_classified_type: "cer",
          ranking_score: 0.61,
          readability_status: "PASS",
          size_bytes: 280000,
        },
      ],
      companion_files: [],
      duplicate_files: [],
      open_file_required: [],
      missing_reason: null,
    },
    {
      group_id: "SF-RMF",
      source_type: "rmf",
      confidence: 0.72,
      group_status: "READABILITY_INSUFFICIENT",
      recommended_canonical_file_id: "f-003",
      recommended_canonical_reason: "RMF spreadsheet detected, but readability still needs open-file verification.",
      candidates: [
        {
          file_id: "f-003",
          file_name: "RMF_ISO14971_2024.xlsx",
          relative_path: "/docs/RMF_ISO14971_2024.xlsx",
          auto_classified_type: "rmf",
          ranking_score: 0.72,
          readability_status: "NEEDS_OPEN_FILE_CHECK",
          size_bytes: 160000000,
          negative_signals: ["large spreadsheet"],
        },
      ],
      alternatives: [],
      companion_files: [],
      duplicate_files: [],
      open_file_required: [
        {
          file_id: "f-003",
          file_name: "RMF_ISO14971_2024.xlsx",
          relative_path: "/docs/RMF_ISO14971_2024.xlsx",
          auto_classified_type: "rmf",
          ranking_score: 0.72,
          readability_status: "NEEDS_OPEN_FILE_CHECK",
          size_bytes: 160000000,
        },
      ],
      missing_reason: null,
    },
    {
      group_id: "SF-EQUIVALENCE",
      source_type: "equivalence",
      confidence: 0.58,
      group_status: "LOW_CONFIDENCE_NEED_OPEN_FILE_CHECK",
      recommended_canonical_file_id: "f-007",
      recommended_canonical_reason: "Equivalence matrix found but still needs reviewer scrutiny.",
      candidates: [
        {
          file_id: "f-007",
          file_name: "Equivalence_Matrix.xlsx",
          relative_path: "/docs/Equivalence_Matrix.xlsx",
          auto_classified_type: "equivalence",
          ranking_score: 0.58,
          readability_status: "PASS",
          size_bytes: 150000,
        },
      ],
      alternatives: [],
      companion_files: [],
      duplicate_files: [],
      open_file_required: [],
      missing_reason: null,
    },
  ];
}

function makeBatchSuggestions(
  title: string,
  draftId: string,
  stagedActions: { action_id: string; action_type: string }[]
): CopilotSuggestion[] {
  return stagedActions.map((action, index) => ({
    suggestion_id: `${draftId}-${index}`,
    suggestion_type: title,
    text: `Drafted action: ${action.action_type.replace(/_/g, " ")}.`,
    evidence_refs: [],
    staged_action: {
      action_id: action.action_id,
      action_type: action.action_type,
    },
    requires_human_confirmation: true,
  }));
}

export default function ReviewWorkbenchPage() {
  const params = useParams();
  const projectId = params.project_id as string;
  if (!projectId) {
    return (
      <div className="container mx-auto py-6">
        <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
          Error: Project ID is required.
        </div>
      </div>
    );
  }

  const {
    slots,
    workbenchId,
    loading,
    error,
    build,
    refresh,
    confirm,
    reselect,
    markMissing,
    markOpenFile,
  } = useSourceSlotWorkbench();

  const [flavor, setFlavor] = useState("BALANCED");
  const [bridgePayload, setBridgePayload] = useState<BridgePayload | null>(null);
  const [sourceFamilyGroups, setSourceFamilyGroups] = useState<SourceFamilyGroup[]>([]);
  const [gPoints, setGPoints] = useState<GPointItem[]>([]);
  const [copilotSuggestions, setCopilotSuggestions] = useState<CopilotSuggestion[]>([]);
  const [heatmap, setHeatmap] = useState<ConfidenceHeatmapItem[]>([]);
  const [gapLoading, setGapLoading] = useState(false);
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [shadowReport, setShadowReport] = useState<Record<string, unknown> | null>(null);
  const [shadowLoading, setShadowLoading] = useState(false);
  const [provenance, setProvenance] = useState<"REAL_EVIDENCE_DRIVEN" | "MOCK_ONLY" | "FALLBACK_DRIVEN" | "EMPTY">("EMPTY");
  // P0-3: Review feedback from Authoring interrupt payload (or review_feedback/latest.json)
  const [reviewFeedback, setReviewFeedback] = useState<ReviewFeedbackPayload | null>(null);

  useEffect(() => {
    let cancelled = false;

    const init = async () => {
      // 1. Try real V5 API first
      try {
        const latest = await getLatestWorkbench(projectId);
        if (!cancelled && latest && latest.slots && latest.slots.length > 0) {
          setHeatmap(latest.heatmap ?? []);
          setProvenance("REAL_EVIDENCE_DRIVEN");
          await refresh(projectId, latest.workbench_id);
          return;
        }
      } catch (e) {
        console.warn("getLatestWorkbench failed:", e);
      }

      // 2. Fallback to localStorage bridge
      const payload = loadBridgePayload();
      if (!cancelled) setBridgePayload(payload);

      const groups = payload?.human_confirmation_packet?.source_family_groups;
      const hasRealGroups = groups && groups.length > 0;

      if (hasRealGroups) {
        const nextGroups = groups;
        if (!cancelled) {
          setSourceFamilyGroups(nextGroups);
          setProvenance("FALLBACK_DRIVEN");
        }
        try {
          const response = await build(projectId, nextGroups as unknown as Record<string, unknown>[]);
          if (!cancelled && response?.heatmap) {
            setHeatmap(response.heatmap);
          }
        } catch (e) {
          console.warn("buildSlotWorkbench from bridge failed:", e);
        }
        return;
      }

      // 3. Dev-only MOCK fallback
      const mockGroups = buildFallbackFamilyGroups();
      if (mockGroups.length > 0) {
        if (!cancelled) {
          setSourceFamilyGroups(mockGroups);
          setProvenance("MOCK_ONLY");
        }
        try {
          const response = await build(projectId, mockGroups as unknown as Record<string, unknown>[]);
          if (!cancelled && response?.heatmap) {
            setHeatmap(response.heatmap);
          }
        } catch (e) {
          console.warn("buildSlotWorkbench from mock failed:", e);
        }
        return;
      }

      // 4. Empty state
      if (!cancelled) {
        setProvenance("EMPTY");
      }
    };

    void init();
    return () => { cancelled = true; };
  }, [build, projectId]);

  const runGapAnalysis = useCallback(async () => {
    if (!workbenchId) return;
    setGapLoading(true);
    try {
      const res = await analyzeGaps(projectId, workbenchId, flavor);
      setGPoints(res.g_points ?? []);
    } catch (e) {
      console.error("Gap analysis failed:", e);
    } finally {
      setGapLoading(false);
    }
  }, [projectId, workbenchId, flavor]);

  const runCopilot = useCallback(
    async (question?: string) => {
      if (!workbenchId) return;
      setCopilotLoading(true);
      try {
        const res = await draftCopilotSuggestions(
          projectId,
          "slot_workbench",
          workbenchId,
          undefined,
          question
        );
        setCopilotSuggestions(res.suggestions ?? []);
      } catch (e) {
        console.error("Copilot draft failed:", e);
      } finally {
        setCopilotLoading(false);
      }
    },
    [projectId, workbenchId]
  );

  const runBatchDraft = useCallback(
    async (operation: string, title: string) => {
      if (!workbenchId) return;
      const res = await draftBatchOperation(projectId, operation, workbenchId);
      setCopilotSuggestions(makeBatchSuggestions(title, res.batch_draft_id, (res.staged_actions ?? []) as { action_id: string; action_type: string }[]));
    },
    [projectId, workbenchId]
  );

  const runBacktest = useCallback(async () => {
    if (!workbenchId) return;
    setShadowLoading(true);
    try {
      const res = await runShadowBacktest(projectId, workbenchId, {
        confidence_score_delta: -0.04,
        open_file_penalty: 0.08,
        large_file_penalty: 0.1,
      });
      setShadowReport(res.report ?? null);
    } catch (e) {
      console.error("Shadow backtest failed:", e);
    } finally {
      setShadowLoading(false);
    }
  }, [projectId, workbenchId]);

  useEffect(() => {
    if (!workbenchId) return;
    void runGapAnalysis();
    void runCopilot("What should I do next?");
  }, [runCopilot, runGapAnalysis, workbenchId]);

  const summary = useMemo(() => {
    const counts = {
      high: heatmap.filter((item) => item.confidence_band === "HIGH").length,
      medium: heatmap.filter((item) => item.confidence_band === "MEDIUM").length,
      low: heatmap.filter((item) => item.confidence_band === "LOW").length,
      missing: heatmap.filter((item) => item.confidence_band === "MISSING").length,
      blocking: gPoints.filter((item) => item.blocking_level === "BLOCKING").length,
    };
    return counts;
  }, [gPoints, heatmap]);

  const unscannedRegister = bridgePayload?.human_confirmation_packet?.unscanned_file_register ?? null;

  return (
    <div className="container mx-auto py-6 space-y-6">
      {provenance === "MOCK_ONLY" && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
          <div className="font-semibold">MOCK DATA — NOT REAL EVIDENCE</div>
          <div>
            This workbench is displaying hard-coded fallback data because no real source package scan result was found.
            Run a source package scan from Complete Project Run to see real evidence. Do not treat these slots as regulatory basis.
          </div>
        </div>
      )}
      {provenance === "REAL_EVIDENCE_DRIVEN" && (
        <div className="rounded-md border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-800">
          <div className="font-semibold">REAL EVIDENCE DRIVEN</div>
          <div>
            These slots are derived from a real source package scan. Recommendations are not confirmations; human gate is still required.
          </div>
        </div>
      )}
      {provenance === "EMPTY" && (
        <div className="rounded-md border border-slate-300 bg-slate-50 p-4 text-sm text-slate-800">
          <div className="font-semibold">No source package scan result found</div>
          <div>
            Run <strong>Complete Project Run</strong> first to generate a source package scan and workbench. This page will then load real evidence automatically.
          </div>
        </div>
      )}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">Source Slot Workbench</h1>
            <Badge variant="outline">Slot-first</Badge>
          </div>
          <p className="text-sm text-muted-foreground max-w-3xl">
            Reviewer workload should focus on blocking gaps and medium-confidence slots first. Raw candidate browsing remains available as a secondary audit layer.
          </p>
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span>Recommendation is not confirmation.</span>
            <span>Controlled hold is valid when reason and next action are explicit.</span>
            <span>HTTP 500 is never an acceptable controlled state.</span>
          </div>
        </div>
        <ReviewFlavorSelector value={flavor} onChange={setFlavor} />
      </div>

      <div className="grid gap-3 md:grid-cols-5">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Blocking Gaps</CardTitle></CardHeader>
          <CardContent className="text-2xl font-semibold">{summary.blocking}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">High Confidence</CardTitle></CardHeader>
          <CardContent className="text-2xl font-semibold">{summary.high}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Medium Attention</CardTitle></CardHeader>
          <CardContent className="text-2xl font-semibold">{summary.medium}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Low Confidence</CardTitle></CardHeader>
          <CardContent className="text-2xl font-semibold">{summary.low}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Missing Slots</CardTitle></CardHeader>
          <CardContent className="text-2xl font-semibold">{summary.missing}</CardContent>
        </Card>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <Tabs defaultValue="slots" className="w-full">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="slots">Source Slots</TabsTrigger>
          <TabsTrigger value="heatmap">Confidence Heatmap</TabsTrigger>
          <TabsTrigger value="gaps">Actionable Gaps</TabsTrigger>
          <TabsTrigger value="copilot">Review Copilot</TabsTrigger>
          <TabsTrigger value="shadow">Shadow Backtest</TabsTrigger>
          <TabsTrigger value="feedback">Review Feedback</TabsTrigger>
          <TabsTrigger value="raw-audit">Raw Audit</TabsTrigger>
        </TabsList>

        <TabsContent value="slots" className="space-y-4">
          <div className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
            Source Slot Mode is the primary workflow. Reviewer should confirm, reselect, mark missing, or mark open-file-check from slot cards instead of browsing 300+ raw files as the main task.
          </div>
          <SourceSlotWorkbench
            slots={slots}
            onConfirm={(slotId, fileId) => confirm(projectId, slotId, fileId)}
            onReselect={(slotId, fileId, reason) => reselect(projectId, slotId, fileId, reason)}
            onMarkMissing={(slotId, reason) => markMissing(projectId, slotId, reason)}
            onMarkOpenFile={(slotId, fileIds, reason) => markOpenFile(projectId, slotId, fileIds, reason)}
            loading={loading}
          />
        </TabsContent>

        <TabsContent value="heatmap" className="space-y-4">
          <ConfidenceHeatmap heatmap={heatmap} />
        </TabsContent>

        <TabsContent value="gaps" className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => void runGapAnalysis()} disabled={gapLoading || !workbenchId}>
              {gapLoading ? "Analyzing..." : "Refresh Actionable Gaps"}
            </Button>
          </div>
          <GapPointPanel gPoints={gPoints} />
        </TabsContent>

        <TabsContent value="copilot" className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void runCopilot("What should I do next?")} disabled={!workbenchId || copilotLoading}>
              {copilotLoading ? "Drafting..." : "Draft Next Action"}
            </Button>
            <Button variant="outline" onClick={() => void runBatchDraft("stage_high_confidence", "batch_draft")} disabled={!workbenchId}>
              Stage High Confidence
            </Button>
            <Button variant="outline" onClick={() => void runBatchDraft("draft_open_file_checks", "open_file_check")} disabled={!workbenchId}>
              Draft Open-file-check List
            </Button>
            <Button variant="outline" onClick={() => void runBatchDraft("show_blocking_gaps", "hold_explanation")} disabled={!workbenchId}>
              Show Only Blocking Gaps
            </Button>
            <Button variant="outline" onClick={() => void runBatchDraft("switch_to_source_slot_mode", "slot_mode_switch")} disabled={!workbenchId}>
              Switch to Source Slot Mode
            </Button>
          </div>
          <ReviewCopilotDrawer suggestions={copilotSuggestions} />
        </TabsContent>

        <TabsContent value="shadow" className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void runBacktest()} disabled={!workbenchId || shadowLoading}>
              {shadowLoading ? "Running..." : "Run Shadow Backtest"}
            </Button>
          </div>
          {shadowReport ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Sandbox Backtest Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div>{String(shadowReport.drift_risk_assessment ?? "")}</div>
                <div>{String(shadowReport.false_positive_risk ?? "")}</div>
                <div>{String(shadowReport.false_negative_risk ?? "")}</div>
                <div>{String(shadowReport.regression_risk ?? "")}</div>
                <div className="text-muted-foreground">{String(shadowReport.rollback_plan ?? "")}</div>
              </CardContent>
            </Card>
          ) : (
            <div className="text-sm text-muted-foreground">
              No shadow backtest report yet. Sandbox evidence is not approval.
            </div>
          )}
        </TabsContent>

        <TabsContent value="feedback" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Review Feedback (Advisory-Only)</CardTitle>
            </CardHeader>
            <CardContent>
              <ReviewFeedbackPanel
                feedback={reviewFeedback}
                onResolve={(actions: FeedbackAction[]) => {
                  toast.success(`Resolved ${actions.length} findings`);
                  console.log("Feedback actions:", actions);
                }}
              />
              {!reviewFeedback && (
                <div className="mt-4">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setReviewFeedback({
                        advisory_only: true,
                        finding_count: 3,
                        message: "CER Review found 3 findings relevant to claims.",
                        findings: [
                          {
                            finding_id: "F-001",
                            severity: "CRITICAL",
                            evidence_depth: "PRIMARY_VERBATIM",
                            category: "cross_doc_inconsistency",
                            description: "CER Section 4.2 states indication X covers population Y, but IFU Section 3.1 restricts indication X to population Z.",
                            suggested_rework_node: "claim_decomposition",
                            rationale: "Claim ledger must reconcile indication/population mismatch before PICO derivation.",
                            target_claim_id: "CER-4.2-IND-X",
                          },
                          {
                            finding_id: "F-002",
                            severity: "HIGH",
                            evidence_depth: "SECONDARY_SUMMARY",
                            category: "evidence_quality_gap",
                            description: "Pivotal evidence E-205 only contains PubMed abstract — no full-text verification.",
                            suggested_rework_node: "evidence_appraisal",
                            rationale: "G41 gate requires PRIMARY_VERBATIM or PRIMARY_DERIVED for pivotal evidence.",
                            target_evidence_id: "E-205",
                          },
                          {
                            finding_id: "F-003",
                            severity: "MEDIUM",
                            evidence_depth: "PRIMARY_DERIVED",
                            category: "terminology_non_standard",
                            description: "Non-standard terminology 'burn lesion' used instead of 'skin burn' in clinical description.",
                            suggested_rework_node: "writer_synthesis",
                          },
                        ],
                      });
                    }}
                  >
                    Load Demo Feedback
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="raw-audit" className="space-y-4">
          <div className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
            Raw Candidate Audit is retained as secondary evidence. It should stay available, but it should not be the primary reviewer workflow.
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Source Family Groups</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {sourceFamilyGroups.map((group) => (
                  <div key={group.group_id} className="rounded-md border p-3 text-sm space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-medium">{group.source_type.toUpperCase()}</div>
                      <Badge variant="outline">{group.group_status}</Badge>
                    </div>
                    <div className="text-muted-foreground">{group.recommended_canonical_reason}</div>
                    <div className="text-xs text-muted-foreground">
                      Candidates {group.candidates.length} · Alternatives {group.alternatives.length} · Open-file {group.open_file_required.length}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Unscanned / Limited Coverage Register</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {unscannedRegister ? (
                  <>
                    <div>Unscanned count: {String((unscannedRegister as { unscanned_count?: number }).unscanned_count ?? 0)}</div>
                    <div>Large files skipped: {String(((unscannedRegister as { large_files_skipped?: unknown[] }).large_files_skipped ?? []).length)}</div>
                    <div>Extraction failed: {String(((unscannedRegister as { extraction_failed?: unknown[] }).extraction_failed ?? []).length)}</div>
                    <div>Needs open-file check: {String(((unscannedRegister as { needs_open_file_check?: unknown[] }).needs_open_file_check ?? []).length)}</div>
                  </>
                ) : (
                  <div className="text-muted-foreground">No persisted unscanned register available in local bridge result.</div>
                )}
                <div className="pt-2 text-xs text-muted-foreground">
                  No file is treated as fully reviewed unless open-file evidence exists.
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <Link href="/workspace/cer/governance/complete-project-run" className="underline underline-offset-4">
          Back to Complete Project Run
        </Link>
        {bridgePayload?.source_package_path && <span>Source package: {bridgePayload.source_package_path}</span>}
      </div>
    </div>
  );
}
