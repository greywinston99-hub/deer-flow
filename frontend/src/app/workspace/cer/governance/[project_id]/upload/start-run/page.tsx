"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cerReviewFetch } from "@/core/cer_auth/api";
import { getBackendBaseURL } from "@/core/config";

interface StartRunResponse {
  project_id: string;
  thread_id: string;
  run_id: string;
  round_id: string;
  mode: string;
  workflow_name: string;
  artifact_root: string;
  executed_steps: string[];
  message: string;
}

export default function StartRunPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = decodeURIComponent(String(params.project_id as string));

  const [starting, setStarting] = useState(false);
  const [result, setResult] = useState<StartRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const startRun = useCallback(async () => {
    setStarting(true);
    setError(null);
    try {
      const r = await cerReviewFetch(
        `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/runs`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: "smoke-run" }),
        }
      );
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
        throw new Error(err.detail ?? `HTTP ${r.status}`);
      }
      const data: StartRunResponse = await r.json();
      setResult(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start run";
      setError(msg);
      toast.error(msg);
    } finally {
      setStarting(false);
    }
  }, [projectId]);

  useEffect(() => {
    void startRun();
  }, [startRun]);

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-80 border-r flex flex-col">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-lg font-semibold">CER Governance</h2>
          </div>
          <p className="text-xs text-muted-foreground">Review Workspace — Governance Data</p>
        </div>
        <div className="p-2 border-b space-y-1">
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <Link href="/workspace/cer/governance/run-home">🏠 Run Home</Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto">
          {/* Header */}
          <div className="mb-6">
            <Link
              href={`/workspace/cer/governance/${encodeURIComponent(projectId)}/upload`}
              className="text-sm text-muted-foreground hover:text-foreground mb-2 inline-flex items-center gap-1"
            >
              ← Back to Upload
            </Link>
            <h1 className="text-2xl font-bold mb-1">Starting Smoke-Run</h1>
            <p className="text-sm text-muted-foreground">
              Project: <span className="font-mono font-medium">{projectId}</span>
            </p>
          </div>

          {/* State */}
          {starting && !result && !error && (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12 gap-4">
                <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full" />
                <div className="text-center">
                  <p className="font-medium">Starting smoke-run...</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Invoking cer_review_runner.py — this may take up to 30 minutes.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {error && (
            <Card className="border-red-300">
              <CardHeader>
                <CardTitle className="text-base text-red-600">Run Failed</CardTitle>
                <CardDescription>{error}</CardDescription>
              </CardHeader>
              <CardContent className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => router.push(`/workspace/cer/governance/${encodeURIComponent(projectId)}/upload`)}
                >
                  Back to Upload
                </Button>
                <Button onClick={() => { setError(null); void startRun(); }}>
                  Retry
                </Button>
              </CardContent>
            </Card>
          )}

          {result && (
            <Card className="border-green-300">
              <CardHeader>
                <CardTitle className="text-base text-green-600">Run Started</CardTitle>
                <CardDescription>{result.message}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-xs text-muted-foreground">Run ID</div>
                    <div className="font-mono text-xs">{result.run_id}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Thread ID</div>
                    <div className="font-mono text-xs">{result.thread_id}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Round</div>
                    <div className="font-mono text-xs">{result.round_id}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Workflow</div>
                    <div className="font-mono text-xs">{result.workflow_name}</div>
                  </div>
                </div>
                {result.executed_steps.length > 0 && (
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Executed Steps</div>
                    <div className="space-y-1">
                      {result.executed_steps.map((step, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <span className="text-green-600">✓</span>
                          <span className="font-mono">{step}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex gap-3 pt-2">
                  <Button
                    onClick={() =>
                      router.push(`/workspace/cer/governance/${encodeURIComponent(projectId)}?run_id=${encodeURIComponent(result.run_id)}`)
                    }
                  >
                    View Run Detail
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => router.push(`/workspace/cer/governance/${encodeURIComponent(projectId)}/upload`)}
                  >
                    Back to Upload
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
