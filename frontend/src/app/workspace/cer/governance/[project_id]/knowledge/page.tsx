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
import { useCERAuth, cerReviewFetch } from "@/core/cer_auth";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface KnowledgeCandidate {
  candidate_id: string;
  asset_type: string;
  source_artifact: string;
  source_chain: string[];
  state: string;
  payload: Record<string, unknown>;
  confidence: number;
  project_id: string;
  extracted_at: string;
  reviewed_at: string | null;
  published_at: string | null;
  review_decision: string | null;
  review_notes: string | null;
  reviewed_by: string | null;
}

interface CandidateListResponse {
  project_id: string;
  total: number;
  candidates: KnowledgeCandidate[];
}

interface ContainerIndexResponse {
  project_id: string;
  generated_at: string;
  asset_types: Record<string, Record<string, unknown>>;
  total_published: number;
}

interface ExtractResponse {
  project_id: string;
  candidates_extracted: number;
  by_type: Record<string, number>;
  by_state: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Asset type display names
// ---------------------------------------------------------------------------

const ASSET_TYPE_LABELS: Record<string, string> = {
  RuleUnit: "Regulatory Rule",
  MethodUnit: "Method/Procedure",
  FailurePattern: "Failure Pattern",
  ChecklistUnit: "Checklist Item",
  BoundaryCondition: "Boundary Condition",
  CrossDocumentMapping: "Cross-Doc Mapping",
  TerminologyUnit: "Terminology",
  EvidenceRequirement: "Evidence Requirement",
  ReviewHeuristic: "Review Heuristic",
  CaseLesson: "Case Lesson",
  WorkflowImprovement: "Workflow Improvement",
};

const STATE_LABELS: Record<string, { label: string; variant: "default" | "secondary" | "outline" | "destructive" }> = {
  extracted: { label: "Extracted", variant: "secondary" },
  normalized: { label: "Normalized", variant: "secondary" },
  needs_human_review: { label: "Pending Review", variant: "outline" },
  approved: { label: "Approved", variant: "default" },
  rejected: { label: "Rejected", variant: "destructive" },
  parked: { label: "Parked", variant: "secondary" },
  published: { label: "Published", variant: "default" },
};

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function listCandidates(projectId: string): Promise<CandidateListResponse> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/knowledge/candidates`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function listPendingReview(projectId: string): Promise<CandidateListResponse> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/knowledge/pending`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getContainerIndex(projectId: string): Promise<ContainerIndexResponse> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/knowledge/container`
  );
  if (r.status === 404) {
    return { project_id: projectId, generated_at: "", asset_types: {}, total_published: 0 };
  }
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function extractKnowledge(projectId: string): Promise<ExtractResponse> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/knowledge/extract`,
    { method: "POST" }
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function submitReview(
  projectId: string,
  candidateId: string,
  decision: "APPROVE" | "REJECT" | "PARK",
  notes?: string
): Promise<void> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/knowledge/candidates/${encodeURIComponent(candidateId)}/review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, notes }),
    }
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function KnowledgePage() {
  const params = useParams();
  const projectId = Array.isArray(params.project_id) ? params.project_id[0] : params.project_id;
  const { user } = useCERAuth();

  const [candidates, setCandidates] = useState<KnowledgeCandidate[]>([]);
  const [pending, setPending] = useState<KnowledgeCandidate[]>([]);
  const [container, setContainer] = useState<ContainerIndexResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<string | null>(null);

  const isReviewer = user?.role === "SENIOR_REVIEWER" || user?.role === "ADMIN";

  const loadData = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [candResult, pendResult, contResult] = await Promise.all([
        listCandidates(projectId).catch((e) => ({ project_id: projectId, total: 0, candidates: [] as KnowledgeCandidate[], _error: e })),
        listPendingReview(projectId).catch((e) => ({ project_id: projectId, total: 0, candidates: [] as KnowledgeCandidate[], _error: e })),
        getContainerIndex(projectId).catch((e) => { console.error(e); return null; }),
      ]);

      if ("_error" in candResult) {
        setCandidates([]);
      } else {
        setCandidates(candResult.candidates);
      }

      if ("_error" in pendResult) {
        setPending([]);
      } else {
        setPending(pendResult.candidates);
      }

      setContainer(contResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load knowledge data");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleExtract = async () => {
    if (!projectId) return;
    setExtracting(true);
    try {
      const result = await extractKnowledge(projectId);
      toast.success(
        `Extracted ${result.candidates_extracted} candidates: ${Object.entries(result.by_type).map(([k, v]) => `${k}: ${v}`).join(", ")}`
      );
      await loadData();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Extraction failed");
    } finally {
      setExtracting(false);
    }
  };

  const handleReview = async (candidateId: string, decision: "APPROVE" | "REJECT" | "PARK") => {
    if (!projectId) return;
    setSubmitting(candidateId);
    try {
      await submitReview(projectId, candidateId, decision, reviewNotes[candidateId] || undefined);
      toast.success(`Candidate ${candidateId} ${decision.toLowerCase()}d`);
      setReviewNotes((prev) => ({ ...prev, [candidateId]: "" }));
      await loadData();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Review submission failed");
    } finally {
      setSubmitting(null);
    }
  };

  // Group candidates by state
  const byState = candidates.reduce<Record<string, number>>((acc, c) => {
    acc[c.state] = (acc[c.state] || 0) + 1;
    return acc;
  }, {});

  // Group candidates by asset type
  const byType = candidates.reduce<Record<string, number>>((acc, c) => {
    acc[c.asset_type] = (acc[c.asset_type] || 0) + 1;
    return acc;
  }, {});

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-sm text-muted-foreground">Loading knowledge assets...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="rounded border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">Failed to load knowledge assets: {error}</p>
        </div>
        <Button variant="outline" onClick={loadData}>Retry</Button>
      </div>
    );
  }

  const hasAnyAssets = candidates.length > 0 || (container?.total_published ?? 0) > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Knowledge Assets</h1>
          <p className="text-sm text-muted-foreground">
            Extracted knowledge from CER artifacts — human review required for publication
          </p>
        </div>
        <Button onClick={handleExtract} disabled={extracting} variant="default">
          {extracting ? "Extracting..." : "Extract Knowledge"}
        </Button>
      </div>

      {/* State breakdown */}
      {candidates.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(byState).map(([state, count]) => {
            const info = STATE_LABELS[state] || { label: state, variant: "secondary" as const };
            return (
              <Card key={state} className="py-3">
                <CardContent className="text-center">
                  <p className="text-2xl font-bold">{count}</p>
                  <Badge variant={info.variant} className="mt-1 text-xs">{info.label}</Badge>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Published container summary */}
      {container && container.total_published > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Published Knowledge</CardTitle>
            <CardDescription>{container.total_published} published assets</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {Object.entries(container.asset_types).map(([type, info]) => {
                const typedInfo = info as { count?: number };
                return (
                  <Badge key={type} variant="default">
                    {ASSET_TYPE_LABELS[type] || type}: {typedInfo.count || 0}
                  </Badge>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Pending review candidates */}
      {pending.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pending Human Review ({pending.length})</CardTitle>
            <CardDescription>These candidates require human review before publication</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {pending.map((candidate) => (
              <div key={candidate.candidate_id} className="border rounded-lg p-4 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline">{ASSET_TYPE_LABELS[candidate.asset_type] || candidate.asset_type}</Badge>
                      <Badge variant="secondary" className="text-xs">{candidate.candidate_id}</Badge>
                      {candidate.confidence > 0 && (
                        <span className="text-xs text-muted-foreground">
                          confidence: {candidate.confidence.toFixed(2)}
                        </span>
                      )}
                    </div>
                    <p className="text-sm mt-1 break-all">
                      {typeof candidate.payload === "object" && candidate.payload !== null
                        ? JSON.stringify(candidate.payload).slice(0, 200)
                        : String(candidate.payload)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Source: {candidate.source_artifact}
                    </p>
                  </div>
                </div>

                {/* Review actions — only for SENIOR_REVIEWER or ADMIN */}
                {isReviewer && (
                  <div className="space-y-2 border-t pt-3">
                    <textarea
                      className="w-full text-sm border rounded p-2 resize-none"
                      rows={2}
                      placeholder="Review notes (optional)"
                      value={reviewNotes[candidate.candidate_id] || ""}
                      onChange={(e) =>
                        setReviewNotes((prev) => ({
                          ...prev,
                          [candidate.candidate_id]: e.target.value,
                        }))
                      }
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="default"
                        onClick={() => handleReview(candidate.candidate_id, "APPROVE")}
                        disabled={submitting === candidate.candidate_id}
                      >
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleReview(candidate.candidate_id, "PARK")}
                        disabled={submitting === candidate.candidate_id}
                      >
                        Park
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleReview(candidate.candidate_id, "REJECT")}
                        disabled={submitting === candidate.candidate_id}
                      >
                        Reject
                      </Button>
                    </div>
                  </div>
                )}

                {!isReviewer && (
                  <p className="text-xs text-muted-foreground border-t pt-2">
                    Only SENIOR_REVIEWER or ADMIN can submit review decisions.
                    Your current role: {user?.role || "unknown"}
                  </p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* All candidates table */}
      {candidates.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">All Candidates ({candidates.length})</CardTitle>
            <CardDescription>By asset type</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(byType).map(([type, count]) => (
                <div key={type} className="flex items-center justify-between py-1 border-b last:border-0">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">{ASSET_TYPE_LABELS[type] || type}</Badge>
                  </div>
                  <span className="text-sm font-medium">{count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty state */}
      {!hasAnyAssets && (
        <Card>
          <CardContent className="py-12 text-center">
            <div className="space-y-3">
              <div className="flex justify-center">
                <svg className="h-12 w-12 text-muted-foreground/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
              <div>
                <p className="font-medium text-muted-foreground">No knowledge assets yet</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Click &quot;Extract Knowledge&quot; to extract candidates from CER review artifacts.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
