"""V5 Semantic Checker Seed — Cross-slot semantic validation with confidence ladder.

Frozen baseline: V5_SEMANTIC_CHECKER_SEED
"""

from __future__ import annotations

import uuid
from typing import Any


# Cross-slot dependency graph: target -> required sources
CROSS_SLOT_RULES: list[dict[str, Any]] = [
    {
        "target": "CER_CEP",
        "requires": ["LITERATURE_SOTA"],
        "gap_type": "semantic_consistency",
        "topic": "CER/CEP lacks literature support",
        "description": "Clinical Evaluation Report/Plan should be supported by Literature or State-of-the-Art evidence.",
        "business_impact": "Clinical argument traceability may be questioned if literature backbone is absent.",
        "blocking_level": "WARNING",
        "recommended_action": "Confirm Literature/SOTA slot is populated or document explicit exemption rationale.",
        "responsible_role": "CER_RMF_REVIEW_LOGIC_QA",
    },
    {
        "target": "GSPR",
        "requires": ["RMF_RISK"],
        "gap_type": "semantic_consistency",
        "topic": "GSPR lacks risk management linkage",
        "description": "General Safety and Performance Requirements should be linked to Risk Management File evidence.",
        "business_impact": "Safety requirement traceability remains incomplete without risk management linkage.",
        "blocking_level": "WARNING",
        "recommended_action": "Confirm RMF slot is populated or explicitly state that GSPR is addressed through alternative means.",
        "responsible_role": "CER_RMF_REVIEW_LOGIC_QA",
    },
    {
        "target": "SSCP",
        "requires": ["CER_CEP", "GSPR"],
        "gap_type": "semantic_consistency",
        "topic": "SSCP lacks clinical or safety backbone",
        "description": "Summary of Safety and Clinical Performance should be supported by both Clinical Evaluation and GSPR evidence.",
        "business_impact": "SSCP claims may be challenged if underlying clinical or safety evidence is missing.",
        "blocking_level": "WARNING",
        "recommended_action": "Populate CER and GSPR slots, or document SSCP limitation explicitly.",
        "responsible_role": "REVIEWER",
    },
    {
        "target": "EQUIVALENCE",
        "requires": ["CER_CEP"],
        "gap_type": "semantic_consistency",
        "topic": "Equivalence claim lacks clinical evaluation support",
        "description": "Equivalence arguments should be grounded in a Clinical Evaluation Report or Plan.",
        "business_impact": "Equivalence-based review boundaries may be rejected without CER backbone.",
        "blocking_level": "WARNING",
        "recommended_action": "Confirm CER slot is present or justify equivalence claim through alternative clinical data.",
        "responsible_role": "REVIEWER",
    },
    {
        "target": "BIOCOMPATIBILITY",
        "requires": ["PERFORMANCE"],
        "gap_type": "semantic_consistency",
        "topic": "Biocompatibility not linked to performance verification",
        "description": "Biocompatibility evaluation is typically part of the broader performance and verification evidence package.",
        "business_impact": "Biocompatibility arguments may appear isolated if not anchored to performance test strategy.",
        "blocking_level": "INFORMATIONAL",
        "recommended_action": "Cross-reference biocompatibility plan with performance verification reports.",
        "responsible_role": "REVIEWER",
    },
    {
        "target": "LABELS_PACKAGING",
        "requires": ["IFU"],
        "gap_type": "semantic_consistency",
        "topic": "Labels/packaging without IFU counterpart",
        "description": "Device labels and packaging should be accompanied by Instructions for Use for regulatory completeness.",
        "business_impact": "Incomplete labeling package may trigger regulatory query.",
        "blocking_level": "INFORMATIONAL",
        "recommended_action": "Confirm IFU is present or justify why standalone labels are acceptable.",
        "responsible_role": "REVIEWER",
    },
]


def _slot_present_and_viable(slot: dict[str, Any]) -> bool:
    """Return True if slot has a candidate with at least LOW confidence."""
    status = slot.get("slot_status", "MISSING")
    band = slot.get("confidence_band", "MISSING")
    return status != "MISSING" and band != "MISSING" and slot.get("candidates")


def run_semantic_checks(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run cross-slot semantic validation and return semantic G-Points."""
    slot_map = {slot["slot_type"]: slot for slot in slots}
    semantic_gaps: list[dict[str, Any]] = []

    for rule in CROSS_SLOT_RULES:
        target_type = rule["target"]
        target_slot = slot_map.get(target_type)

        # Only check semantic rules for slots that ARE present
        if not target_slot or not _slot_present_and_viable(target_slot):
            continue

        missing_required = []
        for req_type in rule["requires"]:
            req_slot = slot_map.get(req_type)
            if not req_slot or not _slot_present_and_viable(req_slot):
                missing_required.append(req_type)

        if missing_required:
            evidence_refs = []
            if target_slot.get("direct_evidence_link"):
                evidence_refs.append(target_slot["direct_evidence_link"])
            for c in target_slot.get("candidates", [])[:2]:
                if c.get("evidence_ref"):
                    evidence_refs.append(c["evidence_ref"])

            semantic_gaps.append(
                {
                    "g_point_id": f"gp-{uuid.uuid4().hex[:8]}",
                    "gap_type": rule["gap_type"],
                    "topic": rule["topic"],
                    "description": f"{rule['description']} Missing required slot(s): {', '.join(missing_required)}.",
                    "evidence_refs": evidence_refs,
                    "business_impact": rule["business_impact"],
                    "blocking_level": rule["blocking_level"],
                    "recommended_action": rule["recommended_action"],
                    "responsible_role": rule["responsible_role"],
                    "workflow_can_continue": "LIMITED" if rule["blocking_level"] in ("BLOCKING", "WARNING") else "YES",
                    "next_action": f"Populate {', '.join(missing_required)} or document limitation",
                    "controlled_hold_reason": None,
                }
            )

    return semantic_gaps


# ── Confidence Ladder ──────────────────────────────────────────────────────────


CONFIDENCE_LADDER_THRESHOLDS = {
    "HIGH": 0.85,
    "MEDIUM": 0.60,
    "LOW": 0.30,
    "MISSING": 0.0,
}


def ladder_band(score: float) -> str:
    """Map a raw confidence score to a confidence ladder band."""
    if score >= CONFIDENCE_LADDER_THRESHOLDS["HIGH"]:
        return "HIGH"
    if score >= CONFIDENCE_LADDER_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    if score >= CONFIDENCE_LADDER_THRESHOLDS["LOW"]:
        return "LOW"
    return "MISSING"


def build_confidence_ladder(slots: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a confidence ladder summary across all slots.

    Returns a dict with:
    - per_slot_ladder: list of {slot_type, current_band, current_score, rungs}
    - aggregate_band: overall workbench confidence band
    - aggregate_score: weighted average score
    - core_complete: whether all core slots are at least MEDIUM
    """
    core_slots = {"IFU", "CER_CEP", "RMF_RISK", "PMCF", "GSPR"}
    per_slot = []
    total_score = 0.0
    total_weight = 0.0

    for slot in slots:
        score = float(slot.get("confidence_score", 0.0))
        band = slot.get("confidence_band", "MISSING")
        slot_type = slot["slot_type"]
        weight = 2.0 if slot_type in core_slots else 1.0

        rungs = []
        for rung_band, threshold in sorted(
            CONFIDENCE_LADDER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True
        ):
            achieved = score >= threshold and band != "MISSING"
            rungs.append(
                {
                    "rung_band": rung_band,
                    "threshold": threshold,
                    "achieved": achieved,
                }
            )

        per_slot.append(
            {
                "slot_type": slot_type,
                "current_band": band,
                "current_score": round(score, 3),
                "rungs": rungs,
            }
        )

        total_score += score * weight
        total_weight += weight

    aggregate_score = round(total_score / max(total_weight, 1.0), 3)
    aggregate_band = ladder_band(aggregate_score)

    core_complete = all(
        s.get("confidence_band") in {"HIGH", "MEDIUM"} and s.get("slot_status") != "MISSING"
        for s in slots
        if s["slot_type"] in core_slots
    )

    return {
        "per_slot_ladder": per_slot,
        "aggregate_band": aggregate_band,
        "aggregate_score": aggregate_score,
        "core_complete": core_complete,
        "ladder_version": "V1_SEED",
    }
