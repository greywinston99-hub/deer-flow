"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useReviewAgents, useReviewAgent, useReviewAgentsEvidence } from "@/core/cer_review/hooks";
import type { AgentInfo, AgentRuntimeEvidence } from "@/core/cer_review/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ArrowLeftIcon,
  ShieldCheckIcon,
  AlertTriangleIcon,
  CheckCircle2Icon,
  XCircleIcon,
  ClockIcon,
} from "lucide-react";

type Domain = "All" | "CER" | "RMF" | "Linkage";

const DOMAINS: Domain[] = ["All", "CER", "RMF", "Linkage"];

function statusIcon(status: string | null) {
  if (!status) return <ClockIcon className="h-4 w-4 text-muted-foreground" />;
  if (status === "completed") return <CheckCircle2Icon className="h-4 w-4 text-green-600" />;
  if (status === "failed" || status === "timeout") return <XCircleIcon className="h-4 w-4 text-red-600" />;
  return <AlertTriangleIcon className="h-4 w-4 text-yellow-600" />;
}

export default function AgentTeamsPage() {
  const [domain, setDomain] = useState<Domain>("All");
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  const { agents, isLoading, error } = useReviewAgents(
    domain === "All" ? undefined : domain,
  );
  const { agent: detail, isLoading: detailLoading } = useReviewAgent(selectedAgent);
  const { evidence, totalTraces, traceSources, isLoading: evidenceLoading } = useReviewAgentsEvidence();

  const evidenceMap = useMemo(() => {
    const map = new Map<string, AgentRuntimeEvidence>();
    for (const e of evidence) {
      map.set(e.agent_name, e);
    }
    return map;
  }, [evidence]);

  const rows = useMemo(() => {
    return agents.map((a) => {
      const ev = evidenceMap.get(a.name);
      return { agent: a, evidence: ev };
    });
  }, [agents, evidenceMap]);

  return (
    <div className="flex h-full">
      {/* ── left sidebar ── */}
      <div className="w-72 border-r flex flex-col bg-background">
        <div className="p-4 border-b">
          <Link href="/workspace/cer/governance/run-home">
            <Button variant="ghost" size="sm" className="mb-2">
              <ArrowLeftIcon className="h-4 w-4 mr-1" />
              Back to Projects
            </Button>
          </Link>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <ShieldCheckIcon className="h-5 w-5" />
            Agent Teams
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            CER/RMF Review Agents &mdash; read-only visibility
          </p>
        </div>

        <div className="p-3 border-b">
          <Tabs value={domain} onValueChange={(v) => setDomain(v as Domain)}>
            <TabsList className="w-full grid grid-cols-4">
              {DOMAINS.map((d) => (
                <TabsTrigger key={d} value={d} className="text-xs">
                  {d}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>

        <ScrollArea className="flex-1">
          {isLoading ? (
            <div className="p-3 space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : error ? (
            <div className="p-4 text-center text-sm text-destructive">
              Failed to load agents.
              <Button variant="outline" size="sm" className="mt-2 block mx-auto">
                Retry
              </Button>
            </div>
          ) : rows.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              No agents found for &ldquo;{domain}&rdquo;
            </div>
          ) : (
            <div className="divide-y">
              {rows.map(({ agent, evidence: ev }) => (
                <button
                  key={agent.name}
                  className={`w-full text-left p-3 hover:bg-accent transition-colors ${
                    selectedAgent === agent.name ? "bg-accent" : ""
                  }`}
                  onClick={() =>
                    setSelectedAgent(
                      selectedAgent === agent.name ? null : agent.name,
                    )
                  }
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium truncate">
                      {agent.name}
                    </span>
                    <span className="flex items-center gap-1">
                      {statusIcon(ev?.last_status ?? null)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 mt-1">
                    <Badge variant="outline" className="text-[10px] px-1 py-0">
                      {agent.category}
                    </Badge>
                    <Badge
                      variant={
                        agent.prompt_loaded ? "default" : "destructive"
                      }
                      className="text-[10px] px-1 py-0"
                    >
                      {agent.prompt_loaded ? "prompt" : "no prompt"}
                    </Badge>
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>

        <div className="p-3 border-t text-xs text-muted-foreground">
          {totalTraces > 0
            ? `${totalTraces} trace dirs found`
            : "NO_EVIDENCE_FOUND"}
          {traceSources.length > 0 && (
            <div className="mt-1 text-[10px] opacity-60">
              source: {traceSources[0]}
            </div>
          )}
        </div>
      </div>

      {/* ── main content ── */}
      <div className="flex-1 overflow-auto p-6">
        {!selectedAgent ? (
          <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
            <ShieldCheckIcon className="h-16 w-16 mb-4 opacity-20" />
            <h3 className="text-lg font-medium">Select an agent</h3>
            <p className="text-sm mt-1 max-w-md">
              Choose a CER or RMF review agent from the sidebar to view its
              configuration, system prompt, and runtime evidence.
            </p>
          </div>
        ) : detailLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-96" />
            <Skeleton className="h-64 w-full" />
          </div>
        ) : detail ? (
          <AgentDetailPanel
            agent={detail}
            evidence={evidenceMap.get(detail.name) ?? null}
          />
        ) : (
          <div className="text-center text-muted-foreground py-12">
            Agent not found.
          </div>
        )}
      </div>
    </div>
  );
}

// ── detail panel ─────────────────────────────────────────────────────────────

function AgentDetailPanel({
  agent,
  evidence,
}: {
  agent: AgentInfo & { full_system_prompt?: string };
  evidence: AgentRuntimeEvidence | null;
}) {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h2 className="text-2xl font-bold">{agent.name}</h2>
        <p className="text-muted-foreground mt-1">{agent.description}</p>
      </div>

      {/* config card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Configuration</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Domain</span>
            <p><Badge variant="outline">{agent.domain}</Badge></p>
          </div>
          <div>
            <span className="text-muted-foreground">Model</span>
            <p>{agent.model}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Max Turns</span>
            <p>{agent.max_turns}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Timeout</span>
            <p>{agent.timeout_seconds}s</p>
          </div>
          <div>
            <span className="text-muted-foreground">Prompt Path</span>
            <p className="font-mono text-xs">
              {agent.prompt_path}
              {agent.prompt_path_source === "derived" && (
                <Badge variant="outline" className="ml-1 text-[10px] px-1 py-0">
                  derived
                </Badge>
              )}
            </p>
          </div>
          {agent.prompt_hash && (
            <div>
              <span className="text-muted-foreground">Prompt Hash</span>
              <p className="font-mono text-[10px] break-all">{agent.prompt_hash}</p>
            </div>
          )}
          <div>
            <span className="text-muted-foreground">Prompt Loaded</span>
            <p>
              {agent.prompt_loaded ? (
                <Badge variant="default" className="text-xs">Loaded</Badge>
              ) : (
                <Badge variant="destructive" className="text-xs">Missing</Badge>
              )}
            </p>
          </div>
          <div className="col-span-2">
            <span className="text-muted-foreground">Tools</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {agent.tools.map((t) => (
                <Badge key={t} variant="secondary" className="text-xs">
                  {t}
                </Badge>
              ))}
            </div>
          </div>
          <div className="col-span-2">
            <span className="text-muted-foreground">Disallowed Tools</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {agent.disallowed_tools.map((t) => (
                <Badge key={t} variant="outline" className="text-xs">
                  {t}
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* prompt card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">System Prompt</CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-64 rounded border bg-muted/50 p-3">
            <pre className="text-xs whitespace-pre-wrap font-mono">
              {agent.prompt_preview || "(empty — no prompt loaded)"}
            </pre>
          </ScrollArea>
          {"full_system_prompt" in agent &&
            agent.full_system_prompt &&
            agent.full_system_prompt.length > agent.prompt_preview.length && (
              <details className="mt-2">
                <summary className="text-xs text-muted-foreground cursor-pointer">
                  Show full prompt ({agent.full_system_prompt.length} chars)
                </summary>
                <ScrollArea className="h-96 mt-2 rounded border bg-muted/50 p-3">
                  <pre className="text-xs whitespace-pre-wrap font-mono">
                    {agent.full_system_prompt}
                  </pre>
                </ScrollArea>
              </details>
            )}
        </CardContent>
      </Card>

      {/* runtime evidence card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Runtime Evidence</CardTitle>
        </CardHeader>
        <CardContent>
          {evidence ? (
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Last Invoked</span>
                <p>{evidence.last_invoked_at ?? "N/A"}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Last Status</span>
                <p className="flex items-center gap-1">
                  {statusIcon(evidence.last_status)}
                  {evidence.last_status ?? "N/A"}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">Duration (ms)</span>
                <p>{evidence.last_duration_ms ?? "N/A"}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Schema Valid</span>
                <p>
                  {evidence.last_schema_valid === null
                    ? "N/A"
                    : evidence.last_schema_valid
                      ? "Yes"
                      : "No"}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">Total Invocations</span>
                <p>{evidence.total_invocations}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Failures</span>
                <p>{evidence.total_failures}</p>
              </div>
              <div className="col-span-2">
                <span className="text-muted-foreground">Trace Source</span>
                <p className="font-mono text-xs">{evidence.trace_source ?? "N/A"}</p>
              </div>
              <div className="col-span-2">
                <span className="text-muted-foreground">Artifact</span>
                <p className="font-mono text-xs break-all">
                  {evidence.last_artifact_path ?? "N/A"}
                </p>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <AlertTriangleIcon className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm font-medium">NO_EVIDENCE_FOUND</p>
              <p className="text-xs mt-1">
                This agent has not been invoked yet, or no trace files exist.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
