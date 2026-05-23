/** SSE stream event types for CER Authoring real-time sync */

export type StreamStatus =
  | "idle"
  | "connecting"
  | "streaming"
  | "interrupted"
  | "done"
  | "error";

export interface BaseStreamEvent {
  event: string;
  timestamp: string;
}

export interface NodeStartEvent extends BaseStreamEvent {
  event: "node_start";
  node: string;
}

export interface NodeEndEvent extends BaseStreamEvent {
  event: "node_end";
  node: string;
  duration_ms: number;
}

export interface InterruptEvent extends BaseStreamEvent {
  event: "interrupt";
  node: string;
  payload: {
    confirmation_point: string;
    step?: string | number;
    priority?: string;
    message?: string;
  };
}

export interface GateResultEvent extends BaseStreamEvent {
  event: "gate_result";
  node: string;
  gate_id?: string;
  status?: string;
  failure_pattern?: string;
  upstream_node_to_reroute?: string;
}

export interface QuickScanEvent extends BaseStreamEvent {
  event: "quick_scan";
  node: string;
  status: string;
  findings_count: number;
}

export interface LeadDecisionEvent extends BaseStreamEvent {
  event: "lead_decision";
  node: string;
  decisions: Array<{
    stage: string;
    decision?: string;
    status?: string;
  }>;
}

export interface StageUpdateEvent extends BaseStreamEvent {
  event: "stage_update";
  node: string;
  stages: Array<{
    stage: string;
    status: string;
    agent?: string;
  }>;
}

export interface StateSnapshotEvent extends BaseStreamEvent {
  event: "state_snapshot";
  node: string;
  state: Record<string, unknown>;
}

export interface ErrorEvent extends BaseStreamEvent {
  event: "error";
  error: string;
}

export interface DoneEvent extends BaseStreamEvent {
  event: "done";
  reason?: string;
}

export type StreamEvent =
  | NodeStartEvent
  | NodeEndEvent
  | InterruptEvent
  | GateResultEvent
  | QuickScanEvent
  | LeadDecisionEvent
  | StageUpdateEvent
  | StateSnapshotEvent
  | ErrorEvent
  | DoneEvent;

export interface StreamState {
  events: StreamEvent[];
  status: StreamStatus;
  error: Error | null;
  currentNode: string | null;
  interruptPayload: InterruptEvent["payload"] | null;
  gateResults: GateResultEvent[];
  quickScanResults: QuickScanEvent[];
}
