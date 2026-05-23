"use client";

import { useEvidenceLineage } from "@/hooks/use-evidence-lineage";
import { EvidenceChainBreakAlert } from "./evidence-chain-break-alert";

interface EvidenceLineageGraphProps {
  projectId: string | null;
}

const NODE_TYPE_COLORS: Record<string, string> = {
  evidence: "bg-blue-100 text-blue-800 border-blue-200",
  claim: "bg-green-100 text-green-800 border-green-200",
  source: "bg-gray-100 text-gray-800 border-gray-200",
};

export function EvidenceLineageGraph({ projectId }: EvidenceLineageGraphProps) {
  const { lineage, breaks, loading, error } = useEvidenceLineage(projectId);

  if (!projectId) {
    return (
      <div className="p-4 text-sm text-gray-400">
        Select a project to view evidence lineage.
      </div>
    );
  }

  if (loading) {
    return <div className="p-4 text-sm text-gray-500">Loading lineage...</div>;
  }

  if (error) {
    return <div className="p-4 text-sm text-red-600">Error: {error}</div>;
  }

  if (!lineage || lineage.node_count === 0) {
    return (
      <div className="p-4 text-sm text-gray-400">
        No lineage data available. Run evidence appraisal first.
      </div>
    );
  }

  const evidenceNodes = lineage.nodes.filter((n) => n.node_type === "evidence");
  const claimNodes = lineage.nodes.filter((n) => n.node_type === "claim");
  const sourceNodes = lineage.nodes.filter((n) => n.node_type === "source");

  return (
    <div className="space-y-4">
      <EvidenceChainBreakAlert breaks={breaks} />

      {/* Stats */}
      <div className="grid grid-cols-4 gap-2">
        <div className="rounded border bg-white p-2 text-center">
          <div className="text-lg font-bold text-blue-600">{evidenceNodes.length}</div>
          <div className="text-[10px] text-gray-500">Evidence</div>
        </div>
        <div className="rounded border bg-white p-2 text-center">
          <div className="text-lg font-bold text-green-600">{claimNodes.length}</div>
          <div className="text-[10px] text-gray-500">Claims</div>
        </div>
        <div className="rounded border bg-white p-2 text-center">
          <div className="text-lg font-bold text-gray-600">{sourceNodes.length}</div>
          <div className="text-[10px] text-gray-500">Sources</div>
        </div>
        <div className="rounded border bg-white p-2 text-center">
          <div className="text-lg font-bold text-purple-600">{lineage.edge_count}</div>
          <div className="text-[10px] text-gray-500">Links</div>
        </div>
      </div>

      {/* Nodes Table */}
      <div className="rounded border bg-white">
        <div className="border-b px-3 py-2 text-xs font-semibold text-gray-600">
          Nodes ({lineage.node_count})
        </div>
        <div className="max-h-64 overflow-y-auto">
          {lineage.nodes.map((node) => (
            <div
              key={node.id}
              className={`flex items-center gap-2 border-b px-3 py-1.5 text-xs last:border-0 ${NODE_TYPE_COLORS[node.node_type] || ""}`}
            >
              <span className="font-mono font-medium">{node.id}</span>
              <span className="rounded bg-white/50 px-1 text-[10px]">{node.node_type}</span>
              {node.claim_text && (
                <span className="truncate text-gray-600">{String(node.claim_text).slice(0, 60)}</span>
              )}
              {node.pmid && (
                <span className="text-gray-500">PMID:{node.pmid}</span>
              )}
              {node.weight && (
                <span className="rounded bg-white/50 px-1 text-[10px]">{node.weight}</span>
              )}
              {node.evidence_depth && (
                <span className="text-[10px] text-gray-500">{node.evidence_depth}</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Edges Table */}
      <div className="rounded border bg-white">
        <div className="border-b px-3 py-2 text-xs font-semibold text-gray-600">
          Edges ({lineage.edge_count})
        </div>
        <div className="max-h-48 overflow-y-auto">
          {lineage.edges.map((edge, i) => (
            <div key={i} className="flex items-center gap-2 border-b px-3 py-1.5 text-xs last:border-0">
              <span className="font-mono text-blue-700">{edge.source}</span>
              <span className="text-gray-400">→</span>
              <span className="font-mono text-green-700">{edge.target}</span>
              <span className="rounded bg-gray-100 px-1 text-[10px] text-gray-600">{edge.relation}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
