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
  AlertTriangleIcon,
  UserCheckIcon,
  ClockIcon,
  CheckCircle2Icon,
} from "lucide-react";

interface GateItem {
  project_id: string;
  project_name: string;
  run_id: string;
  gate_id: string;
  gate_label: string;
  gate_type: "G1" | "G3" | "INTAKE" | "RMF";
  status: string;
  priority: "high" | "medium";
  last_updated?: string;
}

export default function HumanGatePage() {
  const [items, setItems] = useState<GateItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadGates = async () => {
    setLoading(true);
    setError(null);
    try {
      const projRes = await fetch(`${getBackendBaseURL()}/api/cer-review/projects`);
      if (!projRes.ok) throw new Error(projRes.statusText);
      const { projects } = await projRes.json();

      const gateItems: GateItem[] = [];
      for (const p of (projects ?? [])) {
        if (!p.latest_run_id) continue;
        try {
          const runRes = await fetch(
            `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(p.project_id)}/run/${encodeURIComponent(p.latest_run_id)}`,
          );
          if (!runRes.ok) continue;
          const detail = await runRes.json();
          const gates = detail.gate_statuses ?? {};

          for (const [gate, status] of Object.entries(gates)) {
            if (status === "PENDING" || status === "BLOCKING" || status === "HUMAN_GATE") {
              const isG1 = gate.includes("G1") || gate.includes("GATE_1") || gate.includes("gate-1");
              const isG3 = gate.includes("G3") || gate.includes("GATE_3") || gate.includes("gate-3");
              gateItems.push({
                project_id: p.project_id,
                project_name: p.project_name ?? p.project_id,
                run_id: p.latest_run_id,
                gate_id: gate,
                gate_label: isG1 ? "G1 等价性路径审查" : isG3 ? "G3 风险-收益审查" : gate,
                gate_type: isG1 ? "G1" : isG3 ? "G3" : "INTAKE",
                status,
                priority: status === "BLOCKING" ? "high" : "medium",
              });
            }
          }

          // Also check if overall status indicates human gate pending
          if (detail.status === "halted" || detail.status === "human_gate_pending") {
            const alreadyListed = gateItems.some((g) => g.project_id === p.project_id);
            if (!alreadyListed) {
              gateItems.push({
                project_id: p.project_id,
                project_name: p.project_name ?? p.project_id,
                run_id: p.latest_run_id,
                gate_id: "human_gate",
                gate_label: "人审待处理",
                gate_type: "INTAKE",
                status: "PENDING",
                priority: "high",
              });
            }
          }
        } catch {
          // Skip projects with missing run data
        }
      }

      setItems(gateItems);
    } catch (e: any) {
      setError(e.message ?? "Failed to load human gate items");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGates();
  }, []);

  const pending = items.filter((i) => i.status === "PENDING");
  const blocking = items.filter((i) => i.status === "BLOCKING");

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
            <UserCheckIcon className="h-5 w-5" />
            Human Gate
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            {pending.length + blocking.length > 0
              ? `${pending.length + blocking.length} 个待处理`
              : "无待处理项"}
          </p>
        </div>

        <div className="p-2 border-b space-y-1">
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <Link href="/workspace/review/projects">📋 项目列表</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <Link href="/workspace/review/tasks">⚡ 运行中任务</Link>
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground">
              {items.length > 0 ? `待审队列 (${items.length})` : "队列"}
            </span>
            <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={loadGates}>
              刷新
            </Button>
          </div>

          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              无待审项目
            </div>
          ) : (
            <div className="space-y-1">
              {items.map((item) => (
                <Link
                  key={`${item.project_id}-${item.gate_id}`}
                  href={`/workspace/review/projects/${encodeURIComponent(item.project_id)}/human-gate/${encodeURIComponent(item.gate_id)}?run_id=${encodeURIComponent(item.run_id)}`}
                  className="block p-3 rounded hover:bg-accent transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium truncate">{item.gate_label}</span>
                    {item.priority === "high" ? (
                      <AlertTriangleIcon className="h-4 w-4 text-red-600" />
                    ) : (
                      <ClockIcon className="h-4 w-4 text-yellow-600" />
                    )}
                  </div>
                  <div className="flex items-center gap-1 mt-1">
                    <span className="text-[10px] text-muted-foreground">{item.project_id}</span>
                    <Badge variant="outline" className="text-[10px] px-1 py-0">
                      {item.gate_type}
                    </Badge>
                    <Badge
                      variant={item.status === "BLOCKING" ? "destructive" : "secondary"}
                      className="text-[10px] px-1 py-0"
                    >
                      {item.status === "BLOCKING" ? "阻断" : "待审"}
                    </Badge>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── main content ── */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-4xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold">Human Gate</h1>
              <p className="text-muted-foreground mt-1">
                需要人工评审的 Gate 决策队列
              </p>
            </div>
            <Button onClick={loadGates} variant="outline" size="sm">
              刷新
            </Button>
          </div>

          {loading ? (
            <div className="space-y-4">
              <Skeleton className="h-48 w-full" />
            </div>
          ) : error ? (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-sm text-destructive mb-4">{error}</p>
                <Button variant="outline" onClick={loadGates}>重试</Button>
              </CardContent>
            </Card>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground">
              <CheckCircle2Icon className="h-16 w-16 mb-4 opacity-20" />
              <h3 className="text-lg font-medium">无待审 Gate</h3>
              <p className="text-sm mt-1 max-w-md">
                所有 Gate 已处理完毕。当 Workflow 执行到 Human Gate 节点时，新的待审项会显示在此处。
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {items.map((item) => (
                <Card key={`${item.project_id}-${item.gate_id}`}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm flex items-center gap-2">
                        {item.priority === "high" ? (
                          <AlertTriangleIcon className="h-4 w-4 text-red-600" />
                        ) : (
                          <ClockIcon className="h-4 w-4 text-yellow-600" />
                        )}
                        {item.gate_label}
                      </CardTitle>
                      <div className="flex gap-1">
                        <Badge variant="outline">{item.gate_type}</Badge>
                        <Badge variant={item.status === "BLOCKING" ? "destructive" : "secondary"}>
                          {item.status === "BLOCKING" ? "阻断" : "待审"}
                        </Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-3 text-xs mb-3">
                      <div>
                        <span className="text-muted-foreground">Project</span>
                        <p>{item.project_name}</p>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Run</span>
                        <p className="font-mono text-[10px]">{item.run_id}</p>
                      </div>
                    </div>
                    <Link
                      href={`/workspace/review/projects/${encodeURIComponent(item.project_id)}/human-gate/${encodeURIComponent(item.gate_id)}?run_id=${encodeURIComponent(item.run_id)}`}
                    >
                      <Button size="sm">进入评审</Button>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
