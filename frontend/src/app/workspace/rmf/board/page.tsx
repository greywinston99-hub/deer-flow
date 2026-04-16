"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getBackendBaseURL } from "@/core/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ProjectBoardItem {
  project_id: string;
  project_name: string;
  product_name: string;
  current_status: string;
  latest_machine_recommendation: string | null;
  latest_human_decision: string | null;
  latest_gate_status: string | null;
  total_runs: number;
  total_rework_rounds: number;
  updated_at: string;
  latest_thread_id: string | null;
  latest_run_id: string | null;
}

interface BoardSummary {
  total_projects: number;
  total_runs: number;
  total_rework_rounds: number;
  by_status: Record<string, number>;
  by_machine_recommendation: Record<string, number>;
  by_human_decision: Record<string, number>;
  pending_human_decision_count: number;
  rework_required_count: number;
  passed_count: number;
}

interface BoardResponse {
  summary: BoardSummary;
  projects: ProjectBoardItem[];
  filter_status: string | null;
}

interface RecentActivityItem {
  project_id: string;
  project_name: string;
  event: string;
  detail: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function getBoard(status?: string): Promise<BoardResponse> {
  const url = status && status !== "all"
    ? `${getBackendBaseURL()}/api/rmf/board?status=${encodeURIComponent(status)}`
    : `${getBackendBaseURL()}/api/rmf/board`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getRecentActivity(): Promise<{ items: RecentActivityItem[] }> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/board/recent`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function getByStatus(): Promise<{ status: string; count: number; projects: ProjectBoardItem[] }[]> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/board/by-status`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-500",
  ready_to_run: "bg-blue-500",
  running: "bg-yellow-500",
  pending_human_decision: "bg-orange-500",
  rework_required: "bg-red-500",
  conditional_pass: "bg-amber-500",
  passed: "bg-green-500",
  closed: "bg-gray-700",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  ready_to_run: "Ready to Run",
  running: "Running",
  pending_human_decision: "Pending Human Decision",
  rework_required: "Rework Required",
  conditional_pass: "Conditional Pass",
  passed: "Passed",
  closed: "Closed",
};

function formatDate(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function gateBadge(gate: string | null | undefined): React.ReactNode {
  if (!gate) return <span className="text-muted-foreground text-xs">—</span>;
  const color =
    gate === "pass" ? "bg-green-100 text-green-800" :
    gate === "rework_required" ? "bg-red-100 text-red-800" :
    gate === "conditional_pass" ? "bg-amber-100 text-amber-800" :
    "bg-gray-100";
  return <Badge className={`${color} text-xs`}>{gate}</Badge>;
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function RMFOpsBoardPage() {
  const router = useRouter();
  const [board, setBoard] = useState<BoardResponse | null>(null);
  const [recent, setRecent] = useState<RecentActivityItem[]>([]);
  const [byStatus, setByStatus] = useState<{ status: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [role, setRole] = useState<string>("operator");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [boardData, recentData, statusData] = await Promise.all([
        getBoard(statusFilter === "all" ? undefined : statusFilter),
        getRecentActivity(),
        getByStatus(),
      ]);
      setBoard(boardData);
      setRecent(recentData.items);
      setByStatus(statusData.map(g => ({ status: g.status, count: g.count })));
    } catch (err) {
      toast.error(String(err));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const allStatuses = [
    "all",
    "draft",
    "ready_to_run",
    "running",
    "pending_human_decision",
    "rework_required",
    "conditional_pass",
    "passed",
    "closed",
  ];

  return (
    <div className="w-full max-w-7xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">RMF Operations Board</h1>
          <p className="text-sm text-muted-foreground">
            Team operations view — all projects, statuses, and recent activity
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Role:</span>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="operator">Operator</SelectItem>
                <SelectItem value="reviewer">Reviewer</SelectItem>
                <SelectItem value="approver">Approver</SelectItem>
                <SelectItem value="admin">Admin</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline" onClick={() => router.push("/workspace/rmf")}>
            ← Workbench
          </Button>
          <Button variant="outline" onClick={() => router.push("/workspace/rmf/projects")}>
            Projects
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-muted-foreground">Loading...</div>
      ) : board ? (
        <>
          {/* Summary Cards */}
          {board.summary && (
            <div className="grid grid-cols-4 gap-3">
              <Card>
                <CardContent className="pt-4">
                  <div className="text-xs text-muted-foreground">Total Projects</div>
                  <div className="text-2xl font-bold">{board.summary.total_projects}</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <div className="text-xs text-muted-foreground">Total Runs</div>
                  <div className="text-2xl font-bold">{board.summary.total_runs}</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <div className="text-xs text-muted-foreground">Rework Required</div>
                  <div className="text-2xl font-bold text-red-600">{board.summary.rework_required_count}</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <div className="text-xs text-muted-foreground">Pending Human Decision</div>
                  <div className="text-2xl font-bold text-orange-600">{board.summary.pending_human_decision_count}</div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* By-Status breakdown */}
          {board.summary && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Projects by Status</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {allStatuses.filter(s => s !== "all").map(s => {
                    const count = board.summary.by_status[s] ?? 0;
                    const color = STATUS_COLORS[s] ?? "bg-gray-500";
                    return (
                      <div key={s} className="flex items-center gap-1.5">
                        <Badge className={`${color} text-white text-xs`}>
                          {STATUS_LABELS[s] ?? s}: {count}
                        </Badge>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Machine vs Human vs Final Gate breakdown */}
          {board.summary && (
            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardHeader><CardTitle className="text-base">By Machine Recommendation</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-1">
                    {Object.entries(board.summary.by_machine_recommendation).map(([rec, count]) => (
                      <div key={rec} className="flex items-center justify-between text-sm">
                        <span>{gateBadge(rec)}</span>
                        <span className="font-medium">{count}</span>
                      </div>
                    ))}
                    {Object.keys(board.summary.by_machine_recommendation).length === 0 && (
                      <div className="text-xs text-muted-foreground">No data</div>
                    )}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="text-base">By Human Decision</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-1">
                    {Object.entries(board.summary.by_human_decision).map(([dec, count]) => (
                      <div key={dec} className="flex items-center justify-between text-sm">
                        <span>{gateBadge(dec)}</span>
                        <span className="font-medium">{count}</span>
                      </div>
                    ))}
                    {Object.keys(board.summary.by_human_decision).length === 0 && (
                      <div className="text-xs text-muted-foreground">No data</div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Filter:</span>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {allStatuses.map(s => (
                  <SelectItem key={s} value={s}>
                    {s === "all" ? "All Statuses" : STATUS_LABELS[s] ?? s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-sm text-muted-foreground">
              {board.projects.length} project{board.projects.length !== 1 ? "s" : ""}
            </span>
          </div>

          {/* Project Table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {statusFilter === "all" ? "All RMF Projects" : `${STATUS_LABELS[statusFilter] ?? statusFilter} Projects`}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {board.projects.length === 0 ? (
                <div className="text-sm text-muted-foreground py-6 text-center">
                  No projects found.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="pb-2 font-medium">Project</th>
                        <th className="pb-2 font-medium">Status</th>
                        <th className="pb-2 font-medium">Machine Rec</th>
                        <th className="pb-2 font-medium">Human Decision</th>
                        <th className="pb-2 font-medium">Final Gate</th>
                        <th className="pb-2 font-medium text-center">Runs</th>
                        <th className="pb-2 font-medium text-center">Reworks</th>
                        <th className="pb-2 font-medium">Updated</th>
                        <th className="pb-2 font-medium">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {board.projects.map((p) => (
                        <tr key={p.project_id} className="hover:bg-muted/50">
                          <td className="py-2">
                            <div className="font-medium text-sm">{p.project_name}</div>
                            <div className="text-xs text-muted-foreground truncate max-w-32">{p.product_name}</div>
                          </td>
                          <td className="py-2">
                            <Badge className={`${STATUS_COLORS[p.current_status] ?? "bg-gray-500"} text-white text-xs`}>
                              {STATUS_LABELS[p.current_status] ?? p.current_status}
                            </Badge>
                          </td>
                          <td className="py-2">{gateBadge(p.latest_machine_recommendation)}</td>
                          <td className="py-2">{gateBadge(p.latest_human_decision)}</td>
                          <td className="py-2">{gateBadge(p.latest_gate_status)}</td>
                          <td className="py-2 text-center font-medium">{p.total_runs}</td>
                          <td className="py-2 text-center">
                            {p.total_rework_rounds > 0 ? (
                              <span className="text-orange-600 font-medium">{p.total_rework_rounds}</span>
                            ) : (
                              <span className="text-muted-foreground">0</span>
                            )}
                          </td>
                          <td className="py-2 text-xs text-muted-foreground">{formatDate(p.updated_at)}</td>
                          <td className="py-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => router.push(`/workspace/rmf/projects/${p.project_id}`)}
                            >
                              View
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent Activity */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              {recent.length === 0 ? (
                <div className="text-sm text-muted-foreground py-4 text-center">No recent activity</div>
              ) : (
                <div className="space-y-2">
                  {recent.map((item) => (
                    <div key={`${item.project_id}-${item.timestamp}`} className="flex items-start gap-3 text-sm">
                      <div className="min-w-0 flex-1">
                        <span className="font-medium">{item.event}</span>
                        <span className="text-muted-foreground"> — </span>
                        <span className="text-muted-foreground truncate">{item.detail}</span>
                      </div>
                      <div className="text-xs text-muted-foreground shrink-0">{formatDate(item.timestamp)}</div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
