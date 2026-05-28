"""Deterministic RMF/PMS/PMCF crosswalk helpers for CER authoring."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_rmf_crosswalk(state: dict[str, Any], risk_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build conservative risk/benefit/PMCF closure artifacts.

    The output is designed for gates and writer input packets. It does not
    invent RMF acceptability; absent RMF or PMS/PMCF data remains a controlled
    gap or blocker depending on the consuming gate.
    """
    has_rmf = _has_source(state, "rmf") or _has_source(state, "risk")
    has_pms = _has_source(state, "pms") or _has_source(state, "pmcf") or _has_source(state, "complaint")
    claims = state.get("claim_ledger") or []
    warnings = [
        row for row in claims
        if str(row.get("claim_type") or "").lower() in {"ifu_warning", "warning_contraindication"}
    ]
    if not warnings:
        warnings = [
            {
                "claim_id": row.get("risk_id") or f"RISK-{idx:03d}",
                "claim_text": row.get("risk_side_effect") or row.get("risk_description") or row.get("description") or "",
            }
            for idx, row in enumerate(risk_rows[:12], start=1)
        ]

    ifu_warning_crosswalk = []
    for idx, warning in enumerate(warnings[:20], start=1):
        warning_text = str(warning.get("claim_text") or warning.get("risk_side_effect") or "")[:300]
        ifu_warning_crosswalk.append(
            {
                "warning_id": f"IFU-WARN-{idx:03d}",
                "claim_id": str(warning.get("claim_id") or ""),
                "warning_text": warning_text,
                "rmf_required": True,
                "rmf_coverage_status": "mapped_pending_review" if has_rmf else "missing_rmf_source",
                "residual_risk_status": "requires_rmf_acceptability_confirmation",
                "final_body_allowed": bool(has_rmf),
            }
        )

    hazard_trace = []
    for idx, row in enumerate(risk_rows[:30], start=1):
        risk_id = str(row.get("risk_id") or f"R-{idx:03d}")
        hazard_trace.append(
            {
                "risk_id": risk_id,
                "hazard_or_hazardous_situation": str(row.get("risk_side_effect") or row.get("risk_description") or row.get("description") or "")[:300],
                "source": str(row.get("source") or "risk_trace_matrix"),
                "rmf_coverage_status": "present_requires_review" if has_rmf else "missing_rmf_source",
                "residual_risk_acceptability": "not_concludable_without_rmf" if not has_rmf else "requires_manufacturer_confirmation",
                "ifu_warning_linked": any(risk_id in str(w.get("claim_id") or "") for w in ifu_warning_crosswalk),
            }
        )

    pmcf_plan = {
        "pmcf_plan_exists": has_pms,
        "pms_pmcf_source_present": has_pms,
        "endpoint": "Confirm clinical performance, adverse events, user feedback, complaint trends and residual-risk acceptability for IFU-defined use.",
        "trigger": "Required when subject-device PMS/PMCF data, RMF residual-risk closure or direct clinical evidence are incomplete.",
        "timeline": "Define in manufacturer PMCF plan before final CER approval.",
        "owner": "Manufacturer clinical/regulatory owner",
        "status": "source_data_present" if has_pms else "required_controlled_gap",
    }

    benefit_risk_matrix = []
    for claim in claims[:30]:
        claim_id = str(claim.get("claim_id") or "")
        support = str(claim.get("support_status") or claim.get("support_level") or "").lower()
        closed = has_rmf and (has_pms or support in {"supported", "fully_supported", "closed"})
        benefit_risk_matrix.append(
            {
                "claim_id": claim_id,
                "claim_type": str(claim.get("claim_type") or ""),
                "benefit_or_performance_claim": str(claim.get("claim_text") or "")[:300],
                "evidence_support_status": support or "unknown",
                "rmf_status": "present_requires_review" if has_rmf else "missing_rmf_source",
                "pms_pmcf_status": "present" if has_pms else "missing_requires_pmcf_plan",
                "benefit_risk_conclusion_allowed": closed,
                "allowed_conclusion": "controlled_positive_if_evidence_supports" if closed else "controlled_draft_limitation_only",
            }
        )

    closure_status = "CONCLUDABLE_WITH_CONTROLLED_UNCERTAINTY" if has_rmf and (has_pms or not claims) else "NOT_CONCLUDABLE"
    return {
        "rmf_hazard_trace": {
            "schema": "cer_rmf_hazard_trace_v1",
            "created_at": _now(),
            "has_rmf_source": has_rmf,
            "rows": hazard_trace,
        },
        "ifu_warning_rmf_crosswalk": {
            "schema": "cer_ifu_warning_rmf_crosswalk_v1",
            "created_at": _now(),
            "has_rmf_source": has_rmf,
            "rows": ifu_warning_crosswalk,
        },
        "benefit_risk_closure_matrix": {
            "schema": "cer_benefit_risk_closure_matrix_v1",
            "created_at": _now(),
            "closure_status": closure_status,
            "rows": benefit_risk_matrix,
        },
        "pmcf_plan_control_matrix": {
            "schema": "cer_pmcf_plan_control_matrix_v1",
            "created_at": _now(),
            **pmcf_plan,
        },
    }


def _has_source(state: dict[str, Any], needle: str) -> bool:
    needle = needle.lower()
    for item in state.get("source_inventory") or []:
        haystack = " ".join(
            str(item.get(key, ""))
            for key in ("document_type", "source_role", "filename", "path", "type")
        ).lower()
        if needle in haystack:
            return True
    return False


def build_rmf_deep_linkage(
    state: dict[str, Any],
    risk_rows: list[dict[str, Any]] | None = None,
    ifu_warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """WS9: Build deep RMF linkage with parsed hazard/residual-risk IDs.

    Goes beyond source-present checks to trace IFU warnings to specific
    RMF hazard IDs, sequence of events, hazardous situations, harms,
    risk control measures, and residual risk acceptability.
    """
    risk_rows = risk_rows or state.get("risk_rows") or []
    ifu_warnings = ifu_warnings or [
        row for row in (state.get("claim_ledger") or [])
        if str(row.get("claim_type") or "").lower() in {"ifu_warning", "ifu_warning_residual_risk", "warning_contraindication"}
    ]
    has_rmf = _has_source(state, "rmf") or _has_source(state, "risk")

    hazard_trace_deep: list[dict[str, Any]] = []
    for idx, row in enumerate(risk_rows[:50], start=1):
        risk_id = str(row.get("risk_id") or f"RISK-{idx:03d}")
        hazard_trace_deep.append({
            "rmf_hazard_id": str(row.get("hazard_id") or row.get("rmf_hazard_id") or f"HAZ-{idx:03d}"),
            "sequence_of_events": str(row.get("sequence_of_events") or row.get("event_sequence") or "")[:400],
            "hazardous_situation": str(row.get("hazardous_situation") or row.get("hazard") or row.get("risk_side_effect") or "")[:300],
            "harm": str(row.get("harm") or row.get("potential_harm") or row.get("risk_description") or "")[:300],
            "initial_risk": str(row.get("initial_risk") or row.get("pre_mitigation_risk") or ""),
            "risk_control_measure": str(row.get("risk_control_measure") or row.get("mitigation") or "")[:300],
            "residual_risk": str(row.get("residual_risk") or row.get("post_mitigation_risk") or ""),
            "residual_risk_acceptability": str(row.get("residual_risk_acceptability") or row.get("acceptability") or "requires_manufacturer_confirmation"),
            "source": str(row.get("source") or "risk_trace_matrix"),
        })

    ifu_warning_crosswalk_deep: list[dict[str, Any]] = []
    for idx, warning in enumerate(ifu_warnings[:30], start=1):
        warning_text = str(warning.get("claim_text") or warning.get("warning_text") or "")[:300]
        linked_hazards = [
            h["rmf_hazard_id"] for h in hazard_trace_deep
            if any(kw.lower() in warning_text.lower() for kw in str(h.get("harm") or "").split()[:3] if len(kw) > 3)
        ]
        ifu_warning_crosswalk_deep.append({
            "ifu_warning_id": f"IFU-WARN-DEEP-{idx:03d}",
            "claim_id": str(warning.get("claim_id") or ""),
            "warning_text": warning_text,
            "rmf_hazard_ids_linked": linked_hazards,
            "linkage_status": "linked" if linked_hazards else "unlinked",
            "rmf_required": True,
            "rmf_coverage_status": "mapped" if has_rmf and linked_hazards else ("missing_rmf_source" if not has_rmf else "unlinked_warning"),
            "residual_risk_status": "requires_rmf_acceptability_confirmation",
            "vigilance_signal_id": str(warning.get("vigilance_signal_id") or warning.get("signal_id") or ""),
        })

    unlinked_warnings = [w for w in ifu_warning_crosswalk_deep if w["linkage_status"] == "unlinked"]
    linkage_complete = len(unlinked_warnings) == 0
    if not has_rmf:
        gate_status = "FAIL_MISSING_RMF_SOURCE"
    elif not linkage_complete:
        gate_status = "FAIL_UNLINKED_WARNINGS"
    else:
        gate_status = "PASS"

    return {
        "schema": "rmf_deep_linkage_v1",
        "generated_at": _now(),
        "rmf_hazard_trace": {
            "has_rmf_source": has_rmf,
            "total_hazards": len(hazard_trace_deep),
            "rows": hazard_trace_deep,
        },
        "ifu_warning_rmf_crosswalk": {
            "total_warnings": len(ifu_warning_crosswalk_deep),
            "linked_count": len(ifu_warning_crosswalk_deep) - len(unlinked_warnings),
            "unlinked_count": len(unlinked_warnings),
            "unlinked_warning_ids": [w["ifu_warning_id"] for w in unlinked_warnings],
            "rows": ifu_warning_crosswalk_deep,
        },
        "gate_status": gate_status,
        "linkage_complete": linkage_complete,
        "blocks_unqualified_br_conclusion": gate_status != "PASS",
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
