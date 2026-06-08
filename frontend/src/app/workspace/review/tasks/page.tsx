"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { getBackendBaseURL } from "@/core/config";
import {
  ShieldCheckIcon,
  ArrowLeftIcon,
  CheckCircle2Icon,
  AlertTriangleIcon,
  XCircleIcon,
  ClockIcon,
  Loader2Icon,
  PlayIcon,
  UserCheckIcon,
} from "lucide-react";

interface RunItem {
  project_id: string;
  project_name: string;
  run_id: string;
  thread_id?: string;
  mode?: string;
  status: string;
  executed_steps?: string[];
  lane_statuses?: Record<string, string>;
  gate_statuses?: Record<string, string>;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

const _pendingCfg = { label: "未开始", icon: ClockIcon, color: "text-muted-foreground" };
const STATUS_CONFIG: Record<string, { label: string; icon: typeof CheckCircle2Icon; color: string }> = {
  completed: { label: "已完成", icon: CheckCircle2Icon, color: "text-green-600" },
  running: { label: "执行中", icon: Loader2Icon, color: "text-blue-600" },
  halted: { label: "已暂停", icon: AlertTriangleIcon, color: "text-yellow-600" },
  human_gate_pending: { label: "等待人审", icon: UserCheckIcon, color: "text-orange-600" },
  failed: { label: "失败", icon: XCircleIcon, color: "text-red-600" },
  pending: _pendingCfg,
};

export default function TasksPage() {
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTasks = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch all projects
      const projRes = await fetch(`${getBackendBaseURL()}/api/cer-review/projects`);
      if (!projRes.ok) throw new Error(projRes.statusText);
      const { projects } = await projRes.json();

      // For each project with a latest_run, fetch run detail
      const runItems: RunItem[] = [];
      for (const p of (projects ?? [])) {
        if (p.latest_run_id) {
          try {
            const runRes = await fetch(
              `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(p.project_id)}/run/${encodeURIComponent(p.latest_run_id)}`,
            );
            if (runRes.ok) {
              const detail = await runRes.json();
              runItems.push({
                project_id: p.project_id,
                project_name: p.project_name ?? p.project_id,
                run_id: p.latest_run_id,
                mode: detail.mode ?? "unknown",
                status: detail.status ?? p.latest_run_status ?? "unknown",
                lane_statuses: detail.lane_statuses ?? {},
                gate_statuses: detail.gate_statuses ?? {},
                started_at: detail.started_at,
              });
            } else {
              // Fallback: just show project-level status
              runItems.push({
                project_id: p.project_id,
                project_name: p.project_name ?? p.project_id,
                run_id: p.latest_run_id,
                status: p.latest_run_status ?? "unknown",
              });
            }
          } catch {
            runItems.push({
              project_id: p.project_id,
              project_name: p.project_name ?? p.project_id,
              run_id: p.latest_run_id,
              status: p.latest_run_status ?? "unknown",
            });
          }
        }
      }

      // Sort: running/halted first, then by started_at desc
      runItems.sort((a, b) => {
        const aActive = a.status === "running" || a.status === "halted";
        const bActive = b.status === "running" || b.status === "halted";
        if (aActive !== bActive) return aActive ? -1 : 1;
        return (b.started_at ?? "").localeCompare(a.started_at ?? "");
      });

      setRuns(runItems);
    } catch (e: any) {
      setError(e.message ?? "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
  }, []);

  const activeCount = runs.filter((r) => r.status === "running" || r.status === "halted" || r.status === "human_gate_pending").length;

  return (
    <div className="flex h-full">
      {/* ── left sidebar ── */}
      <div className="w-72 border-r flex flex-col bg-background">
        <div className="p-4 border-b">
          <Link href="/workspace/review/projects">
            <Button variant="ghost" size="sm" className="mb-2">
              <ArrowLeftIcon className="h-4 w-4 mr-1" />
              返回项目列表
            </Button>
          </Link>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <ShieldCheckIcon className="h-5 w-5" />
            运行中任务
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            {activeCount > 0 ? `${activeCount} 个活跃任务` : "无活跃任务"}
          </p>
        </div>

        <div className="p-2 border-b space-y-1">
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <Link href="/workspace/review/projects">📋 项目列表</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <Link href="/workspace/review/new">+ 新建评审</Link>
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground">
              {runs.length > 0 ? `全部任务 (${runs.length})` : "任务"}
            </span>
            <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={loadTasks}>
              刷新
            </Button>
          </div>

          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : runs.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              无运行记录
            </div>
          ) : (
            <div className="space-y-1">
              {runs.map((r) => {
                const cfg = STATUS_CONFIG[r.status] ?? _pendingCfg;
                const Icon = cfg.icon;
                return (
                  <Link
                    key={`${r.project_id}-${r.run_id}`}
                    href={`/workspace/review/projects/${encodeURIComponent(r.project_id)}/run/${encodeURIComponent(r.run_id)}`}
                    className="block p-3 rounded hover:bg-accent transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium truncate">{r.project_name}</span>
                      <Icon className={`h-4 w-4 ${cfg.color} ${r.status === "running" ? "animate-spin" : ""}`} />
                    </div>
                    <div className="flex items-center gap-1 mt-1">
                      <span className="text-[10px] text-muted-foreground">{r.project_id}</span>
                      <Badge variant="outline" className="text-[10px] px-1 py-0">
                        {cfg.label}
                      </Badge>
                    </div>
                    {r.lane_statuses && Object.keys(r.lane_statuses).length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-0.5">
                        {Object.entries(r.lane_statuses).slice(0, 4).map(([lane, status]) => (
                          <span
                            key={lane}
                            className={`text-[9px] px-1 rounded ${
                              status === "COMPLETE" ? "bg-green-100 text-green-700" :
                              status === "FLAGGED" ? "bg-yellow-100 text-yellow-700" :
                              "bg-muted text-muted-foreground"
                            }`}
                          >
                            {lane}
                          </span>
                        ))}
                      </div>
                    )}
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── main content ── */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-4xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold">运行中任务</h1>
              <p className="text-muted-foreground mt-1">
                所有评审项目的 Workflow 执行状态和进度
              </p>
            </div>
            <Button onClick={loadTasks} variant="outline" size="sm">
              刷新
            </Button>
          </div>

          {loading ? (
            <div className="space-y-4">
              <Skeleton className="h-48 w-full" />
              <Skeleton className="h-48 w-full" />
            </div>
          ) : error ? (
            <Card>
              <CardContent className="py-8 text-center">
                <XCircleIcon className="h-8 w-8 mx-auto mb-2 text-destructive" />
                <p className="text-sm text-destructive mb-4">{error}</p>
                <Button variant="outline" onClick={loadTasks}>重试</Button>
              </CardContent>
            </Card>
          ) : runs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground">
              <PlayIcon className="h-16 w-16 mb-4 opacity-20" />
              <h3 className="text-lg font-medium">暂无运行任务</h3>
              <p className="text-sm mt-1 max-w-md">
                创建评审项目并启动 Workflow 后，运行中的任务将显示在此处。
              </p>
              <Button className="mt-4" asChild>
                <Link href="/workspace/review/new">创建评审项目</Link>
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {runs.map((r) => {
                const cfg = STATUS_CONFIG[r.status] ?? _pendingCfg;
                const Icon = cfg.icon;
                return (
                  <Card key={`${r.project_id}-${r.run_id}`}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-sm flex items-center gap-2">
                          <Icon className={`h-4 w-4 ${cfg.color} ${r.status === "running" ? "animate-spin" : ""}`} />
                          {r.project_name}
                        </CardTitle>
                        <Badge variant="outline">
                          {cfg.label}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-3">
                        <div>
                          <span className="text-muted-foreground">Project ID</span>
                          <p className="font-mono">{r.project_id}</p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Run ID</span>
                          <p className="font-mono text-[10px]">{r.run_id}</p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Mode</span>
                          <p>{r.mode ?? "unknown"}</p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Started</span>
                          <p>{r.started_at ? new Date(r.started_at).toLocaleString() : "N/A"}</p>
                        </div>
                      </div>

                      {/* Lane statuses */}
                      {r.lane_statuses && Object.keys(r.lane_statuses).length > 0 && (
                        <div className="mb-3">
                          <span className="text-xs text-muted-foreground mb-1 block">Lane Status</span>
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(r.lane_statuses).map(([lane, status]) => (
                              <Badge
                                key={lane}
                                variant={status === "COMPLETE" ? "default" : status === "FLAGGED" ? "destructive" : "secondary"}
                                className="text-[10px]"
                              >
                                {lane}: {status}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Gate statuses */}
                      {r.gate_statuses && Object.keys(r.gate_statuses).length > 0 && (
                        <div className="mb-3">
                          <span className="text-xs text-muted-foreground mb-1 block">Gate Status</span>
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(r.gate_statuses).map(([gate, status]) => (
                              <Badge
                                key={gate}
                                variant={status === "PENDING" ? "outline" : status === "COMPLETE" ? "default" : "secondary"}
                                className="text-[10px]"
                              >
                                {gate}: {status}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      <Link
                        href={`/workspace/review/projects/${encodeURIComponent(r.project_id)}/run/${encodeURIComponent(r.run_id)}`}
                      >
                        <Button variant="outline" size="sm" className="text-xs">
                          查看详情
                        </Button>
                      </Link>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
