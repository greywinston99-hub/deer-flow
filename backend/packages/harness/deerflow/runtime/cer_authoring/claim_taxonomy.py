"""WS3: Claim Taxonomy and Evidence Routing.

Classifies every claim into engineer-aligned taxonomy and routes each claim
type to its required evidence path.  Produces `claim_taxonomy_decision_table`
and `claim_evidence_route_matrix`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

CLAIM_CLASSES = [
    "non_claim_admin",
    "intended_purpose_scope",
    "indication",
    "efficacy_clinical_benefit",
    "safety_clinical_benefit",
    "performance_claim",
    "ifu_warning_residual_risk",
    "contraindication",
    "technical_specification",
    "sterility_or_shelf_life",
]

CLAIM_EVIDENCE_ROUTES: dict[str, dict[str, Any]] = {
    "non_claim_admin": {
        "primary_route": "none",
        "required_sources": [],
        "skip_pubmed": True,
        "skip_sota": True,
        "final_body_allowed": True,
        "support_ceiling": "ADMIN_ONLY",
    },
    "intended_purpose_scope": {
        "primary_route": "IFU",
        "required_sources": ["subject_device_ifu"],
        "skip_pubmed": True,
        "skip_sota": False,
        "final_body_allowed": True,
        "support_ceiling": "STATEMENT_OF_SCOPE",
    },
    "indication": {
        "primary_route": "IFU + clinical_guidelines",
        "required_sources": ["subject_device_ifu", "clinical_guidelines"],
        "skip_pubmed": False,
        "skip_sota": False,
        "final_body_allowed": True,
        "support_ceiling": "MODERATE",
    },
    "efficacy_clinical_benefit": {
        "primary_route": "clinical_evidence",
        "required_sources": ["clinical_study", "pms_pmcf"],
        "min_pivotal": 1,
        "min_supportive": 1,
        "require_direct": True,
        "skip_pubmed": False,
        "skip_sota": False,
        "final_body_allowed": True,
        "support_ceiling": "STRONG",
    },
    "safety_clinical_benefit": {
        "primary_route": "clinical+PMS+vigilance",
        "required_sources": ["clinical_study", "pms_pmcf", "vigilance"],
        "min_independent_sources": 2,
        "skip_pubmed": False,
        "skip_sota": False,
        "final_body_allowed": True,
        "support_ceiling": "STRONG",
    },
    "performance_claim": {
        "primary_route": "clinical_or_bench",
        "required_sources": ["clinical_study", "bench_test"],
        "min_pivotal": 1,
        "skip_pubmed": False,
        "skip_sota": False,
        "final_body_allowed": True,
        "support_ceiling": "STRONG",
    },
    "ifu_warning_residual_risk": {
        "primary_route": "RMF/GSPR",
        "required_sources": ["subject_device_rmf", "subject_device_gspr"],
        "min_rmf_coverage": 0.8,
        "require_rmf": True,
        "require_gspr": True,
        "skip_pubmed": True,
        "skip_sota": True,
        "final_body_allowed": True,
        "support_ceiling": "MODERATE",
    },
    "contraindication": {
        "primary_route": "RMF/GSPR/IFU",
        "required_sources": ["subject_device_rmf", "subject_device_ifu"],
        "require_rmf": True,
        "skip_pubmed": True,
        "skip_sota": True,
        "final_body_allowed": True,
        "support_ceiling": "CAUTIOUS",
    },
    "technical_specification": {
        "primary_route": "bench_test/IFU",
        "required_sources": ["subject_device_ifu", "bench_test"],
        "skip_pubmed": True,
        "skip_sota": False,
        "final_body_allowed": True,
        "support_ceiling": "STATEMENT_OF_FACT",
    },
    "sterility_or_shelf_life": {
        "primary_route": "bench_test/manufacturer",
        "required_sources": ["bench_test", "manufacturer_data"],
        "skip_pubmed": True,
        "skip_sota": True,
        "final_body_allowed": True,
        "support_ceiling": "STATEMENT_OF_FACT",
    },
}

CLAIM_TYPE_KEYWORDS: dict[str, list[str]] = {
    "non_claim_admin": ["package contains", "store in", "manufactured by", "contact information", "customer service"],
    "intended_purpose_scope": ["is intended for", "is designed for", "is indicated for use in", "the device is a"],
    "indication": ["indicated for", "for the treatment of", "for use in patients with", "diagnosis of"],
    "efficacy_clinical_benefit": ["reduces", "improves", "increases", "decreases", "lowers", "enhances", "effective", "benefit", "superior", "better outcome"],
    "safety_clinical_benefit": ["safe", "fewer complications", "lower adverse event", "reduced risk of", "no serious adverse", "well tolerated"],
    "performance_claim": ["achieves", "delivers", "provides", "generates", "accuracy", "sensitivity", "specificity", "flow rate", "pressure"],
    "ifu_warning_residual_risk": ["warning", "caution", "do not use", "not for use", "precaution", "potential risk", "may cause"],
    "contraindication": ["contraindicated", "must not be used", "is prohibited", "should not be used in"],
    "technical_specification": ["diameter", "length", "weight", "material", "voltage", "frequency", "specification", "dimensions"],
    "sterility_or_shelf_life": ["sterile", "sterilized", "shelf life", "expiration", "expiry", "storage condition", "EO sterilized"],
}


def classify_claim(claim_text: str, existing_type: str = "") -> str:
    """Classify a claim into the engineer-aligned taxonomy.

    Uses keyword matching against the claim text with fallback to the existing
    claim_type if no clear match is found.
    """
    text_lower = claim_text.lower()
    scores: dict[str, int] = {}
    for cls_name, keywords in CLAIM_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > 0:
            scores[cls_name] = score

    if not scores:
        existing_norm = str(existing_type or "").lower().replace(" ", "_")
        for cls_name in CLAIM_CLASSES:
            if cls_name.replace("_", " ") in existing_norm or existing_norm in cls_name:
                return cls_name
        return "intended_purpose_scope"

    return max(scores, key=lambda k: scores[k])


def route_claim_evidence(claim_class: str) -> dict[str, Any]:
    """Return the evidence routing rules for a given claim class."""
    return CLAIM_EVIDENCE_ROUTES.get(claim_class, CLAIM_EVIDENCE_ROUTES["intended_purpose_scope"])


def build_claim_taxonomy_decision_table(
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify every claim and produce taxonomy + evidence route artifacts."""
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []

    for i, claim in enumerate(claims):
        claim_text = str(claim.get("claim_text") or claim.get("description") or "")
        existing_type = str(claim.get("claim_type") or "")
        claim_class = classify_claim(claim_text, existing_type)
        route = route_claim_evidence(claim_class)

        rows.append({
            "claim_id": claim.get("claim_id") or f"CLAIM-{i+1:03d}",
            "claim_text": claim_text[:300],
            "original_claim_type": existing_type,
            "classified_claim_class": claim_class,
            "is_benefit_claim": claim_class in {"efficacy_clinical_benefit", "safety_clinical_benefit"},
            "is_safety_claim": claim_class == "safety_clinical_benefit",
            "is_warning": claim_class in {"ifu_warning_residual_risk", "contraindication"},
            "is_admin": claim_class == "non_claim_admin",
            "final_body_allowed": bool(route.get("final_body_allowed")),
            "support_ceiling": route.get("support_ceiling", "CAUTIOUS"),
        })

        route_rows.append({
            "claim_id": claim.get("claim_id") or f"CLAIM-{i+1:03d}",
            "claim_class": claim_class,
            "primary_evidence_route": route.get("primary_route", ""),
            "required_sources": route.get("required_sources", []),
            "min_pivotal": route.get("min_pivotal"),
            "min_supportive": route.get("min_supportive"),
            "require_direct": route.get("require_direct", False),
            "min_rmf_coverage": route.get("min_rmf_coverage"),
            "skip_pubmed": route.get("skip_pubmed", False),
            "skip_sota": route.get("skip_sota", False),
        })

    return {
        "schema": "claim_taxonomy_v1",
        "generated_at": now,
        "claim_taxonomy_decision_table": rows,
        "claim_evidence_route_matrix": route_rows,
        "summary": {
            "total_claims": len(claims),
            "classified_classes": sorted(set(r["classified_claim_class"] for r in rows)),
            "benefit_claims": sum(1 for r in rows if r["is_benefit_claim"]),
            "safety_claims": sum(1 for r in rows if r["is_safety_claim"]),
            "warning_claims": sum(1 for r in rows if r["is_warning"]),
            "admin_claims": sum(1 for r in rows if r["is_admin"]),
            "not_allowed_in_body": sum(1 for r in rows if not r["final_body_allowed"]),
        },
    }
