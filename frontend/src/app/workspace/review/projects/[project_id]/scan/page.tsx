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
  CheckCircle2Icon,
  AlertTriangleIcon,
  XCircleIcon,
  FileIcon,
  FolderOpenIcon,
  Loader2Icon,
} from "lucide-react";

interface ScannedFile {
  file_id: string;
  file_name: string;
  source_path: string;
  relative_path: string;
  extension: string;
  size_bytes: number;
  scan_status: string;
  warning?: string | null;
}

interface ClassificationCandidate {
  file_id: string;
  document_type: string;
  confidence: number;
  matched_keywords: string[];
  reason: string;
  requires_human_confirmation: boolean;
  file_name: string;
  relative_path: string;
  extension: string;
  size_bytes: number;
}

interface ScanResult {
  scan_id: string;
  project_id: string;
  project_name: string;
  source_package_path: string;
  scanned_files: ScannedFile[];
  classification_candidates: ClassificationCandidate[];
  status: string;
  warnings: string[];
  total_files_count: number;
  scanned_files_count: number;
}

function typeLabel(docType: string): string {
  const map: Record<string, string> = {
    cer: "CER",
    cep: "CEP",
    rmf: "RMF",
    fmea: "FMEA",
    ifu: "IFU",
    pmcf: "PMCF Plan",
    pms: "PMS Plan",
    clinical_evidence: "Clinical Evidence",
    risk_related: "Risk Related",
    equivalence: "Equivalence",
    sota: "SOTA / Literature",
    literature: "Literature",
    gspr: "GSPR",
    sscp: "SSCP",
    labels_packaging: "Labels & Packaging",
    td: "Technical Doc",
    biocompatibility: "Biocompatibility",
    performance: "Performance",
    reviewer_note: "Reviewer Note",
  };
  return map[docType] ?? docType.toUpperCase();
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

export default function ScanResultsPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = decodeURIComponent(params.project_id as string);
  const projectName = decodeURIComponent(searchParams.get("project_name") ?? projectId);

  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchScan = async () => {
      try {
        // Try to load from intake status
        const res = await fetch(
          `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/intake/status`,
        );
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        // Build scan result from status response
        if (data) {
          setScanResult(data as ScanResult);
        }
      } catch (e: any) {
        setError(e.message ?? "Failed to load scan results");
      } finally {
        setLoading(false);
      }
    };
    fetchScan();
  }, [projectId]);

  return (
    <div className="flex h-full">
      {/* ── left sidebar ── */}
      <div className="w-72 border-r flex flex-col bg-background">
        <div className="p-4 border-b">
          <Link href="/workspace/review/new">
            <Button variant="ghost" size="sm" className="mb-2">
              <ArrowLeftIcon className="h-4 w-4 mr-1" />
              返回新建
            </Button>
          </Link>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <FolderOpenIcon className="h-5 w-5" />
            文件扫描
          </h2>
          <p className="text-xs text-muted-foreground mt-1 truncate">
            {projectName}
          </p>
        </div>

        <div className="p-3 border-b text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Project ID</span>
            <span className="font-mono">{projectId}</span>
          </div>
        </div>

        <ScrollArea className="flex-1 p-3">
          {!loading && scanResult?.scanned_files && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                已发现 {scanResult.scanned_files.length} 个文件
              </p>
              {scanResult.warnings?.map((w, i) => (
                <div key={i} className="flex items-start gap-1 text-xs text-yellow-600">
                  <AlertTriangleIcon className="h-3 w-3 mt-0.5 shrink-0" />
                  <span className="break-all">{w}</span>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>

      {/* ── main content ── */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-4xl">
          <h1 className="text-2xl font-bold mb-2">文件扫描结果</h1>
          <p className="text-muted-foreground mb-6">
            项目: {projectName}
          </p>

          {loading ? (
            <div className="space-y-4">
              <Skeleton className="h-8 w-64" />
              <Skeleton className="h-64 w-full" />
            </div>
          ) : error ? (
            <Card>
              <CardContent className="py-8 text-center">
                <XCircleIcon className="h-8 w-8 mx-auto mb-2 text-destructive" />
                <p className="text-sm text-destructive mb-4">{error}</p>
                <Button variant="outline" onClick={() => window.location.reload()}>
                  重试
                </Button>
              </CardContent>
            </Card>
          ) : scanResult ? (
            <div className="space-y-6">
              {/* Summary card */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">扫描概要</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">源路径</span>
                      <p className="font-mono text-xs mt-0.5 break-all">
                        {scanResult.source_package_path ?? "N/A"}
                      </p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">总文件数</span>
                      <p>{scanResult.total_files_count ?? scanResult.scanned_files?.length ?? 0}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">状态</span>
                      <p>
                        <Badge variant={scanResult.status === "ok" ? "default" : "secondary"}>
                          {scanResult.status ?? "unknown"}
                        </Badge>
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Classification table */}
              {scanResult.classification_candidates?.length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">
                      文件分类 ({scanResult.classification_candidates.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-xs text-muted-foreground">
                            <th className="py-2 pr-4">文件名</th>
                            <th className="py-2 pr-4">类型推断</th>
                            <th className="py-2 pr-4">置信度</th>
                            <th className="py-2 pr-4">路径</th>
                            <th className="py-2">确认</th>
                          </tr>
                        </thead>
                        <tbody>
                          {scanResult.classification_candidates.map((c) => (
                            <tr key={c.file_id} className="border-b last:border-0">
                              <td className="py-2 pr-4">
                                <div className="flex items-center gap-1">
                                  <FileIcon className="h-3 w-3 text-muted-foreground" />
                                  <span className="font-mono text-xs">{c.file_name}</span>
                                </div>
                                <span className="text-[10px] text-muted-foreground">
                                  {formatBytes(c.size_bytes ?? 0)}
                                </span>
                              </td>
                              <td className="py-2 pr-4">
                                <Badge variant="outline" className="text-[10px]">
                                  {typeLabel(c.document_type)}
                                </Badge>
                              </td>
                              <td className="py-2 pr-4">
                                <div className="flex items-center gap-1">
                                  {c.confidence >= 0.8 ? (
                                    <CheckCircle2Icon className="h-3 w-3 text-green-600" />
                                  ) : c.confidence >= 0.5 ? (
                                    <AlertTriangleIcon className="h-3 w-3 text-yellow-600" />
                                  ) : (
                                    <XCircleIcon className="h-3 w-3 text-red-600" />
                                  )}
                                  <span>{(c.confidence * 100).toFixed(0)}%</span>
                                </div>
                              </td>
                              <td className="py-2 pr-4">
                                <span className="font-mono text-[10px] text-muted-foreground break-all">
                                  {c.relative_path}
                                </span>
                              </td>
                              <td className="py-2">
                                {c.requires_human_confirmation ? (
                                  <Badge variant="secondary" className="text-[10px]">需确认</Badge>
                                ) : (
                                  <Badge variant="default" className="text-[10px]">已识别</Badge>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* File list fallback when no classification candidates */}
              {(!scanResult.classification_candidates || scanResult.classification_candidates.length === 0) &&
                scanResult.scanned_files?.length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">
                      已扫描文件 ({scanResult.scanned_files.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {scanResult.scanned_files.map((f) => (
                        <div
                          key={f.file_id}
                          className="flex items-center justify-between p-2 rounded border text-sm"
                        >
                          <div className="flex items-center gap-2">
                            <FileIcon className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <span className="font-mono text-xs">{f.file_name}</span>
                              <p className="text-[10px] text-muted-foreground font-mono">
                                {f.relative_path}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">
                              {formatBytes(f.size_bytes)}
                            </span>
                            {f.scan_status === "ok" ? (
                              <CheckCircle2Icon className="h-4 w-4 text-green-600" />
                            ) : f.scan_status === "flagged" ? (
                              <AlertTriangleIcon className="h-4 w-4 text-yellow-600" />
                            ) : (
                              <XCircleIcon className="h-4 w-4 text-red-600" />
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Next action */}
              <div className="flex gap-3">
                <Button variant="outline" asChild>
                  <Link href="/workspace/review/new">重新扫描</Link>
                </Button>
                <Button asChild>
                  <Link
                    href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/upload/start-run`}
                  >
                    确认并启动评审 Workflow
                  </Link>
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
