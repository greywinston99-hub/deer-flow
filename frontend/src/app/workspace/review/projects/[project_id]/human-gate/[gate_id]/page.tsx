"use client";

import { useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { getBackendBaseURL } from "@/core/config";
import {
  ArrowLeftIcon,
  ShieldCheckIcon,
  UserCheckIcon,
  CheckCircle2Icon,
  XCircleIcon,
  RotateCcwIcon,
  AlertTriangleIcon,
  Loader2Icon,
} from "lucide-react";

type Decision = "APPROVE" | "REJECT" | "REWORK";

export default function HumanGateDecisionPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = decodeURIComponent(params.project_id as string);
  const gateId = decodeURIComponent(params.gate_id as string);
  const runId = decodeURIComponent(searchParams.get("run_id") ?? "");

  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [stepId, setStepId] = useState("");
  const [findingId, setFindingId] = useState("");
  const [sourceFile, setSourceFile] = useState("");
  const [sourceLocation, setSourceLocation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isG1 = gateId.includes("G1") || gateId.includes("gate-1") || gateId.includes("GATE_1");
  const isG3 = gateId.includes("G3") || gateId.includes("gate-3") || gateId.includes("GATE_3");
  const gateLabel = isG1 ? "G1 等价性路径审查" : isG3 ? "G3 风险-收益审查" : "人审决策";
  const gateType = isG1 ? "G1" : isG3 ? "G3" : "INTAKE";

  const handleDecision = async (decision: Decision) => {
    if (!reviewer.trim()) { setError("请输入评审人"); return; }
    if (decision !== "APPROVE" && !reason.trim()) { setError("退回/驳回必须填写理由"); return; }

    setSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const body: Record<string, any> = {
        run_id: runId,
        interviewer: reviewer,
        reviewer: reviewer,
        decision: decision === "APPROVE"
          ? (gateType === "G3" ? "BRR_ACCEPTABLE" : "APPROVE_EQUIVALENCE_ROUTE")
          : decision === "REJECT"
            ? (gateType === "G3" ? "BRR_UNACCEPTABLE" : "REJECT_EQUIVALENCE_ROUTE")
            : "CONDITIONAL_EQUIVALENCE",
        rationale: reason,
        reason: reason,
        project_id: projectId,
        gate_id: gateId,
        step_id: stepId || undefined,
        finding_id: findingId || undefined,
        source_file: sourceFile || undefined,
        source_location: sourceLocation || undefined,
        evidence_ref: sourceFile || undefined,
        round_id: runId,
        reauth_timestamp: new Date().toISOString(),
      };

      const endpoint = gateType === "G3"
        ? `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/gate-3/decision`
        : gateType === "G1"
          ? `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/gate-1/decision`
          : `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/intake/human-decision`;

      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error((data as any).detail ?? (data as any).error ?? `HTTP ${res.status}`);
      }

      setResult({
        success: true,
        message: `决策已提交 · ${decision === "APPROVE" ? "已批准" : decision === "REJECT" ? "已驳回" : "已退回返工"}`,
      });
    } catch (e: any) {
      setError(e.message ?? "Submitting decision failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex h-full">
      {/* ── left sidebar ── */}
      <div className="w-72 border-r flex flex-col bg-background">
        <div className="p-4 border-b">
          <Link href="/workspace/review/human-gate">
            <Button variant="ghost" size="sm" className="mb-2">
              <ArrowLeftIcon className="h-4 w-4 mr-1" />
              返回 Human Gate
            </Button>
          </Link>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <UserCheckIcon className="h-5 w-5" />
            Gate 决策
          </h2>
          <p className="text-xs text-muted-foreground mt-1 truncate">{gateLabel}</p>
        </div>

        <div className="p-3 border-b text-xs space-y-1">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Project</span>
            <span className="font-mono">{projectId}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Run</span>
            <span className="font-mono text-[10px]">{runId || "N/A"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Gate</span>
            <Badge variant="outline" className="text-[10px]">{gateType}</Badge>
          </div>
        </div>
      </div>

      {/* ── main content ── */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-2xl">
          <h1 className="text-2xl font-bold mb-2">{gateLabel}</h1>
          <p className="text-muted-foreground mb-6">
            提交人工评审决策。驳回或退回时必须填写理由并绑定证据。
          </p>

          {/* Result banner */}
          {result && (
            <div className={`p-4 rounded mb-6 ${result.success ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
              <div className="flex items-center gap-2">
                {result.success ? <CheckCircle2Icon className="h-5 w-5" /> : <XCircleIcon className="h-5 w-5" />}
                <span className="text-sm font-medium">{result.message}</span>
              </div>
              {result.success && (
                <Button variant="outline" size="sm" className="mt-3" asChild>
                  <Link href="/workspace/review/human-gate">返回 Human Gate 队列</Link>
                </Button>
              )}
            </div>
          )}

          <Card className="mb-6">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <ShieldCheckIcon className="h-4 w-4" />
                决策表单
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Reviewer */}
              <div className="space-y-1">
                <Label htmlFor="reviewer">评审人 *</Label>
                <Input
                  id="reviewer"
                  placeholder="评审人姓名/ID"
                  value={reviewer}
                  onChange={(e) => setReviewer(e.target.value)}
                  disabled={submitting}
                />
              </div>

              {/* Reason */}
              <div className="space-y-1">
                <Label htmlFor="reason">
                  理由 {reason ? "" : "(退回/驳回时必填)"}
                </Label>
                <Textarea
                  id="reason"
                  placeholder="填写决策理由——为什么批准/驳回/退回？关联了哪些证据？"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  disabled={submitting}
                  rows={4}
                />
              </div>

              {/* Evidence binding fields */}
              <div className="border-t pt-4">
                <p className="text-xs text-muted-foreground mb-3">
                  证据绑定（以下字段将写入后端，确保决策可追溯）
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="stepId" className="text-xs">Step ID</Label>
                    <Input
                      id="stepId"
                      placeholder="cer_human_boundary"
                      value={stepId}
                      onChange={(e) => setStepId(e.target.value)}
                      disabled={submitting}
                      className="font-mono text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="findingId" className="text-xs">Finding ID</Label>
                    <Input
                      id="findingId"
                      placeholder="finding-001"
                      value={findingId}
                      onChange={(e) => setFindingId(e.target.value)}
                      disabled={submitting}
                      className="font-mono text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="sourceFile" className="text-xs">Source File</Label>
                    <Input
                      id="sourceFile"
                      placeholder="/path/to/source/file.pdf"
                      value={sourceFile}
                      onChange={(e) => setSourceFile(e.target.value)}
                      disabled={submitting}
                      className="font-mono text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="sourceLocation" className="text-xs">Source Location</Label>
                    <Input
                      id="sourceLocation"
                      placeholder="Section 3.2, paragraph 4"
                      value={sourceLocation}
                      onChange={(e) => setSourceLocation(e.target.value)}
                      disabled={submitting}
                      className="font-mono text-xs"
                    />
                  </div>
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="p-3 rounded bg-destructive/10 text-destructive text-sm">
                  <AlertTriangleIcon className="h-4 w-4 inline mr-1" />
                  {error}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Action buttons */}
          <div className="flex gap-3">
            <Button
              onClick={() => handleDecision("APPROVE")}
              disabled={submitting || !!result?.success}
              variant="default"
              className="flex-1"
            >
              {submitting ? <Loader2Icon className="h-4 w-4 mr-1 animate-spin" /> : <CheckCircle2Icon className="h-4 w-4 mr-1" />}
              批准 (Approve)
            </Button>
            <Button
              onClick={() => handleDecision("REWORK")}
              disabled={submitting || !!result?.success}
              variant="secondary"
              className="flex-1"
            >
              <RotateCcwIcon className="h-4 w-4 mr-1" />
              退回返工 (Rework)
            </Button>
            <Button
              onClick={() => handleDecision("REJECT")}
              disabled={submitting || !!result?.success}
              variant="destructive"
              className="flex-1"
            >
              <XCircleIcon className="h-4 w-4 mr-1" />
              驳回 (Reject)
            </Button>
          </div>

          <p className="text-xs text-muted-foreground mt-3 text-center">
            退回或驳回时必须填写理由并绑定 Step ID / Source File。决策将写入后端并记录到 decision ledger。
          </p>
        </div>
      </div>
    </div>
  );
}
