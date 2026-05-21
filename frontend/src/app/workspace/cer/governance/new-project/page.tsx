"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cerReviewFetch } from "@/core/cer_auth/api";
import { getBackendBaseURL } from "@/core/config";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CreateProjectResponse {
  project_id: string;
  project_name: string;
  created_at: string;
  governance_path: string;
  input_path: string;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

async function createProject(data: {
  project_id: string;
  project_name: string;
  device_name: string;
  device_family?: string;
  device_class?: string;
  intended_use?: string;
  market_stage: string;
  jurisdiction: string;
  organization?: string;
}): Promise<CreateProjectResponse> {
  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/projects`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
    throw new Error(err.detail || `HTTP ${r.status}`);
  }
  return r.json() as Promise<CreateProjectResponse>;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function NewProjectPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  const [projectId, setProjectId] = useState("");
  const [projectName, setProjectName] = useState("");
  const [deviceName, setDeviceName] = useState("");
  const [deviceFamily, setDeviceFamily] = useState("");
  const [deviceClass, setDeviceClass] = useState("");
  const [intendedUse, setIntendedUse] = useState("");
  const [marketStage, setMarketStage] = useState("CE Marked");
  const [jurisdiction, setJurisdiction] = useState("EU MDR 2017/745");
  const [organization, setOrganization] = useState("");

  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = useCallback(() => {
    const e: Record<string, string> = {};
    if (!projectId.trim()) {
      e.project_id = "Project ID is required";
    } else if (!/^CER-PJT-\d{4}$/.test(projectId.trim())) {
      e.project_id = "Must match format CER-PJT-XXXX (e.g. CER-PJT-0002)";
    }
    if (!projectName.trim()) e.project_name = "Project name is required";
    if (!deviceName.trim()) e.device_name = "Device name is required";
    if (!marketStage) e.market_stage = "Market stage is required";
    if (!jurisdiction.trim()) e.jurisdiction = "Jurisdiction is required";
    setErrors(e);
    return Object.keys(e).length === 0;
  }, [projectId, projectName, deviceName, marketStage, jurisdiction]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!validate()) return;

      setSubmitting(true);
      try {
        const result = await createProject({
          project_id: projectId.trim(),
          project_name: projectName.trim(),
          device_name: deviceName.trim(),
          device_family: deviceFamily.trim() || undefined,
          device_class: deviceClass.trim() || undefined,
          intended_use: intendedUse.trim() || undefined,
          market_stage: marketStage,
          jurisdiction: jurisdiction.trim(),
          organization: organization.trim() || undefined,
        });
        toast.success(`Project ${result.project_id} created successfully`);
        router.push(
          `/workspace/cer/governance/${encodeURIComponent(result.project_id)}/upload`
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to create project";
        toast.error(msg);
      } finally {
        setSubmitting(false);
      }
    },
    [projectId, projectName, deviceName, deviceFamily, deviceClass, intendedUse, marketStage, jurisdiction, organization, validate, router]
  );

  const isValid =
    projectId.trim() &&
    projectName.trim() &&
    deviceName.trim() &&
    marketStage &&
    jurisdiction.trim();

  return (
    <div className="flex h-full">
      {/* Sidebar — same as run-home */}
      <div className="w-80 border-r flex flex-col">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-lg font-semibold">CER Governance</h2>
          </div>
          <p className="text-xs text-muted-foreground">Review Workspace — Governance Data</p>
        </div>
        <div className="p-2 border-b space-y-1">
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <a href="/workspace/cer/governance/run-home">🏠 Run Home</a>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto">
          {/* Header */}
          <div className="mb-6">
            <Link
              href="/workspace/cer/governance/run-home"
              className="text-sm text-muted-foreground hover:text-foreground mb-2 inline-flex items-center gap-1"
            >
              ← Back to Projects
            </Link>
            <h1 className="text-2xl font-bold mb-1">Create New CER Project</h1>
            <p className="text-sm text-muted-foreground">
              Set up a new CER project. After creation, upload evidence packs and start a review run.
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Project ID */}
            <div className="space-y-1">
              <Label htmlFor="project_id">
                Project ID <span className="text-destructive">*</span>
              </Label>
              <Input
                id="project_id"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value.toUpperCase())}
                placeholder="CER-PJT-0002"
                className={errors.project_id ? "border-destructive" : ""}
              />
              {errors.project_id && (
                <p className="text-xs text-destructive">{errors.project_id}</p>
              )}
              <p className="text-xs text-muted-foreground">
                Must match format CER-PJT-XXXX (e.g. CER-PJT-0002)
              </p>
            </div>

            {/* Project Name */}
            <div className="space-y-1">
              <Label htmlFor="project_name">
                Project Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="project_name"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="136.江苏臣诺-电动吻合器"
                className={errors.project_name ? "border-destructive" : ""}
              />
              {errors.project_name && (
                <p className="text-xs text-destructive">{errors.project_name}</p>
              )}
            </div>

            {/* Device Name */}
            <div className="space-y-1">
              <Label htmlFor="device_name">
                Device Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="device_name"
                value={deviceName}
                onChange={(e) => setDeviceName(e.target.value)}
                placeholder="一次性使用电动腔镜直线型切割吻合器"
                className={errors.device_name ? "border-destructive" : ""}
              />
              {errors.device_name && (
                <p className="text-xs text-destructive">{errors.device_name}</p>
              )}
            </div>

            {/* Device Family */}
            <div className="space-y-1">
              <Label htmlFor="device_family">Device Family</Label>
              <Input
                id="device_family"
                value={deviceFamily}
                onChange={(e) => setDeviceFamily(e.target.value)}
                placeholder="DES-3000 系列"
              />
            </div>

            {/* Device Class */}
            <div className="space-y-1">
              <Label htmlFor="device_class">Device Class</Label>
              <Input
                id="device_class"
                value={deviceClass}
                onChange={(e) => setDeviceClass(e.target.value)}
                placeholder="Class IIa"
              />
            </div>

            {/* Intended Use */}
            <div className="space-y-1">
              <Label htmlFor="intended_use">Intended Use</Label>
              <Textarea
                id="intended_use"
                value={intendedUse}
                onChange={(e) => setIntendedUse(e.target.value)}
                placeholder="腹部、胸部、妇科、儿科手术中的组织切割与吻合"
                rows={2}
              />
            </div>

            {/* Market Stage */}
            <div className="space-y-1">
              <Label htmlFor="market_stage">
                Market Stage <span className="text-destructive">*</span>
              </Label>
              <select
                id="market_stage"
                value={marketStage}
                onChange={(e) => setMarketStage(e.target.value)}
                className={cn(
                  "border-input h-9 w-full min-w-0 rounded-md border bg-transparent px-3 py-1 text-base shadow-xs transition-[color,box-shadow] outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
                  errors.market_stage ? "border-destructive" : "",
                  "cursor-pointer"
                )}
                data-slot="input"
              >
                <option value="CE Marked">CE Marked</option>
                <option value="FDA 510(k)">FDA 510(k)</option>
                <option value="NMPA">NMPA</option>
                <option value="Other">Other</option>
              </select>
              {errors.market_stage && (
                <p className="text-xs text-destructive">{errors.market_stage}</p>
              )}
            </div>

            {/* Jurisdiction */}
            <div className="space-y-1">
              <Label htmlFor="jurisdiction">
                Jurisdiction <span className="text-destructive">*</span>
              </Label>
              <Input
                id="jurisdiction"
                value={jurisdiction}
                onChange={(e) => setJurisdiction(e.target.value)}
                placeholder="EU MDR 2017/745"
                className={errors.jurisdiction ? "border-destructive" : ""}
              />
              {errors.jurisdiction && (
                <p className="text-xs text-destructive">{errors.jurisdiction}</p>
              )}
            </div>

            {/* Organization */}
            <div className="space-y-1">
              <Label htmlFor="organization">Organization</Label>
              <Input
                id="organization"
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                placeholder="江苏臣诺医疗科技有限公司"
              />
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.back()}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={!isValid || submitting}>
                {submitting ? "Creating..." : "Create Project"}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
