"use client";

import { useQuery } from "@tanstack/react-query";
import {
  listReviewAgents,
  getReviewAgent,
  getReviewAgentsRuntimeEvidence,
} from "./api";
import type {
  AgentInfo,
  AgentDetailResponse,
  AgentRuntimeEvidence,
} from "./types";

export function useReviewAgents(domain?: string) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["cer-review-agents", domain ?? "all"],
    queryFn: () => listReviewAgents(domain),
  });
  return {
    agents: (data ?? []) as AgentInfo[],
    isLoading,
    error,
  };
}

export function useReviewAgent(name: string | null) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["cer-review-agent", name],
    queryFn: () => getReviewAgent(name!),
    enabled: !!name,
  });
  return {
    agent: (data ?? null) as AgentDetailResponse | null,
    isLoading,
    error,
  };
}

export function useReviewAgentsEvidence() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["cer-review-agents", "runtime-evidence"],
    queryFn: () => getReviewAgentsRuntimeEvidence(),
    staleTime: Infinity,
  });
  return {
    evidence: (data?.agents ?? []) as AgentRuntimeEvidence[],
    totalTraces: data?.total_traces_found ?? 0,
    traceSources: data?.trace_sources ?? [],
    isLoading,
    error,
  };
}
