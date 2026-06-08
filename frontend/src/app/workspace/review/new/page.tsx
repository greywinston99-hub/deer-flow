"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { getBackendBaseURL } from "@/core/config";
import {
  ArrowLeftIcon,
  ShieldCheckIcon,
  FileTextIcon,
  ActivityIcon,
  FlaskConicalIcon,
  FolderOpenIcon,
  Loader2Icon,
} from "lucide-react";

type ReviewType = "CER" | "RMF" | "CER_RMF";

export default function NewReviewPage() {
  const router = useRouter();
  const [projectName, setProjectName] = useState("");
  const [reviewType, setReviewType] = useState<ReviewType>("CER");
  const [sourcePath, setSourcePath] = useState("");
  const [deviceName, setDeviceName] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<"form" | "scanning" | "done">("form");

  const generateProjectId = () => {
    const ts = Date.now().toString(36).toUpperCase().slice(-4);
    return `CER-PJT-${ts}`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName.trim()) { setError("请输入项目名称"); return; }
    if (!sourcePath.trim()) { setError("请输入 source package 路径"); return; }

    setSubmitting(true);
    setError(null);
    setStep("scanning");

    try {
      const projectId = generateProjectId();

      // Step 1: Create project
      const createRes = await fetch(`${getBackendBaseURL()}/api/cer-review/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          project_name: projectName,
          device_name: deviceName || projectName,
          device_family: reviewType === "RMF" ? "RMF Device" : undefined,
          device_class: "Class IIa",
          intended_use: notes || undefined,
          market_stage: "CE Marked",
          jurisdiction: "EU MDR 2017/745",
        }),
      });

      if (!createRes.ok) {
        const errData = await createRes.json().catch(() => ({}));
        throw new Error((errData as any).detail ?? `Create project failed: ${createRes.statusText}`);
      }

      const project = await createRes.json();

      // Step 2: Trigger source scan
      const scanRes = await fetch(
        `${getBackendBaseURL()}/api/cer-review/intake/source-package/scan`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: projectId,
            project_name: projectName,
            source_package_path: sourcePath,
            scan_mode: "METADATA_ONLY",
            recursive: true,
            max_files: 500,
            human_confirmation_required: true,
          }),
        },
      );

      if (!scanRes.ok) {
        const errData = await scanRes.json().catch(() => ({}));
        throw new Error((errData as any).detail ?? `Scan failed: ${scanRes.statusText}`);
      }

      setStep("done");
      router.push(`/workspace/review/projects/${encodeURIComponent(projectId)}/scan?project_name=${encodeURIComponent(projectName)}`);
    } catch (e: any) {
      setError(e.message ?? "Unknown error");
      setStep("form");
    } finally {
      setSubmitting(false);
    }
  };

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
            新建评审
          </h2>
          <p className="text-xs text-muted-foreground mt-1">创建 CER / RMF 评审项目</p>
        </div>
        <div className="p-3 text-xs text-muted-foreground">
          <p>创建项目后将自动扫描 source package 文件夹中的文件，并识别文件类型。</p>
        </div>
      </div>

      {/* ── main form ── */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-2xl">
          <h1 className="text-2xl font-bold mb-6">创建评审项目</h1>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Project name */}
            <div className="space-y-2">
              <Label htmlFor="projectName">项目名称 *</Label>
              <Input
                id="projectName"
                placeholder="例如：ThermaScan PRO-2000 CER Review"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                disabled={submitting}
              />
            </div>

            {/* Review type */}
            <div className="space-y-2">
              <Label>评审类型 *</Label>
              <div className="flex gap-2">
                {([
                  { value: "CER" as ReviewType, label: "CER 临床评价评审", icon: FileTextIcon, desc: "MDR Annex XIV Part A" },
                  { value: "RMF" as ReviewType, label: "RMF 风险管理评审", icon: ActivityIcon, desc: "ISO 14971:2019" },
                  { value: "CER_RMF" as ReviewType, label: "CER+RMF 联合评审", icon: FlaskConicalIcon, desc: "全文档链一致性" },
                ]).map((opt) => {
                  const Icon = opt.icon;
                  const disabled = opt.value === "CER_RMF";
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      disabled={disabled}
                      className={`flex-1 p-4 rounded border text-left transition-colors ${
                        reviewType === opt.value
                          ? "border-primary bg-primary/5"
                          : disabled
                            ? "border-border bg-muted/30 opacity-50 cursor-not-allowed"
                            : "border-border hover:border-primary/50"
                      }`}
                      onClick={() => !disabled && setReviewType(opt.value)}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Icon className="h-4 w-4" />
                        <span className="text-sm font-medium">{opt.label}</span>
                        {disabled && <Badge variant="secondary" className="text-[10px]">即将上线</Badge>}
                      </div>
                      <p className="text-xs text-muted-foreground">{opt.desc}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Source package path */}
            <div className="space-y-2">
              <Label htmlFor="sourcePath" className="flex items-center gap-1">
                <FolderOpenIcon className="h-4 w-4" />
                本地 Source Package 路径 *
              </Label>
              <Input
                id="sourcePath"
                placeholder="例如：/Users/winstonwei/Documents/cer-project/source-package/"
                value={sourcePath}
                onChange={(e) => setSourcePath(e.target.value)}
                disabled={submitting}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                输入本地文件夹的绝对路径。系统将扫描该目录中的文件并进行分类识别。
              </p>
            </div>

            {/* Device name */}
            <div className="space-y-2">
              <Label htmlFor="deviceName">产品名称（可选）</Label>
              <Input
                id="deviceName"
                placeholder="设备/产品名称"
                value={deviceName}
                onChange={(e) => setDeviceName(e.target.value)}
                disabled={submitting}
              />
            </div>

            {/* Notes */}
            <div className="space-y-2">
              <Label htmlFor="notes">项目备注（可选）</Label>
              <Textarea
                id="notes"
                placeholder="项目描述、注意事项等"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={submitting}
                rows={3}
              />
            </div>

            {/* Error */}
            {error && (
              <div className="p-3 rounded bg-destructive/10 text-destructive text-sm">
                {error}
              </div>
            )}

            {/* Submit */}
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? (
                <>
                  <Loader2Icon className="h-4 w-4 mr-2 animate-spin" />
                  {step === "scanning" ? "正在扫描文件..." : "创建中..."}
                </>
              ) : (
                "创建项目并扫描文件"
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
