"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
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
import { cerReviewFetch } from "@/core/cer_auth/api";
import { getBackendBaseURL } from "@/core/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ReportSourceInventorySummary {
  total_sources: number;
  true_source: number;
  partial_source: number;
  source_unavailable: number;
}

interface ReportLimitationsSummary {
  total_limitations: number;
  rmf_source_count: number;
  equivalence_count: number;
  post_market_count: number;
}

interface ReportFinding {
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

interface ReportFindingsSummary {
  total: number;
  actionable: number;
  human_decision_required: number;
}

interface ReportNonClaim {
  claim_type: string;
  non_claim: string;
  reason: string;
}

interface ReportResponse {
  report_type: string;
  project_id: string;
  workflow_run_id: string;
  mode: string;
  source_inventory_summary: ReportSourceInventorySummary;
  limitations_summary: ReportLimitationsSummary;
  findings: ReportFinding[];
  findings_summary: ReportFindingsSummary;
  non_claims: ReportNonClaim[];
  boundaries: Record<string, boolean>;
  next_state: string;
  non_claim_summary: string;
  generated_at: string;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function getAvailableSourceReport(projectId: string, workflowRunId?: string): Promise<ReportResponse> {
  const params = new URLSearchParams({ project_id: projectId });
  if (workflowRunId) params.set("workflow_run_id", workflowRunId);
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/workflows/available-source/report?${params.toString()}`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function SeverityBadge({ severity }: { severity: string | null }) {
  if (!severity) return null;
  const variants: Record<string, string> = {
    HIGH: "bg-red-100 text-red-800",
    MEDIUM: "bg-yellow-100 text-yellow-800",
    LOW: "bg-blue-100 text-blue-800",
  };
  return <Badge className={variants[severity] ?? "bg-gray-100"}>{severity}</Badge>;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ReportPage() {
  const params = useParams();
  const projectId = decodeURIComponent(String(params.project_id));

  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAvailableSourceReport(projectId);
      setReport(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(`Failed to load report: ${msg}`);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void loadReport();
  }, [loadReport]);

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
          <p className="text-xs text-muted-foreground mt-1">CER Report</p>
        </div>

        {/* Navigation */}
        <div className="p-2 space-y-1 flex-1 overflow-y-auto">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">INTAKE</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../intake`}>Intake Status</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../intake/classification`}>Classification</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../intake/human-gate`}>Human Gate</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../intake/locked-pack`}>Locked Pack</Link>
          </Button>
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1 mt-3">CER REVIEW</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../upload`}>Upload Evidence</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../gate-1`}>G1 Route Review</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../gate-3`}>G3 BRR Review</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../artifacts`}>Artifacts</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7 bg-primary/10" asChild>
            <Link href={`./`}>Report</Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Header */}
          <div>
            <h1 className="text-xl font-bold">CER Reviewer Working Report</h1>
            <p className="text-sm text-muted-foreground">
              Source-bounded CER/RMF review report. This is NOT an official CEAR.
            </p>
          </div>

          {/* Non-claims banner */}
          <Card className="border-red-200 bg-red-50/50">
            <CardContent className="pt-4">
              <div className="flex items-start gap-3">
                <span className="text-2xl">⚠️</span>
                <div className="space-y-1 text-sm">
                  <p className="font-semibold text-red-800">Important — Not an Official Document</p>
                  <ul className="space-y-0.5 text-xs text-red-700 list-disc list-inside">
                    <li>This is NOT an official CEAR</li>
                    <li>No final regulatory decision has been made</li>
                    <li>Not production ready</li>
                    <li>Not submission-ready</li>
                    <li>No approved/active/reusable asset has been created</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>

          {loading && (
            <div className="flex items-center justify-center py-12">
              <p className="text-muted-foreground">Loading report...</p>
            </div>
          )}

          {error && (
            <Card className="border-red-300 bg-red-50">
              <CardContent className="pt-4">
                <div className="text-sm text-red-700">
                  <span className="font-semibold">Error loading report:</span> {error}
                </div>
                <Button variant="outline" size="sm" className="mt-3" onClick={loadReport}>
                  Retry
                </Button>
              </CardContent>
            </Card>
          )}

          {report && (
            <div className="space-y-6">
              {/* Report Meta */}
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Badge variant="outline">{report.report_type}</Badge>
                      <Badge className="bg-purple-100 text-purple-800 font-mono">{report.mode}</Badge>
                      <span className="text-xs text-muted-foreground font-mono">{report.workflow_run_id}</span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Generated: {new Date(report.generated_at).toLocaleString()}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Summary Cards */}
              <div className="grid grid-cols-3 gap-4">
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold">{report.source_inventory_summary.total_sources}</div>
                    <div className="text-xs text-muted-foreground">Total Sources</div>
                    <div className="flex gap-2 mt-2 text-xs">
                      <span className="text-green-600">{report.source_inventory_summary.true_source} true</span>
                      <span className="text-yellow-600">{report.source_inventory_summary.partial_source} partial</span>
                      <span className="text-red-600">{report.source_inventory_summary.source_unavailable} unavailable</span>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold">{report.limitations_summary.total_limitations}</div>
                    <div className="text-xs text-muted-foreground">Known Source Limitations</div>
                    <div className="flex gap-2 mt-2 text-xs">
                      <span>{report.limitations_summary.rmf_source_count} RMF</span>
                      <span>{report.limitations_summary.equivalence_count} EQ</span>
                      <span>{report.limitations_summary.post_market_count} PM</span>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold">{report.findings_summary.total}</div>
                    <div className="text-xs text-muted-foreground">Reviewer Findings</div>
                    <div className="flex gap-2 mt-2 text-xs">
                      <span>{report.findings_summary.actionable} actionable</span>
                      <span>{report.findings_summary.human_decision_required} need human</span>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Report Content Tabs */}
              <Tabs defaultValue="summary">
                <TabsList>
                  <TabsTrigger value="summary">Summary</TabsTrigger>
                  <TabsTrigger value="findings">Findings ({report.findings.length})</TabsTrigger>
                  <TabsTrigger value="non-claims">Non-Claims</TabsTrigger>
                  <TabsTrigger value="raw">Raw JSON</TabsTrigger>
                </TabsList>

                {/* Summary Tab */}
                <TabsContent value="summary">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">Report Summary</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div>
                        <h3 className="text-sm font-semibold mb-2">Source Inventory Summary</h3>
                        <div className="grid grid-cols-4 gap-2 text-xs">
                          <div className="p-2 border rounded">
                            <div className="font-bold">{report.source_inventory_summary.total_sources}</div>
                            <div className="text-muted-foreground">Total Sources</div>
                          </div>
                          <div className="p-2 border rounded bg-green-50">
                            <div className="font-bold text-green-700">{report.source_inventory_summary.true_source}</div>
                            <div className="text-muted-foreground">True Source</div>
                          </div>
                          <div className="p-2 border rounded bg-yellow-50">
                            <div className="font-bold text-yellow-700">{report.source_inventory_summary.partial_source}</div>
                            <div className="text-muted-foreground">Partial Source</div>
                          </div>
                          <div className="p-2 border rounded bg-red-50">
                            <div className="font-bold text-red-700">{report.source_inventory_summary.source_unavailable}</div>
                            <div className="text-muted-foreground">Unavailable</div>
                          </div>
                        </div>
                      </div>

                      <div>
                        <h3 className="text-sm font-semibold mb-2">Source Limitation Summary</h3>
                        <div className="grid grid-cols-4 gap-2 text-xs">
                          <div className="p-2 border rounded">
                            <div className="font-bold">{report.limitations_summary.total_limitations}</div>
                            <div className="text-muted-foreground">Total Limitations</div>
                          </div>
                          <div className="p-2 border rounded">
                            <div className="font-bold">{report.limitations_summary.rmf_source_count}</div>
                            <div className="text-muted-foreground">RMF Source</div>
                          </div>
                          <div className="p-2 border rounded">
                            <div className="font-bold">{report.limitations_summary.equivalence_count}</div>
                            <div className="text-muted-foreground">Equivalence</div>
                          </div>
                          <div className="p-2 border rounded">
                            <div className="font-bold">{report.limitations_summary.post_market_count}</div>
                            <div className="text-muted-foreground">Post-Market</div>
                          </div>
                        </div>
                      </div>

                      <div>
                        <h3 className="text-sm font-semibold mb-2">Next State</h3>
                        <Badge>{report.next_state}</Badge>
                      </div>

                      <div>
                        <h3 className="text-sm font-semibold mb-2">Boundaries Applied</h3>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(report.boundaries).map(([key, value]) => (
                            <div key={key} className="text-xs">
                              <span className="text-muted-foreground">{key}:</span>{" "}
                              <span className={value ? "text-red-600 font-semibold" : "text-green-600"}>
                                {value ? "TRUE" : "false"}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>

                {/* Findings Tab */}
                <TabsContent value="findings">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Reviewer Findings</CardTitle>
                      <CardDescription>
                        {report.findings_summary.actionable} actionable · {report.findings_summary.human_decision_required} require human decision
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      {report.findings.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No findings generated</p>
                      ) : (
                        <div className="space-y-3">
                          {report.findings.map(item => (
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

                {/* Non-Claims Tab */}
                <TabsContent value="non-claims">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Non-Claims</CardTitle>
                      <CardDescription>These claims are explicitly NOT made by this workflow</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {report.non_claims.map((item, i) => (
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

                {/* Raw JSON Tab */}
                <TabsContent value="raw">
                  <Card>
                    <CardContent className="pt-4">
                      <div className="flex justify-end mb-3">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            void navigator.clipboard.writeText(JSON.stringify(report, null, 2));
                            void toast.success("Report JSON copied to clipboard");
                          }}
                        >
                          Copy JSON
                        </Button>
                      </div>
                      <pre className="text-xs bg-muted p-4 rounded overflow-auto max-h-96">
                        {JSON.stringify(report, null, 2)}
                      </pre>
                    </CardContent>
                  </Card>
                </TabsContent>
              </Tabs>

              {/* Export Section */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Export</CardTitle>
                </CardHeader>
                <CardContent className="flex gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      void navigator.clipboard.writeText(JSON.stringify(report, null, 2));
                      void toast.success("Report JSON copied to clipboard");
                    }}
                  >
                    Copy JSON
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `cer-review-report-${projectId}-${report.workflow_run_id}.json`;
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                  >
                    Download JSON
                  </Button>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
