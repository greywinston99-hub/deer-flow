"use client";

import React, { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import ArtifactViewer from "./ArtifactViewer";

interface ReviewCycle {
  cycle_id: string;
  cycle_number: number;
  thread_id: string;
  run_id: string | null;
  machine_recommendation: string | null;
  human_decision: string | null;
  final_gate: string | null;
  status: string;
}

interface RoundComparisonProps {
  projectId: string;
  cycles: ReviewCycle[];
  latestMachineRecommendation: string | null;
  latestHumanDecision: string | null;
  latestGateStatus: string | null;
}

function gateColor(gate: string | null | undefined): string {
  if (!gate) return "bg-gray-100 text-gray-600";
  switch (gate) {
    case "pass":
      return "bg-green-100 text-green-800";
    case "rework_required":
      return "bg-red-100 text-red-800";
    case "conditional_pass":
      return "bg-amber-100 text-amber-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
}

function gateLabel(gate: string | null | undefined): string {
  if (!gate) return "—";
  switch (gate) {
    case "pass":
      return "PASS";
    case "rework_required":
      return "REWORK";
    case "conditional_pass":
      return "CONDITIONAL";
    default:
      return gate;
  }
}

function GateComparisonRow({
  label,
  current,
  previous,
}: {
  label: string;
  current: string | null;
  previous: string | null;
}) {
  const changed = current !== previous;
  const improved =
    (current === "pass" && previous !== "pass") ||
    (current === "conditional_pass" && previous === "rework_required");
  const degraded =
    (current === "rework_required" && previous !== "rework_required") ||
    (current === "conditional_pass" && previous === "pass");

  return (
    <div className="grid grid-cols-3 gap-2 items-center text-xs">
      <div className="text-muted-foreground font-medium">{label}</div>
      <div className="flex justify-center">
        {current ? (
          <Badge className={`${gateColor(current)} text-xs`}>{gateLabel(current)}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </div>
      <div className="flex justify-center items-center gap-1">
        {previous ? (
          <Badge className={`${gateColor(previous)} text-xs`}>{gateLabel(previous)}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
        {changed && (
          <span className={`text-xs ${improved ? "text-green-600" : degraded ? "text-red-600" : "text-muted-foreground"}`}>
            {improved ? "↑" : degraded ? "↓" : "~"}
          </span>
        )}
      </div>
    </div>
  );
}

function RoundCard({
  projectId,
  cycle,
  isLatest,
}: {
  projectId: string;
  cycle: ReviewCycle;
  isLatest: boolean;
}) {
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerPath, setViewerPath] = useState("");
  const [viewerName, setViewerName] = useState("");

  const openArtifact = (path: string, name: string) => {
    setViewerPath(path);
    setViewerName(name);
    setViewerOpen(true);
  };

  const isBlocked = cycle.status === "rework_pending";
  const isCompleted = cycle.status === "completed";

  const keyArtifacts = [
    { path: "06_final/final_report.json", label: "Final Report" },
    { path: "07_gate_closure/gate_closure_report.json", label: "Gate Closure" },
    { path: "07_gate_closure/next_action_packet.json", label: "Next Actions" },
    { path: "05_human_boundary/human_review_queue.json", label: "Review Queue" },
    { path: "06_final/capa_action_list.json", label: "CAPA List" },
  ];

  return (
    <>
      <div
        className={`border rounded-lg p-4 space-y-3 ${
          isLatest ? "border-primary shadow-sm" : "border-muted"
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm">Round {cycle.cycle_number}</span>
            <Badge variant="outline" className="text-xs">{cycle.cycle_id}</Badge>
            {isLatest && <Badge className="bg-primary text-white text-xs">LATEST</Badge>}
          </div>
          <div className="flex items-center gap-1">
            {isBlocked && <Badge className="bg-red-500 text-white text-xs">BLOCKED</Badge>}
            {isCompleted && !isBlocked && <Badge className="bg-green-500 text-white text-xs">COMPLETED</Badge>}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="bg-muted/50 rounded p-2">
            <div className="text-xs text-muted-foreground mb-1">Machine</div>
            <Badge className={`${gateColor(cycle.machine_recommendation)} text-xs`}>
              {gateLabel(cycle.machine_recommendation)}
            </Badge>
          </div>
          <div className="bg-muted/50 rounded p-2">
            <div className="text-xs text-muted-foreground mb-1">Human</div>
            <Badge className={`${gateColor(cycle.human_decision)} text-xs`}>
              {gateLabel(cycle.human_decision)}
            </Badge>
          </div>
          <div className="bg-muted/50 rounded p-2">
            <div className="text-xs text-muted-foreground mb-1">Final Gate</div>
            <Badge className={`${gateColor(cycle.final_gate)} text-xs`}>
              {gateLabel(cycle.final_gate)}
            </Badge>
          </div>
        </div>

        <div className="text-xs text-muted-foreground">
          Thread: <code className="text-xs">{cycle.thread_id}</code>
          {cycle.run_id && <> | Run: <code className="text-xs">{cycle.run_id}</code></>}
        </div>

        {isLatest && (
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">Key Artifacts</div>
            <div className="flex flex-wrap gap-1">
              {keyArtifacts.map((a) => (
                <Button
                  key={a.path}
                  size="sm"
                  variant="outline"
                  className="text-xs h-6 px-2"
                  onClick={() => openArtifact(a.path, a.label)}
                >
                  {a.label}
                </Button>
              ))}
            </div>
          </div>
        )}
      </div>

      <ArtifactViewer
        projectId={projectId}
        cycleId={cycle.cycle_id}
        artifactPath={viewerPath}
        artifactName={viewerName}
        open={viewerOpen}
        onClose={() => setViewerOpen(false)}
      />
    </>
  );
}

export default function RoundComparison({
  projectId,
  cycles,
  latestMachineRecommendation,
  latestHumanDecision,
  latestGateStatus,
}: RoundComparisonProps) {
  if (cycles.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-4 text-center">
        No cycles yet.
      </div>
    );
  }

  const sorted = [...cycles].sort((a, b) => a.cycle_number - b.cycle_number);
  const latest = sorted[sorted.length - 1]!;
  const previous = sorted.length > 1 ? sorted[sorted.length - 2] : null;

  return (
    <div className="space-y-4">
      <div className="text-xs text-muted-foreground">
        Showing {sorted.length} round(s)
      </div>

      <div className="grid grid-cols-1 gap-3">
        {sorted.map((c) => (
          <RoundCard
            key={c.cycle_id}
            projectId={projectId}
            cycle={c}
            isLatest={c.cycle_id === latest.cycle_id}
          />
        ))}
      </div>

      {previous && latest.cycle_number > 0 && (
        <div className="border rounded-lg p-4 space-y-2 bg-muted/30">
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
            Round {latest.cycle_number} vs Round {previous.cycle_number} — Gate Comparison
          </div>
          <div className="grid grid-cols-3 gap-2 items-center text-xs mb-1">
            <div />
            <div className="text-center font-medium text-muted-foreground">Round {latest.cycle_number} (Current)</div>
            <div className="text-center font-medium text-muted-foreground">Round {previous.cycle_number} (Previous)</div>
          </div>
          <GateComparisonRow label="Machine Rec" current={latest.machine_recommendation} previous={previous.machine_recommendation} />
          <GateComparisonRow label="Human Decision" current={latest.human_decision} previous={previous.human_decision} />
          <GateComparisonRow label="Final Gate" current={latest.final_gate} previous={previous.final_gate} />
        </div>
      )}

      {latestMachineRecommendation === "rework_required" && (
        <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-700">
          <strong>Current gate:</strong> Machine recommends <strong>rework_required</strong>.
          {latestHumanDecision === "rework_required"
            ? " Human reviewer agreed — rework is mandatory."
            : latestHumanDecision === "conditional_pass"
            ? " Human reviewer issued conditional pass — CAPAs required."
            : " Awaiting human decision."}
        </div>
      )}
      {latestMachineRecommendation === "pass" && (
        <div className="bg-green-50 border border-green-200 rounded p-3 text-xs text-green-700">
          <strong>Current gate:</strong> Machine recommends <strong>pass</strong>.
          {latestHumanDecision === "pass" ? " Human reviewer agreed — ready for closure." : " Awaiting human review."}
        </div>
      )}
      {latestMachineRecommendation === "conditional_pass" && (
        <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs text-amber-700">
          <strong>Current gate:</strong> Machine recommends <strong>conditional_pass</strong>.
          {latestHumanDecision ? ` Human reviewer issued ${latestHumanDecision}.` : " Awaiting human decision."}
        </div>
      )}
    </div>
  );
}
