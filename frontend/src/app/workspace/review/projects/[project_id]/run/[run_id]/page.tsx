"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
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
  ClockIcon,
  Loader2Icon,
  FileTextIcon,
  EyeIcon,
  SearchIcon,
} from "lucide-react";

interface RunDetail {
  run_id: string;
  thread_id?: string;
  status: string;
  mode?: string;
  started_at?: string;
  completed_at?: string;
  lane_statuses?: Record<string, string>;
  gate_statuses?: Record<string, string>;
  ledger_summary?: { entries?: any[]; total?: number };
  findings_summary?: any[];
  state_log_summary?: any[];
  executed_steps?: string[];
}

const CER_D1_STEPS = [
  { step_id: "cer_intake", label: "文档接收与解析", agent: "cer-intake-reviewer" },
  { step_id: "cer_structure_compliance", label: "结构合规", agent: "cer-structure-compliance-reviewer" },
  { step_id: "cer_intended_purpose", label: "预期用途审查", agent: "cer-intended-purpose-reviewer" },
  { step_id: "cer_cep_methodology", label: "CEP 方法学", agent: "cer-cep-methodology-reviewer" },
  { step_id: "cer_clinical_evidence_panel", label: "临床证据面板", agent: "cer-clinical-evidence-panel-reviewer" },
  { step_id: "cer_ifu_sscp_label", label: "IFU/SSCP/标签", agent: "cer-ifu-sscp-label-reviewer" },
  { step_id: "cer_qa_gate", label: "QA Gate", agent: "cer-qa-gate-reviewer" },
  { step_id: "cer_cear_style_finding_formatter", label: "Finding 格式化", agent: "cer-cear-formatter-reviewer" },
  { step_id: "cer_human_boundary", label: "Human Boundary", agent: "cer-human-boundary-reviewer" },
  { step_id: "cer_gate_closure", label: "Gate 关闭", agent: "cer-gate-closure-reviewer" },
];

function stepStatus(stepId: string, executed: string[], halted: boolean): "completed" | "running" | "halted" | "pending" {
  const idx = executed.indexOf(stepId);
  if (idx === -1) return "pending";
  if (idx === executed.length - 1 && halted) return "halted";
  if (idx === executed.length - 1) return "running";
  return "completed";
}

export default function RunDetailPage() {
  const params = useParams();
  const projectId = decodeURIComponent(params.project_id as string);
  const runId = decodeURIComponent(params.run_id as string);

  const [run, setRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchRun = async () => {
    try {
      const res = await fetch(
        `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/run/${encodeURIComponent(runId)}`,
      );
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();
      setRun(data);

      // Auto-refresh if still running
      if (data.status === "running" || data.status === "halted") {
        setAutoRefresh(true);
      } else {
        setAutoRefresh(false);
      }
    } catch (e: any) {
      setError(e.message ?? "Failed to load run detail");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRun();
  }, [projectId, runId]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchRun, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, projectId, runId]);

  const executed = run?.executed_steps ?? Object.keys(run?.lane_statuses ?? {});
  const halted = run?.status === "halted" || run?.status === "human_gate_pending";
  const steps = CER_D1_STEPS;

  return (
    <div className="flex h-full">
      {/* ── left sidebar ── */}
      <div className="w-72 border-r flex flex-col bg-background">
        <div className="p-4 border-b">
          <Link href="/workspace/review/tasks">
            <Button variant="ghost" size="sm" className="mb-2">
              <ArrowLeftIcon className="h-4 w-4 mr-1" />
              返回任务列表
            </Button>
          </Link>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <EyeIcon className="h-5 w-5" />
            Run 详情
          </h2>
          <p className="text-xs text-muted-foreground mt-1 truncate">{projectId}</p>
        </div>

        <div className="p-3 border-b text-xs space-y-1">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Run ID</span>
            <span className="font-mono">{runId}</span>
          </div>
          {run?.thread_id && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Thread</span>
              <span className="font-mono text-[10px]">{run.thread_id}</span>
            </div>
          )}
          {run?.status && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Status</span>
              <Badge variant={run.status === "completed" ? "default" : "outline"} className="text-[10px]">
                {run.status}
              </Badge>
            </div>
          )}
        </div>

        <ScrollArea className="flex-1 p-2">
          <p className="text-xs font-medium text-muted-foreground mb-2">Workflow Steps</p>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <div className="space-y-1">
              {steps.map((s) => {
                const status = stepStatus(s.step_id, executed, halted);
                return (
                  <div
                    key={s.step_id}
                    className={`p-2 rounded text-xs transition-colors ${
                      status === "completed" ? "bg-green-50" :
                      status === "running" ? "bg-blue-50" :
                      status === "halted" ? "bg-orange-50" :
                      "bg-muted/30"
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      {status === "completed" && <CheckCircle2Icon className="h-3 w-3 text-green-600" />}
                      {status === "running" && <Loader2Icon className="h-3 w-3 text-blue-600 animate-spin" />}
                      {status === "halted" && <AlertTriangleIcon className="h-3 w-3 text-orange-600" />}
                      {status === "pending" && <ClockIcon className="h-3 w-3 text-muted-foreground" />}
                      <span className={`font-medium ${
                        status === "completed" ? "text-green-700" :
                        status === "halted" ? "text-orange-700" :
                        ""
                      }`}>
                        {s.label}
                      </span>
                    </div>
                    <div className="mt-0.5 text-[10px] text-muted-foreground ml-4">
                      <span className="font-mono">{s.step_id}</span>
                      <span className="mx-1">·</span>
                      <span>{s.agent}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </div>

      {/* ── main content ── */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-4xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold">Run 详情</h1>
              <p className="text-muted-foreground mt-1">{projectId} / {runId}</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={fetchRun}>
                刷新
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}`}>
                  完整治理视图
                </Link>
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="space-y-4">
              <Skeleton className="h-64 w-full" />
            </div>
          ) : error ? (
            <Card>
              <CardContent className="py-8 text-center">
                <XCircleIcon className="h-8 w-8 mx-auto mb-2 text-destructive" />
                <p className="text-sm text-destructive mb-4">{error}</p>
                <Button variant="outline" onClick={fetchRun}>重试</Button>
              </CardContent>
            </Card>
          ) : run ? (
            <div className="space-y-6">
              {/* Run summary */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">运行概要</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Status</span>
                      <p><Badge>{run.status}</Badge></p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Mode</span>
                      <p>{run.mode ?? "N/A"}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Started</span>
                      <p className="text-xs">{run.started_at ? new Date(run.started_at).toLocaleString() : "N/A"}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Completed</span>
                      <p className="text-xs">{run.completed_at ? new Date(run.completed_at).toLocaleString() : "N/A"}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Workflow progress */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Workflow 步骤进度</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-0">
                    {steps.map((s, i) => {
                      const status = stepStatus(s.step_id, executed, halted);
                      return (
                        <div key={s.step_id} className="flex items-start gap-3 py-2 border-b last:border-0">
                          <div className="mt-0.5">
                            {status === "completed" && <CheckCircle2Icon className="h-5 w-5 text-green-600" />}
                            {status === "running" && <Loader2Icon className="h-5 w-5 text-blue-600 animate-spin" />}
                            {status === "halted" && <AlertTriangleIcon className="h-5 w-5 text-orange-600" />}
                            {status === "pending" && <ClockIcon className="h-5 w-5 text-muted-foreground" />}
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{s.label}</span>
                              <Badge variant="outline" className="text-[10px]">
                                {status === "completed" ? "已完成" :
                                 status === "running" ? "执行中" :
                                 status === "halted" ? "已暂停" : "未开始"}
                              </Badge>
                            </div>
                            <div className="text-xs text-muted-foreground mt-0.5">
                              <span className="font-mono">{s.step_id}</span>
                              <span className="mx-1">→</span>
                              <span>{s.agent}</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Lane statuses */}
              {run.lane_statuses && Object.keys(run.lane_statuses).length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Lane 状态</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(run.lane_statuses).map(([lane, status]) => (
                        <div key={lane} className="flex items-center justify-between p-2 rounded border text-sm">
                          <span className="font-mono text-xs">{lane}</span>
                          <Badge variant={status === "COMPLETE" ? "default" : status === "FLAGGED" ? "destructive" : "secondary"}>
                            {status}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Findings summary */}
              {run.findings_summary && run.findings_summary.length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Findings ({run.findings_summary.length})</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {run.findings_summary.slice(0, 10).map((f: any, i: number) => (
                        <div key={i} className="p-2 rounded border text-xs">
                          <div className="font-medium">{f.item ?? f.label ?? `Finding #${i + 1}`}</div>
                          {f.severity && (
                            <Badge variant="outline" className="text-[10px] mt-1">
                              {f.severity}
                            </Badge>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Quick links */}
              <div className="flex gap-2">
                <Button variant="outline" size="sm" asChild>
                  <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}`}>
                    完整项目治理
                  </Link>
                </Button>
                <Button variant="outline" size="sm" asChild>
                  <Link href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/artifacts?run_id=${encodeURIComponent(runId)}`}>
                    <FileTextIcon className="h-3 w-3 mr-1" />
                    Artifacts
                  </Link>
                </Button>
                <Button variant="outline" size="sm" asChild>
                  <Link href={`/workspace/review/projects/${encodeURIComponent(projectId)}/evidence?run_id=${encodeURIComponent(runId)}`}>
                    <SearchIcon className="h-3 w-3 mr-1" />
                    Evidence
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
