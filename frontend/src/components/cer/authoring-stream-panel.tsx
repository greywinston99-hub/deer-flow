"use client";

import { useMemo } from "react";
import { useAuthoringStream } from "@/hooks/use-authoring-stream";
import type {
  GateResultEvent,
  QuickScanEvent,
  StreamEvent,
} from "@/core/cer_auth/stream_types";

interface AuthoringStreamPanelProps {
  threadId: string | null;
  className?: string;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  idle: { label: "Idle", color: "text-gray-500" },
  connecting: { label: "Connecting...", color: "text-blue-500" },
  streaming: { label: "Running", color: "text-green-500" },
  interrupted: { label: "Awaiting Input", color: "text-amber-500" },
  done: { label: "Complete", color: "text-gray-500" },
  error: { label: "Error", color: "text-red-500" },
};

const NODE_LABELS: Record<string, string> = {
  initialize: "Initialize",
  device_profile: "Device Profile",
  claim_decomposition: "Claim Decomposition",
  pico_derivation: "PICO Derivation",
  methodology_review: "Methodology Review",
  sota_search: "SOTA Search",
  retrieval_domain_gate: "Retrieval Domain Gate",
  literature_screening: "Literature Screening",
  screening_depth_gate: "Screening Depth Gate",
  evidence_appraisal: "Evidence Appraisal",
  fulltext_basis_gate: "Full-Text Basis Gate",
  endpoint_extraction: "Endpoint Extraction",
  sota_endpoint_gate: "SOTA Endpoint Gate",
  claim_evidence_matrix: "Claim-Evidence Matrix",
  claim_evidence_gate: "Claim-Evidence Gate",
  gap_pmcf: "Gap/PMCF",
  pre_writer_readiness_gate: "Pre-Writer Readiness Gate",
  cer_writing: "CER Writing",
  review_quick_scan: "Quick-Scan Review",
};

export function AuthoringStreamPanel({
  threadId,
  className = "",
}: AuthoringStreamPanelProps) {
  const {
    events,
    status,
    error,
    currentNode,
    interruptPayload,
    gateResults,
    quickScanResults,
  } = useAuthoringStream(threadId);

  const statusMeta = STATUS_LABELS[status] || STATUS_LABELS.idle;

  const nodeTimeline = useMemo(() => {
    const timeline: Array<{
      node: string;
      label: string;
      status: "pending" | "running" | "done" | "blocked";
      durationMs?: number;
    }> = [];

    const pipelineNodes = Object.keys(NODE_LABELS);
    const completed = new Set<string>();
    const blocked = new Set<string>();

    for (const ev of events) {
      if (ev.event === "node_end") {
        completed.add(ev.node);
      }
      if (ev.event === "gate_result" && ev.status === "REWORK_REQUIRED") {
        blocked.add(ev.node);
      }
      if (ev.event === "gate_result" && ev.status === "PASS") {
        blocked.delete(ev.node);
      }
    }

    for (const node of pipelineNodes) {
      let nodeStatus: "pending" | "running" | "done" | "blocked" = "pending";
      if (completed.has(node)) {
        nodeStatus = "done";
      } else if (blocked.has(node)) {
        nodeStatus = "blocked";
      } else if (currentNode === node) {
        nodeStatus = "running";
      }
      timeline.push({
        node,
        label: NODE_LABELS[node] || node,
        status: nodeStatus,
      });
    }

    return timeline;
  }, [events, currentNode]);

  const latestEvents = useMemo(() => events.slice(-10).reverse(), [events]);

  if (!threadId) {
    return (
      <div className={`p-4 text-sm text-gray-400 ${className}`}>
        Select a project to view real-time authoring progress.
      </div>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Status Header */}
      <div className="flex items-center justify-between rounded-lg border bg-white p-3">
        <div className="flex items-center gap-2">
          <div
            className={`h-2.5 w-2.5 rounded-full ${
              status === "streaming"
                ? "animate-pulse bg-green-500"
                : status === "interrupted"
                ? "bg-amber-500"
                : status === "error"
                ? "bg-red-500"
                : "bg-gray-400"
            }`}
          />
          <span className="text-sm font-medium text-gray-700">
            {statusMeta.label}
          </span>
          {currentNode && (
            <span className="text-xs text-gray-500">
              ({NODE_LABELS[currentNode] || currentNode})
            </span>
          )}
        </div>
        <div className="text-xs text-gray-400">
          {events.length} event{events.length !== 1 ? "s" : ""}
        </div>
      </div>

      {/* Interrupt Banner */}
      {interruptPayload && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <div className="text-xs font-semibold text-amber-700">
            ⚠️ Human Input Required
          </div>
          <div className="mt-1 text-sm text-amber-800">
            {interruptPayload.message || `Confirm ${interruptPayload.confirmation_point}`}
          </div>
          <div className="mt-1 text-xs text-amber-600">
            Step: {interruptPayload.step} · Priority: {interruptPayload.priority}
          </div>
        </div>
      )}

      {/* Quick-Scan Toast */}
      {quickScanResults.length > 0 && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
          <div className="text-xs font-semibold text-blue-700">
            🔍 Quick-Scan Complete
          </div>
          {quickScanResults.map((qs: QuickScanEvent, i) => (
            <div key={i} className="mt-1 text-sm text-blue-800">
              {qs.findings_count} finding{qs.findings_count !== 1 ? "s" : ""} detected
              {qs.status.startsWith("failed") && (
                <span className="text-red-600"> (failed: {qs.status})</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Gate Results */}
      {gateResults.length > 0 && (
        <div className="space-y-1">
          {gateResults.slice(-3).map((g: GateResultEvent, i) => (
            <div
              key={i}
              className={`rounded-md px-2 py-1.5 text-xs ${
                g.status === "PASS"
                  ? "border border-green-200 bg-green-50 text-green-700"
                  : g.status === "REWORK_REQUIRED"
                  ? "border border-red-200 bg-red-50 text-red-700"
                  : "border border-gray-200 bg-gray-50 text-gray-700"
              }`}
            >
              <span className="font-medium">{g.gate_id || g.node}</span>: {g.status}
              {g.failure_pattern && (
                <span className="ml-1 text-gray-500">({g.failure_pattern})</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pipeline Timeline */}
      <div className="rounded-lg border bg-white p-3">
        <div className="mb-2 text-xs font-semibold text-gray-500">
          Pipeline Progress
        </div>
        <div className="space-y-1">
          {nodeTimeline.map((item) => (
            <div key={item.node} className="flex items-center gap-2">
              <div
                className={`h-1.5 w-1.5 rounded-full ${
                  item.status === "done"
                    ? "bg-green-500"
                    : item.status === "running"
                    ? "animate-pulse bg-blue-500"
                    : item.status === "blocked"
                    ? "bg-red-400"
                    : "bg-gray-200"
                }`}
              />
              <span
                className={`text-xs ${
                  item.status === "done"
                    ? "text-gray-500 line-through"
                    : item.status === "running"
                    ? "font-medium text-blue-700"
                    : item.status === "blocked"
                    ? "text-red-600"
                    : "text-gray-400"
                }`}
              >
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <div className="font-medium">Connection Error</div>
          <div className="text-xs">{error.message}</div>
        </div>
      )}

      {/* Event Log (collapsible) */}
      <details className="rounded-lg border bg-white">
        <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-gray-600">
          Event Log ({latestEvents.length} recent)
        </summary>
        <div className="max-h-48 overflow-y-auto px-3 pb-2">
          {latestEvents.map((ev: StreamEvent, i) => (
            <div key={i} className="border-b border-gray-100 py-1 text-xs text-gray-500 last:border-0">
              <span className="font-medium text-gray-700">{ev.event}</span>
              {"node" in ev && ev.node && (
                <span className="ml-1 text-gray-400">({ev.node})</span>
              )}
              <span className="ml-1 text-gray-300">
                {new Date(ev.timestamp).toLocaleTimeString()}
              </span>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
