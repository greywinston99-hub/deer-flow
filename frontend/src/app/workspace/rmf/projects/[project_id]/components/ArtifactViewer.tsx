"use client";

import React, { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getBackendBaseURL } from "@/core/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ArtifactSummary {
  recommended_gate?: string;
  overall_risk_level?: string;
  items_reviewed?: number;
  items_passed?: number;
  items_rejected?: number;
  blocking_items?: string[];
  capa_count?: number;
  backflow_candidates?: string[];
  executive_summary?: string;
  key_findings?: string[];
  critical_issues?: string[];
  final_decision?: string;
  decision_rationale?: string;
  conditions?: string[];
  next_steps?: string[];
  sign_off_required?: boolean;
  closure_date?: string;
  packet_type?: string;
  priority?: string;
  actions?: { description: string; status: string }[];
  responsible_parties?: string[];
  due_date?: string;
  status?: string;
  total_items?: number;
  high_priority?: number;
  medium_priority?: number;
  low_priority?: number;
  total_capas?: number;
  open?: unknown[];
  in_progress?: unknown[];
  closed?: unknown[];
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Artifact summary cards
// ---------------------------------------------------------------------------

function SummaryCard({ data }: { data: ArtifactSummary }) {
  const entries = Object.entries(data).filter(([, v]) => v !== undefined && v !== null && v !== "");

  if (entries.length === 0) return null;

  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
      {entries.map(([k, v]) => (
        <React.Fragment key={k}>
          <span className="text-muted-foreground font-medium capitalize">
            {k.replace(/_/g, " ")}:
          </span>
          {Array.isArray(v) ? (
            <span className="text-foreground">{v.length} item(s)</span>
          ) : (
            <span className="text-foreground">{String(v)}</span>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Final report summary
// ---------------------------------------------------------------------------

function FinalReportSummary({ data }: { data: ArtifactSummary }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        {data.recommended_gate && (
          <Badge
            className={
              data.recommended_gate === "pass"
                ? "bg-green-500 text-white"
                : data.recommended_gate === "rework_required"
                ? "bg-red-500 text-white"
                : data.recommended_gate === "conditional_pass"
                ? "bg-amber-500 text-white"
                : "bg-gray-500 text-white"
            }
          >
            {data.recommended_gate}
          </Badge>
        )}
        {data.overall_risk_level && (
          <Badge variant="outline">Risk: {data.overall_risk_level}</Badge>
        )}
      </div>
      {data.executive_summary && (
        <p className="text-xs text-muted-foreground italic border-l-2 border-muted pl-2">
          {data.executive_summary}
        </p>
      )}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-muted rounded p-2">
          <div className="text-lg font-bold">{data.items_reviewed ?? "—"}</div>
          <div className="text-xs text-muted-foreground">Reviewed</div>
        </div>
        <div className="bg-green-50 rounded p-2">
          <div className="text-lg font-bold text-green-700">{data.items_passed ?? "—"}</div>
          <div className="text-xs text-green-600">Passed</div>
        </div>
        <div className="bg-red-50 rounded p-2">
          <div className="text-lg font-bold text-red-700">{data.items_rejected ?? "—"}</div>
          <div className="text-xs text-red-600">Rejected</div>
        </div>
      </div>
      {data.blocking_items && data.blocking_items.length > 0 && (
        <div>
          <div className="text-xs font-medium text-red-600 mb-1">Blocking Items:</div>
          <ul className="text-xs text-red-700 space-y-0.5">
            {data.blocking_items.slice(0, 5).map((item, i) => (
              <li key={i}>• {item}</li>
            ))}
            {data.blocking_items.length > 5 && (
              <li className="text-muted-foreground">…and {data.blocking_items.length - 5} more</li>
            )}
          </ul>
        </div>
      )}
      {data.key_findings && data.key_findings.length > 0 && (
        <div>
          <div className="text-xs font-medium mb-1">Key Findings:</div>
          <ul className="text-xs space-y-0.5">
            {data.key_findings.slice(0, 3).map((f, i) => (
              <li key={i}>• {f}</li>
            ))}
          </ul>
        </div>
      )}
      {data.capa_count !== undefined && (
        <div className="text-xs">
          <span className="text-muted-foreground">CAPAs generated: </span>
          <span className="font-medium">{data.capa_count}</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gate closure summary
// ---------------------------------------------------------------------------

function GateClosureSummary({ data }: { data: ArtifactSummary }) {
  return (
    <div className="space-y-2 text-xs">
      <div className="flex items-center gap-2">
        {data.final_decision && (
          <Badge
            className={
              data.final_decision === "pass"
                ? "bg-green-500 text-white"
                : data.final_decision === "rework_required"
                ? "bg-red-500 text-white"
                : "bg-amber-500 text-white"
            }
          >
            {data.final_decision}
          </Badge>
        )}
        {data.sign_off_required !== undefined && (
          <Badge variant={data.sign_off_required ? "destructive" : "secondary"}>
            {data.sign_off_required ? "Sign-off required" : "No sign-off"}
          </Badge>
        )}
      </div>
      {data.decision_rationale && (
        <p className="text-muted-foreground italic border-l-2 border-muted pl-2">
          {data.decision_rationale}
        </p>
      )}
      {data.conditions && data.conditions.length > 0 && (
        <div>
          <div className="text-xs font-medium mb-1">Conditions:</div>
          <ul className="space-y-0.5">
            {data.conditions.map((c, i) => (
              <li key={i} className="text-muted-foreground">• {c}</li>
            ))}
          </ul>
        </div>
      )}
      {data.next_steps && data.next_steps.length > 0 && (
        <div>
          <div className="text-xs font-medium mb-1">Next Steps:</div>
          <ul className="space-y-0.5">
            {data.next_steps.map((s, i) => (
              <li key={i} className="text-muted-foreground">• {s}</li>
            ))}
          </ul>
        </div>
      )}
      {data.closure_date && (
        <div className="text-muted-foreground">Closure date: {data.closure_date}</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Next action packet summary
// ---------------------------------------------------------------------------

function NextActionPacketSummary({ data }: { data: ArtifactSummary }) {
  return (
    <div className="space-y-2 text-xs">
      <div className="flex items-center gap-2">
        {data.priority && (
          <Badge
            variant={data.priority === "critical" ? "destructive" : "outline"}
          >
            {data.priority}
          </Badge>
        )}
        {data.status && <Badge variant="outline">{data.status}</Badge>}
      </div>
      {data.actions && data.actions.length > 0 && (
        <div>
          <div className="text-xs font-medium mb-1">Actions ({data.actions.length}):</div>
          <ul className="space-y-1">
            {data.actions.slice(0, 5).map((a, i) => (
              <li key={i} className="flex items-start gap-1">
                <Badge
                  variant="outline"
                  className={`text-xs shrink-0 mt-0.5 ${
                    a.status === "open"
                      ? "border-red-400 text-red-600"
                      : a.status === "in_progress"
                      ? "border-blue-400 text-blue-600"
                      : "border-green-400 text-green-600"
                  }`}
                >
                  {a.status}
                </Badge>
                <span className="text-muted-foreground">{a.description}</span>
              </li>
            ))}
            {data.actions.length > 5 && (
              <li className="text-muted-foreground">…and {data.actions.length - 5} more</li>
            )}
          </ul>
        </div>
      )}
      {data.responsible_parties && data.responsible_parties.length > 0 && (
        <div className="text-muted-foreground">
          Owners: {data.responsible_parties.join(", ")}
        </div>
      )}
      {data.due_date && (
        <div className="text-muted-foreground">Due: {data.due_date}</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Human review queue summary
// ---------------------------------------------------------------------------

function HumanReviewQueueSummary({ data }: { data: ArtifactSummary }) {
  return (
    <div className="space-y-2 text-xs">
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-red-50 rounded p-2">
          <div className="text-lg font-bold text-red-700">{data.high_priority ?? 0}</div>
          <div className="text-xs text-red-600">High</div>
        </div>
        <div className="bg-amber-50 rounded p-2">
          <div className="text-lg font-bold text-amber-700">{data.medium_priority ?? 0}</div>
          <div className="text-xs text-amber-600">Medium</div>
        </div>
        <div className="bg-green-50 rounded p-2">
          <div className="text-lg font-bold text-green-700">{data.low_priority ?? 0}</div>
          <div className="text-xs text-green-600">Low</div>
        </div>
      </div>
      {(data.items as unknown[]) && (data.items as unknown[]).length > 0 && (
        <div>
          <div className="text-xs font-medium mb-1">Sample Items:</div>
          <ul className="space-y-0.5">
            {(data.items as unknown[]).slice(0, 5).map((item: unknown, i: number) => {
              const itemObj = item as { id?: string; title?: string; item_id?: string; description?: string };
              const label = itemObj.title || itemObj.id || itemObj.item_id || itemObj.description || String(item);
              return <li key={i} className="text-muted-foreground truncate">• {label}</li>;
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// CAPA action list summary
// ---------------------------------------------------------------------------

function CapaActionListSummary({ data }: { data: ArtifactSummary }) {
  const open = Array.isArray(data.open) ? data.open.length : 0;
  const inProgress = Array.isArray(data.in_progress) ? data.in_progress.length : 0;
  const closed = Array.isArray(data.closed) ? data.closed.length : 0;

  return (
    <div className="space-y-2 text-xs">
      <div className="flex items-center gap-2">
        <Badge variant="outline">Total: {data.total_capas ?? 0}</Badge>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-red-50 rounded p-2">
          <div className="text-lg font-bold text-red-700">{open}</div>
          <div className="text-xs text-red-600">Open</div>
        </div>
        <div className="bg-blue-50 rounded p-2">
          <div className="text-lg font-bold text-blue-700">{inProgress}</div>
          <div className="text-xs text-blue-600">In Progress</div>
        </div>
        <div className="bg-green-50 rounded p-2">
          <div className="text-lg font-bold text-green-700">{closed}</div>
          <div className="text-xs text-green-600">Closed</div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main ArtifactViewer component
// ---------------------------------------------------------------------------

interface ArtifactViewerProps {
  projectId: string;
  cycleId?: string; // undefined = latest
  artifactPath: string;
  artifactName: string;
  open: boolean;
  onClose: () => void;
}

export default function ArtifactViewer({
  projectId,
  cycleId,
  artifactPath,
  artifactName,
  open,
  onClose,
}: ArtifactViewerProps) {
  const [content, setContent] = useState<string | null>(null);
  const [summary, setSummary] = useState<ArtifactSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"summary" | "raw">("summary");

  const isMarkdown = artifactPath.endsWith(".md");
  const isJson = artifactPath.endsWith(".json");

  const fetchArtifact = useCallback(async () => {
    if (!open) return;
    setLoading(true);
    setError(null);
    setContent(null);
    setSummary(null);

    try {
      const base = getBackendBaseURL();
      const cyclePart = cycleId ? `${cycleId}/` : "latest/";
      const url = `${base}/api/rmf/projects/${projectId}/artifacts/${cyclePart}${artifactPath}`;

      const [contentResp, summaryResp] = await Promise.allSettled([
        fetch(url),
        isJson && !cycleId ? fetch(`${url}?summary=true`) : Promise.reject("no summary"),
      ]);

      // Content
      if (contentResp.status === "fulfilled" && contentResp.value.ok) {
        const text = await contentResp.value.text();
        setContent(text);
      } else if (contentResp.status === "rejected") {
        setError(String(contentResp.reason));
      } else if (contentResp.value?.status === 404) {
        setError("Artifact not found");
      } else {
        setError(`HTTP ${contentResp.value?.status ?? "unknown"}`);
      }

      // Summary (only for JSON, latest cycle)
      if (summaryResp.status === "fulfilled" && summaryResp.value.ok) {
        const data = await summaryResp.value.json();
        setSummary(data);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [open, projectId, cycleId, artifactPath, isJson]);

  useEffect(() => {
    fetchArtifact();
  }, [fetchArtifact]);

  // Detect artifact type from name
  const artifactType = artifactName.endsWith(".json")
    ? artifactName.replace(".json", "")
    : null;

  const renderStructuredSummary = () => {
    if (!summary) return null;

    switch (artifactType) {
      case "final_report":
        return <FinalReportSummary data={summary} />;
      case "gate_closure_report":
        return <GateClosureSummary data={summary} />;
      case "next_action_packet":
        return <NextActionPacketSummary data={summary} />;
      case "human_review_queue":
        return <HumanReviewQueueSummary data={summary} />;
      case "capa_action_list":
        return <CapaActionListSummary data={summary} />;
      default:
        return <SummaryCard data={summary} />;
    }
  };

  const renderContent = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          Loading artifact…
        </div>
      );
    }

    if (error) {
      return (
        <div className="text-center py-12 text-red-500 text-sm">
          Failed to load: {error}
        </div>
      );
    }

    if (!content) return null;

    if (isMarkdown) {
      return (
        <div className="prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      );
    }

    if (isJson) {
      if (viewMode === "raw") {
        return (
          <pre className="text-xs overflow-auto bg-muted p-3 rounded font-mono whitespace-pre-wrap">
            {content}
          </pre>
        );
      }
      return (
        <div className="space-y-4">
          {summary && artifactType && renderStructuredSummary()}
          {!summary && (
            <pre className="text-xs overflow-auto bg-muted p-3 rounded font-mono whitespace-pre-wrap">
              {content}
            </pre>
          )}
        </div>
      );
    }

    return (
      <pre className="text-xs overflow-auto bg-muted p-3 rounded font-mono whitespace-pre-wrap">
        {content}
      </pre>
    );
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <DialogTitle className="text-base font-medium">{artifactName}</DialogTitle>
            <div className="flex items-center gap-2">
              {isJson && summary && (
                <div className="flex items-center gap-1 border rounded p-0.5">
                  <button
                    onClick={() => setViewMode("summary")}
                    className={`text-xs px-2 py-0.5 rounded ${
                      viewMode === "summary"
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    Summary
                  </button>
                  <button
                    onClick={() => setViewMode("raw")}
                    className={`text-xs px-2 py-0.5 rounded ${
                      viewMode === "raw"
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    Raw
                  </button>
                </div>
              )}
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  const base = getBackendBaseURL();
                  const cyclePart = cycleId ? `${cycleId}/` : "latest/";
                  window.open(
                    `${base}/api/rmf/projects/${projectId}/artifacts/${cyclePart}${artifactPath}?raw=true`,
                    "_blank",
                  );
                }}
              >
                Download
              </Button>
            </div>
          </div>
        </DialogHeader>
        <div className="flex-1 overflow-auto">{renderContent()}</div>
      </DialogContent>
    </Dialog>
  );
}
