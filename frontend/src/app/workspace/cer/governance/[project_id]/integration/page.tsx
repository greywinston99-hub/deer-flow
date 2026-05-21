"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
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
import { cerReviewFetch, useCERAuth } from "@/core/cer_auth";
import { getBackendBaseURL } from "@/core/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ReviewMark = "confirmed" | "needs_follow_up" | "dismissed" | "parked";

interface IntegrationStatus {
  project_id: string;
  integration_run_id: string;
  status: "not_started" | "running" | "completed" | "failed" | "already_completed";
  stages: Record<string, string>;
  started_at: string | null;
  completed_at: string | null;
  errors: string[];
}

// Unified view response
interface IntegrationViewSummary {
  total_linkages: number;
  total_findings: number;
  historical_incomplete: number;
  knowledge_suggestions: number;
  reviewer_marks: number;
}

interface IntegrationViewResponse {
  project_id: string;
  integration_run_id: string | null;
  status: string;
  summary: IntegrationViewSummary;
  linkages: LinkageItem[];
  findings: FindingItem[];
  knowledge_suggestions: SuggestionItem[];
  reviewer_marks: ReviewMarkRecord[];
}

interface LinkageItem {
  linkage_id: string;
  cer_element: string;
  rmf_element: string;
  ifu_element: string | null;
  linkage_type: string;
  consistency_status: string;
  confidence: number | null;
  requires_human_review: boolean;
  source_artifact_path: string | null;
  notes: string | null;
  reviewer_mark: string | null;
}

interface FindingItem {
  finding_id: string;
  category: string;
  finding_type: string;
  title: string;
  description: string;
  severity: string | null;
  source_artifact_path: string | null;
  confidence: number | null;
  requires_human_review: boolean;
  reviewer_mark: string | null;
}

interface GapItem {
  gap_id: string;
  gap_type: string;
  topic: string;
  description: string;
  impacted_linkages: string[];
  source_hint: string | null;
  requires_human_review: boolean;
  reviewer_mark: string | null;
}

interface SuggestionItem {
  suggestion_id: string;
  asset_type: string;
  suggested_content: string;
  source_artifact_path: string;
  rationale: string;
  confidence: number | null;
  requires_human_review: boolean;
  reviewer_mark: string | null;
}

interface ReviewMarkRecord {
  item_id: string;
  item_type: string;
  mark: string;
  notes: string | null;
  marked_at: string;
  marked_by: string | null;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function getIntegrationStatus(projectId: string): Promise<IntegrationStatus> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/integration/status`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function triggerIntegrationRun(projectId: string, forceRerun: boolean): Promise<unknown> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/integration/run`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force_rerun: forceRerun }),
    }
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getIntegrationView(projectId: string): Promise<IntegrationViewResponse> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/integration/view`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getGaps(projectId: string): Promise<{ gaps: GapItem[] }> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/integration/gaps`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function actOnKnowledgeSuggestion(
  projectId: string,
  suggestionId: string,
  action: "confirm" | "dismiss" | "park",
  notes?: string
): Promise<unknown> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/integration/knowledge-suggestion/${encodeURIComponent(suggestionId)}/action`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, notes }),
    }
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function submitReviewMark(
  projectId: string,
  itemId: string,
  itemType: string,
  mark: ReviewMark,
  notes?: string
): Promise<unknown> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/integration/review-mark`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_id: itemId, item_type: itemType, mark, notes }),
    }
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CONSISTENCY_COLOR: Record<string, string> = {
  consistent: "bg-green-100 text-green-800",
  inconsistent: "bg-red-100 text-red-800",
  needs_review: "bg-yellow-100 text-yellow-800",
  historical_incomplete: "bg-gray-100 text-gray-600",
  unresolved_gap: "bg-orange-100 text-orange-800",
};

const MARK_BADGE: Record<ReviewMark, string> = {
  confirmed: "bg-green-50 border-green-200 text-green-700",
  needs_follow_up: "bg-yellow-50 border-yellow-200 text-yellow-700",
  dismissed: "bg-gray-50 border-gray-200 text-gray-600",
  parked: "bg-blue-50 border-blue-200 text-blue-700",
};

const CATEGORY_LABELS: Record<string, string> = {
  intended_purpose: "Intended Purpose",
  benefit_risk: "Benefit-Risk",
  residual_risk: "Residual Risk",
  ifu_risk: "IFU Risk",
  pms_pmcf: "PMS/PMCF",
  finding_rmf: "CER Finding ↔ RMF",
  knowledge_suggestion: "Knowledge Suggestion",
};

function MarkButton({
  itemId,
  itemType,
  currentMark,
  onMarked,
}: {
  itemId: string;
  itemType: string;
  currentMark: string | null;
  onMarked: (mark: ReviewMark) => void;
}) {
  return (
    <div className="flex gap-1 mt-2">
      {(Object.keys(MARK_BADGE) as ReviewMark[]).map((mark) => (
        <Button
          key={mark}
          variant="outline"
          className={`text-[10px] h-6 ${currentMark === mark ? MARK_BADGE[mark] : ""}`}
          onClick={() => onMarked(mark)}
        >
          {mark.replace("_", " ")}
        </Button>
      ))}
    </div>
  );
}

function FindingCard({ finding, onMark }: { finding: FindingItem; onMark: (mark: ReviewMark) => void }) {
  return (
    <div className="border rounded-lg p-3 space-y-1">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <Badge variant="outline" className="text-[10px]">
              {CATEGORY_LABELS[finding.category] || finding.category}
            </Badge>
            <Badge variant="outline" className="text-[10px]">
              {finding.finding_type.replace("_", " ")}
            </Badge>
            {finding.severity && (
              <Badge
                variant="outline"
                className={`text-[10px] ${
                  finding.severity === "high"
                    ? "border-red-300 text-red-600"
                    : finding.severity === "medium"
                    ? "border-yellow-300 text-yellow-600"
                    : "border-gray-300 text-gray-500"
                }`}
              >
                {finding.severity}
              </Badge>
            )}
            {finding.requires_human_review && (
              <Badge variant="outline" className="text-[10px] border-orange-300 text-orange-600">
                needs review
              </Badge>
            )}
            {finding.reviewer_mark && (
              <Badge className={`text-[10px] ${MARK_BADGE[finding.reviewer_mark as ReviewMark]}`}>
                {finding.reviewer_mark.replace("_", " ")}
              </Badge>
            )}
          </div>
          <p className="text-sm font-medium mt-1">{finding.title}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{finding.description}</p>
          {finding.source_artifact_path && (
            <p className="text-[10px] text-muted-foreground font-mono mt-0.5 truncate">
              src: {finding.source_artifact_path}
            </p>
          )}
        </div>
      </div>
      <MarkButton
        itemId={finding.finding_id}
        itemType="finding"
        currentMark={finding.reviewer_mark as ReviewMark | null}
        onMarked={onMark}
      />
    </div>
  );
}

function LinkageCard({ linkage, onMark }: { linkage: LinkageItem; onMark: (mark: ReviewMark) => void }) {
  return (
    <div className="border rounded-lg p-3 space-y-1">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <Badge variant="outline" className="text-[10px]">
              {linkage.linkage_type.replace("_", " ")}
            </Badge>
            <Badge className={`text-[10px] ${CONSISTENCY_COLOR[linkage.consistency_status] || "bg-gray-100"}`}>
              {linkage.consistency_status.replace("_", " ")}
            </Badge>
            {linkage.requires_human_review && (
              <Badge variant="outline" className="text-[10px] border-orange-300 text-orange-600">
                needs review
              </Badge>
            )}
            {linkage.reviewer_mark && (
              <Badge className={`text-[10px] ${MARK_BADGE[linkage.reviewer_mark as ReviewMark]}`}>
                {linkage.reviewer_mark.replace("_", " ")}
              </Badge>
            )}
          </div>
          <p className="text-xs mt-1">
            <span className="text-muted-foreground">CER:</span> {linkage.cer_element}
          </p>
          <p className="text-xs">
            <span className="text-muted-foreground">RMF:</span> {linkage.rmf_element}
          </p>
          {linkage.ifu_element && (
            <p className="text-xs">
              <span className="text-muted-foreground">IFU:</span> {linkage.ifu_element}
            </p>
          )}
          {linkage.notes && (
            <p className="text-[10px] text-muted-foreground mt-0.5">{linkage.notes}</p>
          )}
        </div>
      </div>
      <MarkButton
        itemId={linkage.linkage_id}
        itemType="linkage"
        currentMark={linkage.reviewer_mark as ReviewMark | null}
        onMarked={onMark}
      />
    </div>
  );
}

function GapCard({ gap, onMark }: { gap: GapItem; onMark: (mark: ReviewMark) => void }) {
  return (
    <div className="border rounded-lg p-3 space-y-1">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <Badge variant="outline" className="text-[10px]">
              {gap.gap_type.replace("_", " ")}
            </Badge>
            {gap.requires_human_review && (
              <Badge variant="outline" className="text-[10px] border-orange-300 text-orange-600">
                needs review
              </Badge>
            )}
            {gap.reviewer_mark && (
              <Badge className={`text-[10px] ${MARK_BADGE[gap.reviewer_mark as ReviewMark]}`}>
                {gap.reviewer_mark.replace("_", " ")}
              </Badge>
            )}
          </div>
          <p className="text-sm font-medium mt-1">{gap.topic}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{gap.description}</p>
          {gap.source_hint && (
            <p className="text-[10px] text-muted-foreground font-mono mt-0.5">hint: {gap.source_hint}</p>
          )}
          {gap.impacted_linkages.length > 0 && (
            <p className="text-[10px] text-muted-foreground mt-0.5">
              impacts: {gap.impacted_linkages.join(", ")}
            </p>
          )}
        </div>
      </div>
      <MarkButton
        itemId={gap.gap_id}
        itemType="gap"
        currentMark={gap.reviewer_mark as ReviewMark | null}
        onMarked={onMark}
      />
    </div>
  );
}

function SuggestionCard({ suggestion, onMark }: { suggestion: SuggestionItem; onMark: (mark: ReviewMark) => void }) {
  return (
    <div className="border rounded-lg p-3 space-y-1">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <Badge variant="outline" className="text-[10px]">
              {suggestion.asset_type.replace("_", " ")}
            </Badge>
            {suggestion.requires_human_review && (
              <Badge variant="outline" className="text-[10px] border-orange-300 text-orange-600">
                needs review
              </Badge>
            )}
            {suggestion.reviewer_mark && (
              <Badge className={`text-[10px] ${MARK_BADGE[suggestion.reviewer_mark as ReviewMark]}`}>
                {suggestion.reviewer_mark.replace("_", " ")}
              </Badge>
            )}
          </div>
          <p className="text-xs mt-1 font-medium">Type: {suggestion.asset_type}</p>
          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-3">{suggestion.suggested_content}</p>
          <p className="text-[10px] text-muted-foreground mt-0.5 font-mono truncate">
            src: {suggestion.source_artifact_path}
          </p>
        </div>
      </div>
      <MarkButton
        itemId={suggestion.suggestion_id}
        itemType="suggestion"
        currentMark={suggestion.reviewer_mark as ReviewMark | null}
        onMarked={onMark}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

type ActiveTab = "overview" | "linkage" | "findings" | "gaps" | "suggestions" | "human-review";

export default function IntegrationPage() {
  const params = useParams();
  const projectId = decodeURIComponent(params.project_id as string);
  const { user } = useCERAuth();

  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [viewData, setViewData] = useState<IntegrationViewResponse | null>(null);
  const [gaps, setGaps] = useState<GapItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const s = await getIntegrationStatus(projectId);
      setStatus(s);
    } catch {
      /* ignore — status endpoint may 404 before first run */
    }
  }, [projectId]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [view, gapsData] = await Promise.all([
        getIntegrationView(projectId).catch(() => null),
        getGaps(projectId).catch(() => null),
      ]);
      setViewData(view);
      setGaps(gapsData?.gaps ?? []);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const handleRun = useCallback(async () => {
    setRunning(true);
    try {
      await triggerIntegrationRun(projectId, true);
      toast.success("Integration run triggered");
      await loadStatus();
      await loadAll();
    } catch (e) {
      toast.error(`Failed to trigger run: ${e}`);
    } finally {
      setRunning(false);
    }
  }, [projectId, loadStatus, loadAll]);

  const handleMark = useCallback(
    async (itemId: string, itemType: string, mark: ReviewMark) => {
      try {
        await submitReviewMark(projectId, itemId, itemType, mark);
        toast.success(`Marked as ${mark}`);
        await loadAll();
      } catch (e) {
        toast.error(`Failed to mark: ${e}`);
      }
    },
    [projectId, loadAll]
  );

  const handleSuggestionAction = useCallback(
    async (suggestionId: string, action: "confirm" | "dismiss" | "park") => {
      try {
        await actOnKnowledgeSuggestion(projectId, suggestionId, action);
        toast.success(`Suggestion ${action}`);
        await loadAll();
      } catch (e) {
        toast.error(`Failed to act on suggestion: ${e}`);
      }
    },
    [projectId, loadAll]
  );

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (status?.status === "completed") {
      void loadAll();
    }
  }, [status, loadAll]);

  const TABS: { id: ActiveTab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "linkage", label: "Linkage Matrix" },
    { id: "findings", label: "Findings" },
    { id: "gaps", label: "Evidence Gaps" },
    { id: "suggestions", label: "Knowledge" },
    { id: "human-review", label: "Human Review" },
  ];

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
                href={`/workspace/cer/governance/${encodeURIComponent(projectId)}`}
                className="hover:underline"
              >
                ← Run Detail
              </Link>
            </div>
            <h2 className="text-sm font-semibold">RMF × CER Integration</h2>
            <p className="text-xs text-muted-foreground">Cross-Document Review</p>
          </div>

          {/* Status */}
          <div className="p-2 border-b">
            <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">STATUS</div>
            <div className="space-y-1">
              {status ? (
                <>
                  <div
                    className={`text-[10px] px-2 py-1 rounded ${
                      status.status === "completed"
                        ? "bg-green-100 text-green-800"
                        : status.status === "running"
                        ? "bg-blue-100 text-blue-800"
                        : status.status === "failed"
                        ? "bg-red-100 text-red-800"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {status.status.replace("_", " ")} {status.integration_run_id && `- ${status.integration_run_id}`}
                  </div>
                  {Object.entries(status.stages).map(([stage, s]) => (
                    <div key={stage} className="flex items-center justify-between text-[10px] px-2">
                      <span className="truncate font-mono">{stage}</span>
                      <span
                        className={
                          s === "completed"
                            ? "text-green-600"
                            : s === "failed"
                            ? "text-red-600"
                            : "text-gray-400"
                        }
                      >
                        {s}
                      </span>
                    </div>
                  ))}
                  {status.errors.length > 0 && (
                    <div className="text-[10px] text-red-600 px-2">{status.errors.length} errors</div>
                  )}
                </>
              ) : (
                <div className="text-[10px] text-muted-foreground px-2">Not started</div>
              )}
            </div>
            <Button
              size="sm"
              className="w-full mt-2 text-xs h-7"
              onClick={() => void handleRun()}
              disabled={running}
            >
              {running ? "Running..." : "Run Integration"}
            </Button>
          </div>

          {/* Tab navigation */}
          <div className="p-2 space-y-1 flex-1 overflow-y-auto">
            <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">SECTIONS</div>
            {TABS.map((tab) => (
              <Button
                key={tab.id}
                variant="ghost"
                size="sm"
                className={`w-full justify-start text-xs h-7 ${
                  activeTab === tab.id ? "bg-primary/10 border border-primary/30" : ""
                }`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === "overview" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold">RMF × CER Integration Overview</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Read-only cross-document integration view. Reviewer-assistive only — does NOT make
                  regulatory decisions. Reviewer marks are separate from Gate 1 / Gate 3 / BRR /
                  Decision Ledger.
                </p>
              </div>

              {/* Summary cards */}
              <div className="grid grid-cols-4 gap-4">
                <Card>
                  <CardHeader className="pb-1">
                    <CardTitle className="text-sm">Linkages</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{viewData?.summary.total_linkages ?? "—"}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-1">
                    <CardTitle className="text-sm">Findings</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{viewData?.summary.total_findings ?? "—"}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-1">
                    <CardTitle className="text-sm">Evidence Gaps</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{gaps.length ?? "—"}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-1">
                    <CardTitle className="text-sm">Knowledge Suggestions</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{viewData?.summary.knowledge_suggestions ?? "—"}</div>
                  </CardContent>
                </Card>
              </div>

              {/* Integration run info */}
              {status && status.status !== "not_started" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Integration Run</CardTitle>
                    <CardDescription className="text-xs">
                      {status.integration_run_id} · {status.started_at && new Date(status.started_at).toLocaleString()}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-4 gap-2">
                      {Object.entries(status.stages).map(([stage, s]) => (
                        <div
                          key={stage}
                          className={`text-[10px] px-2 py-1 rounded ${
                            s === "completed"
                              ? "bg-green-100 text-green-800"
                              : s === "failed"
                              ? "bg-red-100 text-red-800"
                              : "bg-gray-50 text-gray-600"
                          }`}
                        >
                          {stage}: {s}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Notice */}
              <Card className="border-blue-200 bg-blue-50">
                <CardContent className="pt-4">
                  <p className="text-xs text-blue-800">
                    <strong>Reviewer-assistive only.</strong> This view surfaces cross-document
                    inconsistencies, evidence gaps, and linkage suggestions. It does NOT automatically
                    decide RMF acceptability, CER acceptability, BRR final status, or any regulatory
                    conclusion. Gate 1 / Gate 3 / Decision Ledger semantics are unchanged. Knowledge
                    suggestions are surfaced but NOT auto-applied.
                  </p>
                </CardContent>
              </Card>
            </div>
          )}

          {activeTab === "linkage" && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold">RMF × CER Linkage Matrix</h2>
              {loading ? (
                <p className="text-muted-foreground">Loading...</p>
              ) : viewData ? (
                <>
                  {viewData.linkages.length === 0 ? (
                    <p className="text-muted-foreground text-sm">No linkages found. Run integration first.</p>
                  ) : (
                    <div className="space-y-2">
                      {viewData.linkages.map((lnk) => (
                        <LinkageCard key={lnk.linkage_id} linkage={lnk} onMark={(m) => void handleMark(lnk.linkage_id, "linkage", m)} />
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <p className="text-muted-foreground text-sm">Run integration to generate linkage matrix.</p>
              )}
            </div>
          )}

          {activeTab === "findings" && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold">Consistency Findings</h2>
              {loading ? (
                <p className="text-muted-foreground">Loading...</p>
              ) : viewData ? (
                <div className="space-y-2">
                  {viewData.findings.map((f) => (
                    <FindingCard key={f.finding_id} finding={f} onMark={(m) => void handleMark(f.finding_id, "finding", m)} />
                  ))}
                  {viewData.findings.length === 0 && (
                    <p className="text-muted-foreground text-sm">No findings. Run integration first.</p>
                  )}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">Run integration to generate findings.</p>
              )}
            </div>
          )}

          {activeTab === "gaps" && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold">Evidence Gaps</h2>
              {loading ? (
                <p className="text-muted-foreground">Loading...</p>
              ) : (
                <div className="space-y-2">
                  {gaps.map((g) => (
                    <GapCard key={g.gap_id} gap={g} onMark={(m) => void handleMark(g.gap_id, "gap", m)} />
                  ))}
                  {gaps.length === 0 && (
                    <p className="text-muted-foreground text-sm">No gaps identified. Run integration first.</p>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === "suggestions" && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold">Knowledge Suggestions</h2>
              <Card className="border-blue-200 bg-blue-50">
                <CardContent className="pt-4">
                  <p className="text-xs text-blue-800">
                    These are suggestions only. Knowledge assets are NOT auto-applied and NOT
                    auto-published. New candidates must go through the knowledge review gate.
                  </p>
                </CardContent>
              </Card>
              {loading ? (
                <p className="text-muted-foreground">Loading...</p>
              ) : viewData ? (
                <div className="space-y-2">
                  {viewData.knowledge_suggestions.map((s) => (
                    <SuggestionCard
                      key={s.suggestion_id}
                      suggestion={s}
                      onMark={(m) => void handleSuggestionAction(s.suggestion_id, m === "confirmed" ? "confirm" : m === "dismissed" ? "dismiss" : "park")}
                    />
                  ))}
                  {viewData.knowledge_suggestions.length === 0 && (
                    <p className="text-muted-foreground text-sm">No suggestions. Run integration first.</p>
                  )}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">Run integration to generate suggestions.</p>
              )}
            </div>
          )}

          {activeTab === "human-review" && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold">Human Review Required Items</h2>
              <p className="text-sm text-muted-foreground">
                All items flagged as requiring human review. Reviewer marks are persisted separately
                from Gate decisions, BRR matrix, and Decision Ledger.
              </p>

              {loading ? (
                <p className="text-muted-foreground">Loading...</p>
              ) : (
                <div className="space-y-6">
                  {/* Linkages needing review */}
                  <div>
                    <h3 className="text-sm font-medium mb-2">Linkages ({viewData?.linkages.filter((l) => l.requires_human_review).length ?? 0})</h3>
                    <div className="space-y-2">
                      {viewData?.linkages
                        .filter((l) => l.requires_human_review)
                        .map((lnk) => (
                          <LinkageCard key={lnk.linkage_id} linkage={lnk} onMark={(m) => void handleMark(lnk.linkage_id, "linkage", m)} />
                        ))}
                    </div>
                  </div>

                  {/* Findings needing review */}
                  <div>
                    <h3 className="text-sm font-medium mb-2">Findings ({viewData?.findings.filter((f) => f.requires_human_review).length ?? 0})</h3>
                    <div className="space-y-2">
                      {viewData?.findings
                        .filter((f) => f.requires_human_review)
                        .map((f) => (
                          <FindingCard key={f.finding_id} finding={f} onMark={(m) => void handleMark(f.finding_id, "finding", m)} />
                        ))}
                    </div>
                  </div>

                  {/* Gaps needing review */}
                  <div>
                    <h3 className="text-sm font-medium mb-2">Evidence Gaps ({gaps.filter((g) => g.requires_human_review).length ?? 0})</h3>
                    <div className="space-y-2">
                      {gaps
                        .filter((g) => g.requires_human_review)
                        .map((g) => (
                          <GapCard key={g.gap_id} gap={g} onMark={(m) => void handleMark(g.gap_id, "gap", m)} />
                        ))}
                    </div>
                  </div>

                  {/* Suggestions needing review */}
                  <div>
                    <h3 className="text-sm font-medium mb-2">Knowledge Suggestions ({viewData?.knowledge_suggestions.filter((s) => s.requires_human_review).length ?? 0})</h3>
                    <div className="space-y-2">
                      {viewData?.knowledge_suggestions
                        .filter((s) => s.requires_human_review)
                        .map((s) => (
                          <SuggestionCard
                            key={s.suggestion_id}
                            suggestion={s}
                            onMark={(m) => void handleSuggestionAction(s.suggestion_id, m === "confirmed" ? "confirm" : m === "dismissed" ? "dismiss" : "park")}
                          />
                        ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
