"use client";

import { useCallback, useEffect, useState } from "react";

const BASE = () => {
  if (typeof window === "undefined") return "";
  return process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "";
};

export interface LineageNode {
  id: string;
  node_type: string;
  [key: string]: unknown;
}

export interface LineageEdge {
  source: string;
  target: string;
  relation: string;
  [key: string]: unknown;
}

export interface ChainBreak {
  type: string;
  severity: string;
  message: string;
  evidence_id?: string;
  claim_id?: string;
}

export interface LineageData {
  schema: string;
  exported_at: string;
  node_count: number;
  edge_count: number;
  nodes: LineageNode[];
  edges: LineageEdge[];
  chain_breaks: ChainBreak[];
}

export function useEvidenceLineage(projectId: string | null) {
  const [lineage, setLineage] = useState<LineageData | null>(null);
  const [breaks, setBreaks] = useState<ChainBreak[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchLineage = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(
        `${BASE()}/api/cer-knowledge-assets/lineage/${encodeURIComponent(projectId)}`
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = (await r.json()) as LineageData;
      setLineage(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const fetchBreaks = useCallback(async () => {
    if (!projectId) return;
    try {
      const r = await fetch(
        `${BASE()}/api/cer-knowledge-assets/lineage/${encodeURIComponent(projectId)}/breaks`
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setBreaks(data.breaks || []);
    } catch (e) {
      console.warn("Failed to fetch chain breaks:", e);
    }
  }, [projectId]);

  useEffect(() => {
    fetchLineage();
    fetchBreaks();
  }, [fetchLineage, fetchBreaks]);

  return { lineage, breaks, loading, error, refresh: fetchLineage };
}
