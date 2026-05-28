"""WS2: Formal IFU Iteration Loop.

Turns IFU feedback suggestions into a controlled workflow with version/scope/
claim delta tracking.  Produces `ifu_iteration_decision_ledger.json` and
`ifu_claim_scope_delta_matrix`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_ifu_iteration_ledger(
    state: dict[str, Any],
    ifu_feedback: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build formal IFU iteration decision ledger.

    Tracks IFU version, scope changes, claim deltas, and whether each
    iteration item has been closed or is pending manufacturer input.
    """
    now = datetime.now(timezone.utc).isoformat()
    ifu_feedback = ifu_feedback or state.get("ifu_feedback_suggestions") or []
    ifu_facts = state.get("ifu_fact_table") or {}
    preflight = state.get("source_preflight_gate_report") or {}
    claims = state.get("claim_ledger") or []

    decisions: list[dict[str, Any]] = []
    claim_deltas: list[dict[str, Any]] = []

    for i, fb in enumerate(ifu_feedback):
        fb_type = str(fb.get("type") or fb.get("feedback_type") or "")
        decisions.append({
            "iteration_id": f"IFU-ITER-{i+1:03d}",
            "feedback_type": fb_type,
            "description": str(fb.get("description") or fb.get("message") or "")[:300],
            "source_section": str(fb.get("ifu_section") or fb.get("source") or ""),
            "severity": str(fb.get("severity") or "major"),
            "action_required": str(fb.get("recommended_action") or fb.get("action") or "manufacturer_review"),
            "status": str(fb.get("status") or "open"),
            "blocks_writer": fb_type in {"overclaim", "version_conflict"},
            "created_at": now,
        })

    for claim in claims:
        claim_type = str(claim.get("claim_type") or "").lower()
        if "ifu" in claim_type or "warning" in claim_type:
            claim_deltas.append({
                "claim_id": str(claim.get("claim_id") or ""),
                "claim_text": str(claim.get("claim_text") or "")[:200],
                "ifu_reference": str(claim.get("ifu_reference") or claim.get("source_section") or ""),
                "delta_type": "scope_aligned" if claim.get("final_body_allowed") else "scope_gap",
                "aligned_with_ifu": bool(claim.get("final_body_allowed")),
            })

    has_overclaim = any(d["blocks_writer"] and d["feedback_type"] == "overclaim" for d in decisions)
    has_missing_cb = any(d["feedback_type"] == "missing_clinical_benefit" for d in decisions)
    all_closed = all(d["status"] == "closed" for d in decisions)
    open_blockers = [d["iteration_id"] for d in decisions if d["blocks_writer"] and d["status"] != "closed"]

    return {
        "schema": "ifu_iteration_decision_ledger_v1",
        "generated_at": now,
        "ifu_iteration_decision_ledger": {
            "total_iterations": len(decisions),
            "open_count": sum(1 for d in decisions if d["status"] != "closed"),
            "closed_count": sum(1 for d in decisions if d["status"] == "closed"),
            "blocker_count": sum(1 for d in decisions if d["blocks_writer"]),
            "all_closed": all_closed,
            "has_overclaim": has_overclaim,
            "has_missing_clinical_benefit": has_missing_cb,
            "open_blockers": open_blockers,
            "decisions": decisions,
        },
        "ifu_claim_scope_delta_matrix": {
            "total_claims_with_ifu_reference": len(claim_deltas),
            "aligned_count": sum(1 for d in claim_deltas if d["aligned_with_ifu"]),
            "gap_count": sum(1 for d in claim_deltas if not d["aligned_with_ifu"]),
            "deltas": claim_deltas,
        },
        "ifu_fact_table": ifu_facts,
        "preflight_status": preflight.get("status") or preflight.get("gate_status") or "unknown",
    }
