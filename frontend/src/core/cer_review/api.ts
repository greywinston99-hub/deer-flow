import { getBackendBaseURL } from "@/core/config";
import type {
  AgentInfo,
  AgentDetailResponse,
  RuntimeEvidenceResponse,
} from "./types";

export async function listReviewAgents(
  domain?: string,
): Promise<AgentInfo[]> {
  const url = new URL(
    `${getBackendBaseURL()}/api/cer-review/agents`,
    window.location.origin,
  );
  if (domain) url.searchParams.set("domain", domain);
  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(`Failed to load review agents: ${res.statusText}`);
  }
  const data = await res.json();
  return (data as { agents: AgentInfo[] }).agents;
}

export async function getReviewAgent(
  name: string,
): Promise<AgentDetailResponse> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/cer-review/agents/${encodeURIComponent(name)}`,
  );
  if (!res.ok) {
    if (res.status === 404) throw new Error(`Agent '${name}' not found`);
    throw new Error(`Failed to load agent: ${res.statusText}`);
  }
  return res.json() as Promise<AgentDetailResponse>;
}

export async function getReviewAgentsRuntimeEvidence(): Promise<RuntimeEvidenceResponse> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/cer-review/agents/runtime-evidence`,
  );
  if (!res.ok) {
    throw new Error(
      `Failed to load runtime evidence: ${res.statusText}`,
    );
  }
  return res.json() as Promise<RuntimeEvidenceResponse>;
}
