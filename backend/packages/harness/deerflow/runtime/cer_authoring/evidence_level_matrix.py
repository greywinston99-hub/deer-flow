"""WS5: Evidence Level Summary Matrix.

Produces a first-class `evidence_level_summary_matrix` with Oxford/MDCG grading,
pivotal/supportive/background/excluded classification, and conclusion strength
ceilings consumed by writer and review gates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

OXFORD_LEVELS = {
    "systematic_review_rct": "1a",
    "rct": "1b",
    "systematic_review_cohort": "2a",
    "prospective_cohort": "2b",
    "retrospective_cohort": "2b",
    "case_control": "3b",
    "case_series": "4",
    "expert_opinion": "5",
    "narrative_review": "5",
    "in_vitro": "5",
    "animal_study": "5",
}

MDCG_2020_6_LEVELS = {
    "1a": "I",
    "1b": "I",
    "2a": "II",
    "2b": "II",
    "3a": "III",
    "3b": "III",
    "4": "IV",
    "5": "IV",
}

OXFORD_CONCLUSION_CEILING = {
    "1a": "STRONG",
    "1b": "STRONG",
    "2a": "MODERATE",
    "2b": "MODERATE",
    "3a": "CAUTIOUS",
    "3b": "CAUTIOUS",
    "4": "CAUTIOUS",
    "5": "INSUFFICIENT",
}


def _map_oxford_level(study_design: str) -> str:
    design_lower = str(study_design or "").lower().replace(" ", "_").replace("-", "_")
    # Check for exact key matches first
    for key, level in OXFORD_LEVELS.items():
        if key == design_lower:
            return level
    # Check for keyword matches
    if any(kw in design_lower for kw in ["rct", "randomized", "randomised"]):
        return "1b"
    if any(kw in design_lower for kw in ["systematic_review", "meta_analysis", "meta-analysis"]):
        return "1a"
    if any(kw in design_lower for kw in ["prospective_cohort", "cohort"]):
        return "2b"
    if any(kw in design_lower for kw in ["retrospective"]):
        return "2b"
    if any(kw in design_lower for kw in ["case_control"]):
        return "3b"
    if any(kw in design_lower for kw in ["case_series", "case_report"]):
        return "4"
    # Fallback substring matching
    for key, level in OXFORD_LEVELS.items():
        if key in design_lower or design_lower in key:
            return level
    return "5"


def _classify_role(
    evidence: dict[str, Any],
    claims: list[dict[str, Any]],
) -> str:
    """Classify evidence as pivotal, supportive, background, or excluded."""
    source_type = str(evidence.get("source_type") or evidence.get("type") or "").lower()
    oxford = str(evidence.get("oxford_level") or _map_oxford_level(evidence.get("study_design") or ""))
    is_subject = any(kw in source_type for kw in ["subject_device", "clinical_study", "pms", "pmcf"])
    is_direct = bool(evidence.get("direct_evidence") or evidence.get("is_direct"))

    if source_type in {"unknown_unclassified", ""}:
        return "excluded"
    if oxford in {"5"} and not is_subject:
        return "background"
    if is_direct and oxford in {"1a", "1b", "2a", "2b"}:
        return "pivotal"
    if is_direct:
        return "supportive"
    if is_subject:
        return "supportive"
    return "background"


def build_evidence_level_summary_matrix(
    evidence_registry: list[dict[str, Any]] | None = None,
    claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build evidence level summary with role classification and conclusion ceilings."""
    now = datetime.now(timezone.utc).isoformat()
    evidence_registry = evidence_registry or []
    claims = claims or []

    rows: list[dict[str, Any]] = []
    pivotal_count = 0
    supportive_count = 0
    background_count = 0
    excluded_count = 0

    for i, ev in enumerate(evidence_registry):
        eid = str(ev.get("evidence_id") or ev.get("source_id") or f"EV-{i+1:03d}")
        study_design = str(ev.get("study_design") or ev.get("design") or "")
        oxford = _map_oxford_level(study_design)
        mdcg = MDCG_2020_6_LEVELS.get(oxford, "IV")
        role = _classify_role(ev, claims)
        ceiling = OXFORD_CONCLUSION_CEILING.get(oxford, "INSUFFICIENT")

        linked_claims = []
        for claim in claims:
            cid = str(claim.get("claim_id") or "")
            ev_refs = claim.get("evidence_ids") or claim.get("supporting_evidence") or []
            if eid in [str(r) for r in ev_refs]:
                linked_claims.append(cid)

        rows.append({
            "evidence_id": eid,
            "source_type": ev.get("source_type") or ev.get("type") or "",
            "study_design": study_design,
            "sample_size": ev.get("sample_size") or ev.get("n") or "",
            "follow_up": ev.get("follow_up") or ev.get("follow_up_period") or "",
            "oxford_level": oxford,
            "mdcg_2020_6_level": mdcg,
            "role": role,
            "claim_ids_supported": linked_claims,
            "endpoint_ids_supported": ev.get("endpoint_ids") or [],
            "conclusion_strength_ceiling": ceiling,
        })

        if role == "pivotal":
            pivotal_count += 1
        elif role == "supportive":
            supportive_count += 1
        elif role == "background":
            background_count += 1
        else:
            excluded_count += 1

    return {
        "schema": "evidence_level_summary_matrix_v1",
        "generated_at": now,
        "summary": {
            "total_evidence_sources": len(rows),
            "pivotal_count": pivotal_count,
            "supportive_count": supportive_count,
            "background_count": background_count,
            "excluded_count": excluded_count,
            "has_pivotal": pivotal_count > 0,
            "has_supportive": supportive_count > 0,
            "overall_ceiling": (
                "STRONG" if pivotal_count >= 1 and supportive_count >= 1
                else "MODERATE" if pivotal_count >= 1 or supportive_count >= 1
                else "INSUFFICIENT"
            ),
        },
        "rows": rows,
    }
