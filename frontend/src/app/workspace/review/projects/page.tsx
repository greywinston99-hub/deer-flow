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
  PlusIcon,
  FlaskConicalIcon,
  FileTextIcon,
  ActivityIcon,
} from "lucide-react";

interface ReviewProject {
  project_id: string;
  project_name: string;
  device_name?: string;
  device_family?: string;
  status?: string;
  latest_run_id?: string;
  latest_run_status?: string;
  created_at?: string;
  updated_at?: string;
}

export default function ReviewProjectsPage() {
  const [projects, setProjects] = useState<ReviewProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProjects = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${getBackendBaseURL()}/api/cer-review/projects`);
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();
      setProjects(data.projects ?? []);
    } catch (e: any) {
      setError(e.message ?? "Failed to load projects");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  return (
    <div className="flex h-full">
      {/* ── left sidebar ── */}
      <div className="w-72 border-r flex flex-col bg-background">
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <ShieldCheckIcon className="h-5 w-5" />
            评审工作台
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            CER / RMF 临床评审项目管理
          </p>
        </div>

        <div className="p-2 border-b space-y-1">
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <Link href="/workspace/review/projects">📋 项目列表</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <Link href="/workspace/review/new">
              <PlusIcon className="h-3 w-3 mr-1" /> 新建评审
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <Link href="/workspace/review/tasks">⚡ 运行中任务</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <Link href="/workspace/review/human-gate">👤 Human Gate</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <Link href="/workspace/review/agent-teams">🔍 Agent Teams</Link>
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground">
              {projects.length > 0 ? `项目 (${projects.length})` : "项目"}
            </span>
            <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={loadProjects}>
              刷新
            </Button>
          </div>

          {loading ? (
            <div className="space-y-2 p-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : error ? (
            <div className="p-4 text-center text-sm text-destructive">
              {error}
              <Button variant="outline" size="sm" className="mt-2" onClick={loadProjects}>
                重试
              </Button>
            </div>
          ) : projects.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              暂无评审项目
              <div className="mt-2">
                <Link href="/workspace/review/new">
                  <Button variant="outline" size="sm">创建第一个项目</Button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              {projects.map((p) => (
                <Link
                  key={p.project_id}
                  href={`/workspace/cer/governance/${encodeURIComponent(p.project_id)}`}
                  className="block p-3 rounded hover:bg-accent transition-colors"
                >
                  <div className="text-sm font-medium">{p.project_name || p.project_id}</div>
                  <div className="flex items-center gap-1 mt-1">
                    <span className="text-xs text-muted-foreground">{p.project_id}</span>
                    {p.status && (
                      <Badge variant="outline" className="text-[10px] px-1 py-0">
                        {p.status}
                      </Badge>
                    )}
                  </div>
                  {p.device_name && (
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {p.device_name}
                    </div>
                  )}
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── main content ── */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-4xl">
          <h1 className="text-2xl font-bold mb-2">评审工作台</h1>
          <p className="text-muted-foreground mb-6">
            管理 CER 临床评价报告评审、RMF 风险管理文件评审以及 CER+RMF 联合评审项目。
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <FileTextIcon className="h-4 w-4" />
                  CER 临床评价评审
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground mb-3">
                  按照 MDR 2017/745 Annex XIV Part A 对临床评价报告进行系统化评审。
                  10-step D1 workflow，18+ review agents。
                </p>
                <Link href="/workspace/review/new">
                  <Button size="sm" variant="outline">新建 CER 评审</Button>
                </Link>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <ActivityIcon className="h-4 w-4" />
                  RMF 风险管理评审
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground mb-3">
                  按照 ISO 14971:2019 对风险管理文件进行评审。
                  包含 FMEA/RMF 双线 precheck、6-dimension review、Human Boundary。
                </p>
                <Link href="/workspace/rmf/projects">
                  <Button size="sm" variant="outline">查看 RMF 项目</Button>
                </Link>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <FlaskConicalIcon className="h-4 w-4" />
                CER+RMF 联合评审
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground mb-3">
                跨文档一致性评审，覆盖 CER↔RMF↔IFU↔FMEA↔PMCF 的全文档链。
              </p>
              <Badge variant="secondary" className="text-xs">即将上线</Badge>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
