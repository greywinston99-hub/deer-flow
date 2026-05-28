"""WS8: Dedicated Benefit-Risk Body Section.

Ensures CER body has a dedicated §4.8 Benefit-Risk Analysis section with
quantitative/semi-quantitative reasoning, not just annex support.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_benefit_risk_body_section(
    state: dict[str, Any],
    cer_body_text: str = "",
) -> dict[str, Any]:
    """Analyze benefit-risk presence in CER body and produce closure matrix.

    Checks:
    - Whether §4.8 Benefit-Risk Analysis exists in body text
    - Whether it contains clinical benefits with quantitative data
    - Whether risks are mapped with severity/occurrence/residual-risk status
    - Whether PMS/PMCF maturity is assessed
    - Whether conclusion strength is properly limited
    """
    now = datetime.now(timezone.utc).isoformat()
    body_lower = cer_body_text.lower()
    br_ledger = state.get("benefit_risk_ledger") or state.get("benefit_risk_closure_matrix") or {}
    rmf = state.get("rmf_hazard_trace") or {}
    claims = state.get("claim_ledger") or []
    pmcf = state.get("pmcf_plan_control_matrix") or state.get("pmcf_gap_register") or {}

    has_br_section = any(kw in body_lower for kw in [
        "benefit-risk analysis", "benefit risk analysis",
        "benefit-risk profile", "benefit-risk assessment",
        "analysis of benefit-risk", "4.8",
    ])

    has_quantitative = any(kw in body_lower for kw in [
        "incidence", "rate", "percentage", "n=", "odds ratio",
        "hazard ratio", "relative risk", "confidence interval",
        "p-value", "p =", "p<", "mean", "median", "sd",
    ])

    has_risk_mapping = any(kw in body_lower for kw in [
        "residual risk", "risk acceptability", "risk control",
        "severity", "occurrence", "hazard identification",
    ])

    has_pms_pmcf_maturity = any(kw in body_lower for kw in [
        "pms maturity", "pmcf maturity", "post-market",
        "post market", "surveillance data", "pmcf plan",
        "pms data",
    ])

    br_rows = br_ledger.get("rows") or br_ledger.get("benefit_risk_matrix") or []
    has_br_closed = any(
        row.get("benefit_risk_conclusion_allowed") or row.get("br_closed")
        for row in br_rows
    )

    rmf_present = bool(rmf.get("has_rmf_source") or rmf.get("rows"))
    pmcf_present = bool(pmcf.get("pmcf_plan_exists") or pmcf.get("pms_pmcf_source_present"))

    can_conclude_favourable = has_br_section and has_quantitative and has_risk_mapping and rmf_present and pmcf_present
    if not can_conclude_favourable and has_br_section:
        conclusion_allowed = "controlled_uncertainty_only"
    elif can_conclude_favourable:
        conclusion_allowed = "controlled_positive_if_evidence_supports"
    else:
        conclusion_allowed = "blocked_missing_br_section"

    return {
        "schema": "benefit_risk_closure_matrix_v1",
        "generated_at": now,
        "benefit_risk_body_section": {
            "section_present": has_br_section,
            "has_quantitative_data": has_quantitative,
            "has_risk_mapping": has_risk_mapping,
            "has_pms_pmcf_maturity_discussion": has_pms_pmcf_maturity,
        },
        "support_status": {
            "rmf_source_present": rmf_present,
            "pmcf_source_present": pmcf_present,
            "benefit_risk_rows_count": len(br_rows),
            "any_benefit_risk_closed": has_br_closed,
        },
        "conclusion_allowed": conclusion_allowed,
        "unqualified_favourable_allowed": can_conclude_favourable,
        "missing_elements": [
            m for m, present in [
                ("benefit_risk_section", has_br_section),
                ("quantitative_data", has_quantitative),
                ("risk_mapping", has_risk_mapping),
                ("pms_pmcf_maturity", has_pms_pmcf_maturity),
                ("rmf_source", rmf_present),
                ("pmcf_plan", pmcf_present),
            ] if not present
        ],
        "writer_instruction": "Include dedicated §4.8 Benefit-Risk Analysis section with clinical benefits (quantitative), mapped risks, PMS/PMCF maturity, and conclusion strength limitation."
        if not has_br_section else "",
    }
