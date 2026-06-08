export interface AgentInfo {
  name: string;
  domain: string;
  category: string;
  description: string;
  role: string;
  model: string;
  tools: string[];
  disallowed_tools: string[];
  max_turns: number;
  timeout_seconds: number;
  prompt_loaded: boolean;
  prompt_path: string;
  prompt_path_source: "explicit" | "derived";
  prompt_hash: string | null;
  prompt_preview: string;
  registered: boolean;
}

export interface AgentDetailResponse extends AgentInfo {
  full_system_prompt: string;
}

export interface AgentRuntimeEvidence {
  agent_name: string;
  last_invoked_at: string | null;
  last_status: string | null;
  last_duration_ms: number | null;
  last_schema_valid: boolean | null;
  last_artifact_path: string | null;
  total_invocations: number;
  total_failures: number;
  trace_source: string | null;
}

export interface RuntimeEvidenceResponse {
  agents: AgentRuntimeEvidence[];
  total_traces_found: number;
  trace_sources: string[];
  evidence_source: "persistent_evidence" | "thread_runtime" | "no_evidence";
}
