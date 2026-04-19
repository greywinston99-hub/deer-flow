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
import { cerReviewFetch } from "@/core/cer_auth";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ClassificationFileEntry {
  file_id: string;
  relative_path: string;
  final_type: string | null;
  final_ep: string | null;
  confidence: number | null;
  requires_human_review: boolean;
  review_rationale: string | null;
}

interface ClassificationSummary {
  total_files: number;
  auto_proceed_eligible: boolean;
  high_confidence_count: number;
  low_confidence_count: number;
  unknown_ep_count: number;
}

interface ClassificationResponse {
  project_id: string;
  intake_session_id: string;
  summary: ClassificationSummary;
  files: ClassificationFileEntry[];
  missing_required_documents: Array<{
    ep: string;
    required_type: string;
    description: string;
    severity: string;
  }>;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function getClassification(projectId: string): Promise<ClassificationResponse> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/intake/classification`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ClassificationReviewPage() {
  const params = useParams();
  const projectId = decodeURIComponent(String(params.project_id));

  const [data, setData] = useState<ClassificationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getClassification(projectId);
      setData(result);
    } catch (e) {
      if (e instanceof Error) {
        // 404 = no intake session yet, show friendly empty state
        if (e.message.includes("404") || e.message.includes("not_started") || e.message.includes("no intake")) {
          setError("No classification data found. Run intake first.");
        } else if (e.message.includes("500") || e.message.includes("502") || e.message.includes("503") || e.message.includes("Network")) {
          // Real service failure - show toast for 5xx or network errors
          toast.error("Failed to load classification data. Service may be unavailable.");
          setError("Service error. Please try again later.");
        }
        // Other errors (400, 401, 403, etc.) - silently show empty state
      }
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <p>Loading classification data...</p>
      </div>
    );
  }

  if (error || !data) {
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
            <p className="text-xs text-muted-foreground mt-1">Classification Review</p>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-4">
            <div className="text-5xl">📋</div>
            <h2 className="text-xl font-semibold">No Classification Data</h2>
            <p className="text-sm text-muted-foreground max-w-md">
              {error || "Classification data will appear here after running the intake pipeline."}
            </p>
            <Button asChild>
              <Link href={`../`}>View Intake Status</Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const { summary, files, missing_required_documents } = data;

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
          <p className="text-xs text-muted-foreground mt-1">Classification Review</p>
        </div>

        {/* Navigation */}
        <div className="p-2 space-y-1 flex-1 overflow-y-auto">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">INTAKE PAGES</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../`}>Intake Status</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7 bg-primary/10" asChild>
            <Link href={`./`}>Classification Review</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../human-gate`}>Human Gate</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../locked-pack`}>Locked Pack</Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold">Classification Review</h1>
              <p className="text-sm text-muted-foreground">
                Session: {data.intake_session_id}
              </p>
            </div>
            <Button asChild>
              <Link href={`../human-gate`}>Proceed to Human Gate</Link>
            </Button>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Total Files</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{summary.total_files}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">High Confidence</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">
                  {summary.high_confidence_count}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Low Confidence</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-yellow-600">
                  {summary.low_confidence_count}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Unknown EP</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-600">
                  {summary.unknown_ep_count}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Auto Proceed Status */}
          <Card
            className={
              summary.auto_proceed_eligible
                ? "border-green-200 bg-green-50"
                : "border-yellow-200 bg-yellow-50"
            }
          >
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className="text-2xl">{summary.auto_proceed_eligible ? "✓" : "⚠"}</div>
                <div>
                  <div className="font-medium">
                    {summary.auto_proceed_eligible
                      ? "Auto-Proceed Eligible"
                      : "Human Review Required"}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {summary.auto_proceed_eligible
                      ? "All files have high confidence classifications"
                      : "Some files require human review before approval"}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Missing Documents */}
          {missing_required_documents.length > 0 && (
            <Card className="border-yellow-200">
              <CardHeader>
                <CardTitle className="text-base text-yellow-800">
                  Missing Required Documents
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {missing_required_documents.map((doc, i) => (
                    <div key={i} className="flex items-start gap-3 p-2 bg-yellow-50 rounded">
                      <Badge
                        variant="outline"
                        className="border-yellow-300 text-yellow-700 shrink-0"
                      >
                        {doc.ep}
                      </Badge>
                      <div className="flex-1">
                        <div className="text-sm font-medium">{doc.required_type}</div>
                        <div className="text-xs text-muted-foreground">{doc.description}</div>
                      </div>
                      <Badge
                        variant="outline"
                        className={`shrink-0 ${
                          doc.severity === "blocking"
                            ? "border-red-300 text-red-700"
                            : "border-yellow-300 text-yellow-700"
                        }`}
                      >
                        {doc.severity}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Classification Table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">File Classifications</CardTitle>
              <CardDescription>
                Evidence documents and their EP classifications
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {files.map((file) => (
                  <div
                    key={file.file_id}
                    className={`p-3 rounded border ${
                      file.requires_human_review
                        ? "bg-yellow-50 border-yellow-200"
                        : file.confidence && file.confidence >= 0.8
                        ? "bg-green-50 border-green-200"
                        : "bg-gray-50 border-gray-200"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant="outline" className="font-mono text-xs">
                            {file.file_id}
                          </Badge>
                          <Badge
                            variant="outline"
                            className={
                              file.final_type
                                ? "border-blue-300 text-blue-700"
                                : "border-gray-300 text-gray-500"
                            }
                          >
                            {file.final_type || "UNKNOWN"}
                          </Badge>
                          {file.final_ep && (
                            <Badge variant="outline" className="border-purple-300 text-purple-700">
                              {file.final_ep}
                            </Badge>
                          )}
                          {file.requires_human_review && (
                            <Badge variant="outline" className="border-yellow-300 text-yellow-700">
                              HUMAN REVIEW
                            </Badge>
                          )}
                        </div>
                        <div className="text-sm mt-1 truncate">{file.relative_path}</div>
                        {file.review_rationale && (
                          <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                            {file.review_rationale}
                          </div>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <div
                          className={`text-lg font-bold ${
                            file.confidence && file.confidence >= 0.8
                              ? "text-green-600"
                              : file.confidence && file.confidence >= 0.6
                              ? "text-yellow-600"
                              : "text-red-600"
                          }`}
                        >
                          {file.confidence != null ? `${(file.confidence * 100).toFixed(0)}%` : "—"}
                        </div>
                        <div className="text-[10px] text-muted-foreground">confidence</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
