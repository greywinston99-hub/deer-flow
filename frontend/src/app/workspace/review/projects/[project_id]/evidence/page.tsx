"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getBackendBaseURL } from "@/core/config";
import {
  ArrowLeftIcon,
  FileTextIcon,
  FolderOpenIcon,
  SearchIcon,
  ExternalLinkIcon,
  ClockIcon,
  CheckCircle2Icon,
  AlertTriangleIcon,
} from "lucide-react";

interface FindingItem {
  item?: string;
  label?: string;
  finding_type?: string;
  severity?: string;
  source_ref?: string;
  mismatch_description?: string;
}

interface ArtifactItem {
  path: string;
  artifact_name: string;
  lane?: string | null;
  object_type?: string | null;
  has_flags?: boolean;
  size_bytes: number;
  modified_at?: string;
}

interface RunDetailData {
  run_id: string;
  status?: string;
  findings_summary?: FindingItem[];
  lane_statuses?: Record<string, string>;
  gate_statuses?: Record<string, string>;
}

export default function EvidencePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = decodeURIComponent(params.project_id as string);
  const runId = searchParams.get("run_id") ?? "";

  const [run, setRun] = useState<RunDetailData | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFinding, setSelectedFinding] = useState<number | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        if (!runId) {
          // Fetch latest run for project
          const projRes = await fetch(
            `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/runs`,
          );
          if (projRes.ok) {
            const { runs } = await projRes.json();
            const latest = runs?.[0];
            if (latest) {
              const runRes = await fetch(
                `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/run/${encodeURIComponent(latest.run_id)}`,
              );
              if (runRes.ok) setRun(await runRes.json());
            }
          }
        } else {
          const runRes = await fetch(
            `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/run/${encodeURIComponent(runId)}`,
          );
          if (runRes.ok) setRun(await runRes.json());
        }

        // Fetch artifacts
        const artUrl = new URL(
          `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/artifacts`,
          window.location.origin,
        );
        if (runId) artUrl.searchParams.set("run_id", runId);
        const artRes = await fetch(artUrl.toString());
        if (artRes.ok) {
          const data = await artRes.json();
          setArtifacts(data.artifacts ?? []);
        }
      } catch (e: any) {
        setError(e.message ?? "Failed to load evidence data");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [projectId, runId]);

  const findings = run?.findings_summary ?? [];
  const selected = selectedFinding !== null ? findings[selectedFinding] : null;

  const relatedArtifacts = selected
    ? artifacts.filter((a) => {
        const ref = selected.source_ref ?? selected.item ?? "";
        return (
          a.artifact_name?.toLowerCase().includes((selected.item ?? "").toLowerCase()) ||
          a.path?.toLowerCase().includes((selected.item ?? "").slice(0, 10).toLowerCase()) ||
          a.object_type?.toLowerCase().includes((selected.finding_type ?? "").toLowerCase())
        );
      })
    : [];

  return (
    <div className="flex h-full">
      {/* ── left sidebar ── */}
      <div className="w-72 border-r flex flex-col bg-background">
        <div className="p-4 border-b">
          <Link href={`/workspace/review/projects/${encodeURIComponent(projectId)}/run/${encodeURIComponent(runId || "latest")}`}>
            <Button variant="ghost" size="sm" className="mb-2">
              <ArrowLeftIcon className="h-4 w-4 mr-1" />
              返回 Run 详情
            </Button>
          </Link>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <SearchIcon className="h-5 w-5" />
            Evidence
          </h2>
          <p className="text-xs text-muted-foreground mt-1 truncate">{projectId}</p>
        </div>

        <div className="p-3 border-b text-xs text-muted-foreground">
          {findings.length > 0
            ? `${findings.length} findings · ${artifacts.length} artifacts`
            : loading ? "加载中..." : "无数据"}
        </div>

        <ScrollArea className="flex-1 p-2">
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : findings.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              未找到 findings
            </div>
          ) : (
            <div className="space-y-1">
              {findings.map((f, i) => (
                <button
                  key={i}
                  className={`w-full text-left p-2 rounded text-xs transition-colors ${
                    selectedFinding === i ? "bg-accent" : "hover:bg-accent/50"
                  }`}
                  onClick={() => setSelectedFinding(i)}
                >
                  <span className="font-medium line-clamp-2">
                    {f.item ?? f.label ?? `Finding #${i + 1}`}
                  </span>
                  <div className="flex items-center gap-1 mt-0.5">
                    {f.severity && (
                      <Badge variant="outline" className="text-[10px] px-1 py-0">
                        {f.severity}
                      </Badge>
                    )}
                    {f.finding_type && (
                      <Badge variant="secondary" className="text-[10px] px-1 py-0">
                        {f.finding_type}
                      </Badge>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>

      {/* ── main content ── */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-3xl">
          <h1 className="text-2xl font-bold mb-2">Evidence / Source 追溯</h1>
          <p className="text-muted-foreground mb-6">
            点击左侧 finding 查看关联的 evidence item、artifact、source file 和 source location。
          </p>

          {loading ? (
            <div className="space-y-4">
              <Skeleton className="h-48 w-full" />
            </div>
          ) : error ? (
            <Card>
              <CardContent className="py-8 text-center">
                <AlertTriangleIcon className="h-8 w-8 mx-auto mb-2 text-destructive" />
                <p className="text-sm text-destructive mb-4">{error}</p>
              </CardContent>
            </Card>
          ) : !selected ? (
            <div className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground">
              <SearchIcon className="h-16 w-16 mb-4 opacity-20" />
              <h3 className="text-lg font-medium">选择一个 Finding</h3>
              <p className="text-sm mt-1 max-w-md">
                从左侧列表中选择一个 finding 以查看其关联的 evidence item、artifact 路径和 source reference。
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Finding detail */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <FileTextIcon className="h-4 w-4" />
                    Finding
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div>
                    <span className="text-muted-foreground">Item</span>
                    <p className="font-medium">{selected.item ?? selected.label ?? "N/A"}</p>
                  </div>
                  {selected.mismatch_description && (
                    <div>
                      <span className="text-muted-foreground">Description</span>
                      <p className="text-xs mt-0.5">{selected.mismatch_description}</p>
                    </div>
                  )}
                  <div className="grid grid-cols-3 gap-4">
                    {selected.severity && (
                      <div>
                        <span className="text-muted-foreground">Severity</span>
                        <p><Badge variant="outline">{selected.severity}</Badge></p>
                      </div>
                    )}
                    {selected.finding_type && (
                      <div>
                        <span className="text-muted-foreground">Type</span>
                        <p><Badge variant="secondary">{selected.finding_type}</Badge></p>
                      </div>
                    )}
                    <div>
                      <span className="text-muted-foreground">Finding #</span>
                      <p className="font-mono text-xs">{selectedFinding !== null ? selectedFinding + 1 : "N/A"}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Source reference */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <ExternalLinkIcon className="h-4 w-4" />
                    Source Reference
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {selected.source_ref ? (
                    <div className="space-y-2">
                      <p className="font-mono text-xs break-all">{selected.source_ref}</p>
                      <div className="text-xs text-muted-foreground">
                        <span className="font-medium">Source Location Granularity: </span>
                        <Badge variant="outline" className="text-[10px]">
                          {selected.source_ref.includes("Section") ? "Section-level" :
                           selected.source_ref.includes("Line") ? "Line-level" :
                           selected.source_ref.includes("vs") ? "Document-level (CER vs Standard)" :
                           "Document-level"}
                        </Badge>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      此 finding 没有显式 source_ref。
                      <span className="block text-xs mt-1">
                        Source location granularity: UNKNOWN — finding lacks explicit source binding.
                      </span>
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Related artifacts */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <FolderOpenIcon className="h-4 w-4" />
                    Related Artifacts
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {relatedArtifacts.length > 0 ? (
                    <div className="space-y-2">
                      {relatedArtifacts.map((a) => (
                        <div key={a.path} className="p-2 rounded border text-xs">
                          <div className="flex items-center justify-between">
                            <span className="font-mono font-medium truncate">{a.artifact_name}</span>
                            <div className="flex items-center gap-1 shrink-0">
                              {a.has_flags && <AlertTriangleIcon className="h-3 w-3 text-yellow-600" />}
                              <span className="text-muted-foreground">
                                {(a.size_bytes / 1024).toFixed(1)} KB
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            {a.lane && <Badge variant="outline" className="text-[10px]">{a.lane}</Badge>}
                            {a.object_type && <Badge variant="secondary" className="text-[10px]">{a.object_type}</Badge>}
                            <span className="text-[10px] text-muted-foreground font-mono truncate">{a.path}</span>
                          </div>
                          {a.modified_at && (
                            <div className="flex items-center gap-1 mt-1 text-[10px] text-muted-foreground">
                              <ClockIcon className="h-3 w-3" />
                              {new Date(a.modified_at).toLocaleString()}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      未找到与此 finding 直接关联的 artifact。
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* All artifacts cache */}
              {artifacts.length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">
                      All Artifacts ({artifacts.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-1 max-h-64 overflow-y-auto">
                      {artifacts.map((a) => (
                        <div key={a.path} className="flex items-center justify-between p-1.5 rounded text-xs hover:bg-accent">
                          <span className="font-mono truncate">{a.artifact_name}</span>
                          <div className="flex items-center gap-2 shrink-0">
                            {a.lane && <span className="text-[10px] text-muted-foreground">{a.lane}</span>}
                            <Link
                              href={`${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/artifacts/${encodeURIComponent(a.path)}`}
                              target="_blank"
                            >
                              <ExternalLinkIcon className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                            </Link>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Schema / Evidence summary */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Evidence Context</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Project</span>
                      <p className="font-mono text-xs">{projectId}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Run</span>
                      <p className="font-mono text-xs">{runId || run?.run_id || "N/A"}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Findings</span>
                      <p>{findings.length}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Artifacts</span>
                      <p>{artifacts.length}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Run Status</span>
                      <p><Badge variant="outline">{run?.status ?? "unknown"}</Badge></p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Source Granularity</span>
                      <p className="text-xs text-muted-foreground">
                        Document-level (current minimum)
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
