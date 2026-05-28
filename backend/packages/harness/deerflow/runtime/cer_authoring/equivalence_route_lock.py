"""WS7: Equivalence Route Lock.

Makes equivalence route decisions explicit and irreversible before evidence
writing. Prevents the system from silently claiming equivalence when evidence
is insufficient.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

ALLOWED_EQUIVALENCE_DECISIONS = [
    "equivalence_not_claimed",
    "full_equivalence_claimed",
    "similar_device_background_only",
    "customer_risk_accepted_data_gap",
]


def build_equivalence_route_lock(
    state: dict[str, Any],
    equivalence_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Determine and lock the equivalence route before evidence writing.

    The decision is based on:
    - Whether similar devices exist in the market
    - Whether clinical data from similar devices will be referenced
    - Whether technical/biological/clinical equivalence matrices are complete
    - Manufacturer risk acceptance for data gaps
    """
    now = datetime.now(timezone.utc).isoformat()
    eq_data = equivalence_data or state.get("equivalence_comparison_matrix") or {}
    device_profile = state.get("device_profile") or {}
    claims = state.get("claim_ledger") or []
    manufacturer_intake = state.get("manufacturer_intake_report") or {}

    similar_devices = eq_data.get("similar_devices") or state.get("similar_devices") or []
    has_similar = len(similar_devices) > 0
    plans_to_reference = bool(eq_data.get("reference_clinical_data") or state.get("reference_similar_device_data"))

    technical_matrix = eq_data.get("technical_equivalence") or {}
    biological_matrix = eq_data.get("biological_equivalence") or {}
    clinical_matrix = eq_data.get("clinical_equivalence") or {}

    tech_complete = bool(technical_matrix.get("rows") or technical_matrix.get("comparison_complete"))
    bio_complete = bool(biological_matrix.get("rows") or biological_matrix.get("comparison_complete"))
    clin_complete = bool(clinical_matrix.get("rows") or clinical_matrix.get("comparison_complete"))
    all_matrices_complete = tech_complete and bio_complete and clin_complete

    manufacturer_risk_accept = bool(
        manufacturer_intake.get("confirmed_fields", {}).get("data_gap_risk_accepted")
        or state.get("customer_risk_accepted_data_gap")
    )

    if not has_similar:
        decision = "equivalence_not_claimed"
        reason = "No similar device identified in the market."
    elif plans_to_reference and all_matrices_complete:
        decision = "full_equivalence_claimed"
        reason = "Similar device identified, clinical data will be referenced, and technical/biological/clinical equivalence matrices are complete."
    elif has_similar and not plans_to_reference:
        decision = "similar_device_background_only"
        reason = "Similar device exists but clinical data will NOT be referenced; similarity comparison is for background context only."
    elif plans_to_reference and not all_matrices_complete and manufacturer_risk_accept:
        decision = "customer_risk_accepted_data_gap"
        reason = "Clinical data from similar device will be referenced but equivalence matrices are incomplete; manufacturer has accepted the data gap risk."
    elif plans_to_reference and not all_matrices_complete:
        decision = "equivalence_not_claimed"
        reason = "Equivalence matrices are incomplete and manufacturer has NOT accepted the data gap risk; equivalence cannot be claimed."
    else:
        decision = "equivalence_not_claimed"
        reason = "Equivalence route could not be established with current evidence."

    return {
        "schema": "equivalence_route_lock_v1",
        "generated_at": now,
        "decision": decision,
        "decision_reason": reason,
        "similar_devices_count": len(similar_devices),
        "similar_device_ids": [str(d.get("device_id") or d.get("name") or "") for d in similar_devices],
        "plans_to_reference_clinical_data": plans_to_reference,
        "matrices_status": {
            "technical_equivalence_complete": tech_complete,
            "biological_equivalence_complete": bio_complete,
            "clinical_equivalence_complete": clin_complete,
            "all_complete": all_matrices_complete,
        },
        "manufacturer_risk_acceptance": manufacturer_risk_accept,
        "equivalence_claimed": decision == "full_equivalence_claimed",
        "equivalence_closed": decision == "full_equivalence_claimed" and all_matrices_complete,
        "writer_instruction": _writer_instruction(decision),
    }


def _writer_instruction(decision: str) -> str:
    if decision == "equivalence_not_claimed":
        return "Writer must explicitly state: 'Equivalence is not claimed for the device under evaluation.' Provide justification."
    elif decision == "full_equivalence_claimed":
        return "Writer may use data from the equivalent device. Must reference technical/biological/clinical matrices."
    elif decision == "similar_device_background_only":
        return "Writer may describe similar devices in SOTA background. Must NOT use similar device data to support claims."
    elif decision == "customer_risk_accepted_data_gap":
        return "Writer must record that manufacturer accepted data gap risk. Final wording must be limited to 'controlled draft limitation only.'"
    return ""
