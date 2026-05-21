"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
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
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getBackendBaseURL } from "@/core/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ProjectSummary {
  project_id: string;
  project_name: string;
  product_name: string;
  project_profile_path: string;
  input_root: string;
  current_status: string;
  created_at: string;
  updated_at: string;
  latest_thread_id: string | null;
  latest_run_id: string | null;
  latest_gate_status: string | null;
  latest_human_decision: string | null;
  latest_machine_recommendation: string | null;
  total_runs: number;
  total_rework_rounds: number;
}

interface CreateProjectRequest {
  project_name: string;
  product_name: string;
  project_profile: string;
  input_root?: string;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function listProjects(status?: string): Promise<ProjectSummary[]> {
  const url = status
    ? `${getBackendBaseURL()}/api/rmf/projects?status=${encodeURIComponent(status)}`
    : `${getBackendBaseURL()}/api/rmf/projects`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function createProject(body: CreateProjectRequest): Promise<ProjectSummary> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail ?? `HTTP ${r.status}`);
  }
  return r.json();
}

async function deleteProject(projectId: string): Promise<void> {
  const r = await fetch(`${getBackendBaseURL()}/api/rmf/projects/${projectId}`, {
    method: "DELETE",
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
}

// ---------------------------------------------------------------------------
// Helpers
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
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Project Card
// ---------------------------------------------------------------------------

function ProjectCard({
  project,
  onDelete,
}: {
  project: ProjectSummary;
  onDelete: (id: string) => void;
}) {
  const statusColor = STATUS_COLORS[project.current_status] ?? "bg-gray-500";
  const statusLabel = STATUS_LABELS[project.current_status] ?? project.current_status;

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <CardTitle className="truncate">{project.project_name}</CardTitle>
            <CardDescription className="truncate">{project.product_name}</CardDescription>
          </div>
          <Badge className={`${statusColor} text-white shrink-0`}>{statusLabel}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>Project ID:</span>
          <span className="font-mono truncate">{project.project_id}</span>
          <span>Total Runs:</span>
          <span>{project.total_runs}</span>
          <span>Rework Rounds:</span>
          <span>{project.total_rework_rounds}</span>
          <span>Last Updated:</span>
          <span>{formatDate(project.updated_at)}</span>
          <span>Latest Gate:</span>
          <span className={project.latest_gate_status === "pass" ? "text-green-600" : project.latest_gate_status === "rework_required" ? "text-red-600" : ""}>
            {project.latest_gate_status ?? "—"}
          </span>
        </div>
        <div className="flex gap-2 pt-2">
          <Button asChild size="sm" className="flex-1">
            <Link href={`/workspace/rmf/projects/${project.project_id}`}>View Details</Link>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onDelete(project.project_id)}
          >
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Create Project Dialog
// ---------------------------------------------------------------------------

function CreateProjectForm({
  onCreated,
}: {
  onCreated: () => void,
}) {
  const [projectName, setProjectName] = useState("");
  const [productName, setProductName] = useState("");
  const [projectProfile, setProjectProfile] = useState("");
  const [inputRoot, setInputRoot] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName || !productName || !projectProfile) return;
    setLoading(true);
    try {
      await createProject({
        project_name: projectName,
        product_name: productName,
        project_profile: projectProfile,
        input_root: inputRoot || undefined,
      });
      toast.success("Project created");
      setProjectName("");
      setProductName("");
      setProjectProfile("");
      setInputRoot("");
      onCreated();
    } catch (err) {
      toast.error(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="text-sm font-medium">Project Name *</label>
        <Input
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          placeholder="Wuxi Pamu RMF Review Pilot"
          required
          className="mt-1"
        />
      </div>
      <div>
        <label className="text-sm font-medium">Product Name *</label>
        <Input
          value={productName}
          onChange={(e) => setProductName(e.target.value)}
          placeholder="Pulmonary Ablation System"
          required
          className="mt-1"
        />
      </div>
      <div>
        <label className="text-sm font-medium">Project Profile Path *</label>
        <Input
          value={projectProfile}
          onChange={(e) => setProjectProfile(e.target.value)}
          placeholder="/absolute/path/to/project_profile.yaml"
          required
          className="mt-1"
        />
      </div>
      <div>
        <label className="text-sm font-medium">Input Root (optional)</label>
        <Input
          value={inputRoot}
          onChange={(e) => setInputRoot(e.target.value)}
          placeholder="/mnt/knowledge/source_projects/..."
          className="mt-1"
        />
      </div>
      <Button type="submit" disabled={loading} className="w-full">
        {loading ? "Creating..." : "Create Project"}
      </Button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function RMFProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const status = statusFilter === "all" ? undefined : statusFilter;
      const data = await listProjects(status);
      setProjects(data);
    } catch (err) {
      toast.error(String(err));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this project? Threads will not be deleted.")) return;
    try {
      await deleteProject(id);
      toast.success("Project deleted");
      load();
    } catch (err) {
      toast.error(String(err));
    }
  };

  const statusOptions = [
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
    <div className="w-full max-w-5xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">RMF Review Projects</h1>
          <p className="text-sm text-muted-foreground">
            Manage RMF review projects, cycles, and audit trails
          </p>
        </div>
        <div className="flex gap-2">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {statusOptions.map((s) => (
                <SelectItem key={s} value={s}>
                  {s === "all" ? "All Statuses" : STATUS_LABELS[s] ?? s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={() => setShowCreate(true)}>+ New Project</Button>
          <Button variant="outline" onClick={() => router.push("/workspace/rmf")}>
            ← Workbench
          </Button>
        </div>
      </div>

      {/* Create Project Form */}
      {showCreate && (
        <Card>
          <CardHeader>
            <CardTitle>Create New RMF Project</CardTitle>
          </CardHeader>
          <CardContent>
            <CreateProjectForm onCreated={() => { setShowCreate(false); load(); }} />
          </CardContent>
        </Card>
      )}

      {/* Project List */}
      {loading ? (
        <div className="text-center py-12 text-muted-foreground">Loading...</div>
      ) : projects.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          No projects found. Create one to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {projects.map((p) => (
            <ProjectCard key={p.project_id} project={p} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
