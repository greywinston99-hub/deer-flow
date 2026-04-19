"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
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
import { cerReviewFetch } from "@/core/cer_auth";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LockedPackFileEntry {
  relative_path: string;
  sha256: string;
  ep: string;
  size_bytes: number | null;
}

interface LockedPackResponse {
  project_id: string;
  intake_session_id: string;
  total_files: number;
  files: LockedPackFileEntry[];
  manifest_path: string | null;
  verified: boolean;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function getLockedPack(projectId: string): Promise<LockedPackResponse> {
  const r = await cerReviewFetch(
    `/api/cer-review/${encodeURIComponent(projectId)}/intake/locked-pack`
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LockedPackPage() {
  const params = useParams();
  const projectId = decodeURIComponent(String(params.project_id));

  const [data, setData] = useState<LockedPackResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getLockedPack(projectId);
      setData(result);
    } catch (e) {
      if (e instanceof Error && e.message.includes("404")) {
        setError("No locked evidence pack found. Submit human gate decision first.");
      } else {
        toast.error("Failed to load locked pack data");
      }
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <p>Loading locked pack data...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-full">
        {/* Sidebar */}
        <div className="w-72 border-r flex flex-col">
          <div className="p-4 border-b">
            <div className="text-xs text-muted-foreground mb-1">
              <Link href="/workspace/cer/governance/run-home" className="hover:underline">
                ← Run Home
              </Link>
            </div>
            <h2 className="text-sm font-semibold font-mono">{projectId}</h2>
            <p className="text-xs text-muted-foreground mt-1">Locked Evidence Pack</p>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-4">
            <div className="text-5xl">🔒</div>
            <h2 className="text-xl font-semibold">No Locked Evidence Pack</h2>
            <p className="text-sm text-muted-foreground max-w-md">
              {error || "The locked evidence pack will appear here after human gate approval."}
            </p>
            <div className="flex gap-3 justify-center pt-2">
              <Button asChild>
                <Link href={`../human-gate`}>Go to Human Gate</Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href={`../`}>View Intake Status</Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Group files by EP
  const filesByEP = data.files.reduce(
    (acc, file) => {
      const ep = file.ep || "UNKNOWN";
      if (!acc[ep]) acc[ep] = [];
      acc[ep].push(file);
      return acc;
    },
    {} as Record<string, LockedPackFileEntry[]>
  );

  const EP_ORDER = ["EP-001", "EP-002", "EP-003", "EP-004", "EP-005"];

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-72 border-r flex flex-col">
        <div className="p-4 border-b">
          <div className="text-xs text-muted-foreground mb-1">
            <Link href="/workspace/cer/governance/run-home" className="hover:underline">
              ← Run Home
            </Link>
          </div>
          <h2 className="text-sm font-semibold font-mono">{projectId}</h2>
          <p className="text-xs text-muted-foreground mt-1">Locked Evidence Pack</p>
        </div>

        {/* Navigation */}
        <div className="p-2 space-y-1 flex-1 overflow-y-auto">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">INTAKE PAGES</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../`}>Intake Status</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../classification`}>Classification Review</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../human-gate`}>Human Gate</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7 bg-primary/10" asChild>
            <Link href={`./`}>Locked Pack</Link>
          </Button>
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1 mt-3">CER REVIEW</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../upload`}>Upload Evidence</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../upload/start-run`}>Start CER Review</Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold">Locked Evidence Pack</h1>
              <p className="text-sm text-muted-foreground">
                Session: {data.intake_session_id}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {data.verified && (
                <Badge variant="outline" className="border-green-300 text-green-700">
                  ✓ Verified
                </Badge>
              )}
              <Button asChild>
                <Link href={`../upload/start-run`}>Start CER Review</Link>
              </Button>
            </div>
          </div>

          {/* Summary Card */}
          <Card className="border-green-200 bg-green-50">
            <CardContent className="pt-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="text-4xl">🔒</div>
                  <div>
                    <div className="text-lg font-bold">Evidence Pack Locked</div>
                    <div className="text-sm text-green-700">
                      {data.total_files} files across {Object.keys(filesByEP).length} evidence
                      packages
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-green-600">Manifest</div>
                  <div className="text-xs font-mono text-green-700">{data.manifest_path}</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* EP Breakdown */}
          <div className="grid grid-cols-5 gap-4">
            {EP_ORDER.map((ep) => {
              const files = filesByEP[ep] || [];
              return (
                <Card key={ep}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">{ep}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{files.length}</div>
                    <div className="text-xs text-muted-foreground">files</div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Files by EP */}
          {EP_ORDER.map((ep) => {
            const files = filesByEP[ep];
            if (!files || files.length === 0) return null;

            return (
              <Card key={ep}>
                <CardHeader>
                  <CardTitle className="text-base">{ep}</CardTitle>
                  <CardDescription>{files.length} files in this evidence package</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {files.map((file, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-3 p-2 bg-gray-50 rounded"
                      >
                        <div className="text-green-600 shrink-0">✓</div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm truncate">{file.relative_path}</div>
                          <div className="text-xs text-muted-foreground font-mono">
                            {file.sha256.slice(0, 16)}...
                          </div>
                        </div>
                        {file.size_bytes && (
                          <div className="text-xs text-muted-foreground shrink-0">
                            {(file.size_bytes / 1024).toFixed(1)} KB
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
