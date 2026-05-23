"""SSE stream adapter for CER Authoring LangGraph events.

Transforms raw LangGraph `stream_mode="updates"` events into domain-specific
SSE payloads suitable for frontend consumption.
"""

from __future__ import annotations

import json
import logging
import time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AuthoringEventType(str, Enum):
    """Domain-specific event types for CER Authoring SSE stream."""

    NODE_START = "node_start"
    NODE_END = "node_end"
    INTERRUPT = "interrupt"
    GATE_RESULT = "gate_result"
    QUICK_SCAN = "quick_scan"
    STAGE_UPDATE = "stage_update"
    LEAD_DECISION = "lead_decision"
    ERROR = "error"
    DONE = "done"


# Nodes that trigger human interrupts
_INTERRUPT_NODES: set[str] = {
    "device_profile",
    "claim_decomposition",
    "sota_search",
    "evidence_appraisal",
    "endpoint_extraction",
    "claim_sota_alignment",
    "nb_precheck",
}

# Nodes that are hard gates
_GATE_NODES: set[str] = {
    "retrieval_domain_gate",
    "screening_depth_gate",
    "fulltext_basis_gate",
    "sota_endpoint_gate",
    "evidence_sufficiency_gate",
    "claim_evidence_gate",
    "br_justified_gate",
    "alignment_gate",
    "pre_writer_readiness_gate",
}

# Fields to strip from state before sending to frontend
_SENSITIVE_FIELDS: set[str] = {
    "_node_knowledge",
    "subagent_invocation_log",
    "model_provider_preflight",
    "run_scope_audit",
}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def filter_sensitive(state: dict[str, Any]) -> dict[str, Any]:
    """Remove internal/sensitive fields from state before streaming to frontend."""
    return {k: v for k, v in state.items() if k not in _SENSITIVE_FIELDS}


def normalize_event(
    update: dict[str, Any],
    *,
    node_start_times: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    """Convert a single LangGraph update dict into a frontend SSE event.

    Returns None for events that should be dropped (empty updates, internal
    framework events, etc.).
    """
    node_start_times = node_start_times or {}

    # LangGraph updates are keyed by node name
    if len(update) != 1:
        # Multi-node batch — flatten into separate events
        events = []
        for node_name, node_state in update.items():
            single = normalize_event({node_name: node_state}, node_start_times=node_start_times)
            if single:
                events.append(single)
        # Return a synthetic batch event for the caller to yield individually
        if len(events) == 1:
            return events[0]
        return {"event": "batch", "events": events, "timestamp": _now_iso()}

    node_name, node_state = next(iter(update.items()))

    # Skip internal framework nodes
    if node_name in ("__start__", "__end__"):
        return None

    # Skip empty states
    if not node_state:
        return None

    now = time.perf_counter()

    # ── Detect interrupt ──────────────────────────────────────────────────────
    if node_name in _INTERRUPT_NODES:
        # Check if this node produced an interrupt payload
        # In LangGraph, interrupt data is surfaced in the state or via special keys
        # For our graph, interrupt payloads contain "confirmation_point"
        interrupt_payload = _extract_interrupt_payload(node_state)
        if interrupt_payload:
            return {
                "event": AuthoringEventType.INTERRUPT.value,
                "node": node_name,
                "payload": interrupt_payload,
                "timestamp": _now_iso(),
            }

    # ── Detect gate result ────────────────────────────────────────────────────
    if node_name in _GATE_NODES:
        gate_report = _extract_gate_report(node_name, node_state)
        if gate_report:
            return {
                "event": AuthoringEventType.GATE_RESULT.value,
                "node": node_name,
                "gate_id": gate_report.get("gate_id"),
                "status": gate_report.get("status"),
                "failure_pattern": gate_report.get("failure_pattern"),
                "upstream_node_to_reroute": gate_report.get("upstream_node_to_reroute"),
                "timestamp": _now_iso(),
            }

    # ── Detect Quick-Scan completion ──────────────────────────────────────────
    if node_name == "review_quick_scan":
        qs_status = node_state.get("review_quick_scan_status")
        qs_feedback = node_state.get("review_quick_scan_feedback")
        if qs_status and qs_status != "skipped":
            return {
                "event": AuthoringEventType.QUICK_SCAN.value,
                "node": node_name,
                "status": qs_status,
                "findings_count": len(qs_feedback.get("findings", [])) if qs_feedback else 0,
                "timestamp": _now_iso(),
            }

    # ── Detect lead decision ──────────────────────────────────────────────────
    lead_decisions = node_state.get("lead_decisions")
    if lead_decisions:
        return {
            "event": AuthoringEventType.LEAD_DECISION.value,
            "node": node_name,
            "decisions": lead_decisions,
            "timestamp": _now_iso(),
        }

    # ── Detect stage result ───────────────────────────────────────────────────
    stage_results = node_state.get("stage_results")
    if stage_results:
        return {
            "event": AuthoringEventType.STAGE_UPDATE.value,
            "node": node_name,
            "stages": stage_results,
            "timestamp": _now_iso(),
        }

    # ── Generic node_start / node_end ─────────────────────────────────────────
    # Track start time on first sight of node
    if node_name not in node_start_times:
        node_start_times[node_name] = now
        return {
            "event": AuthoringEventType.NODE_START.value,
            "node": node_name,
            "timestamp": _now_iso(),
        }

    # If we've seen this node before, treat as node_end
    duration_ms = round((now - node_start_times[node_name]) * 1000, 1)
    # Remove from tracking so next occurrence is treated as start again
    del node_start_times[node_name]

    return {
        "event": AuthoringEventType.NODE_END.value,
        "node": node_name,
        "duration_ms": duration_ms,
        "timestamp": _now_iso(),
    }


def _extract_interrupt_payload(state: dict[str, Any]) -> dict[str, Any] | None:
    """Extract interrupt payload from node state if present."""
    # In our graph, interrupt data is not directly in state — it's produced
    # by langgraph.types.interrupt() and surfaced via checkpoint.
    # We approximate by looking for fields that indicate an interrupt
    # was the last action in this node.
    if state.get("confirmation_point"):
        return {
            "confirmation_point": state.get("confirmation_point"),
            "step": state.get("step"),
            "priority": state.get("priority"),
            "message": state.get("message"),
        }
    return None


def _extract_gate_report(node_name: str, state: dict[str, Any]) -> dict[str, Any] | None:
    """Extract gate report from node state."""
    report_key = f"{node_name}_report"
    report = state.get(report_key)
    if report and isinstance(report, dict):
        return report
    # Fallback: check gate_routing_trace
    trace = state.get("gate_routing_trace")
    if trace and isinstance(trace, list) and trace:
        return trace[-1]
    return None


def serialize_sse_event(event: dict[str, Any]) -> str:
    """Serialize an event dict into SSE `data:` format."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
