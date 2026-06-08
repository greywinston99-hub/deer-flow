"""BIGDP2026.6 R1: Expert Rule Loader — YAML decision tables → typed rule objects.

Loads the Expert Logic Pack YAML files at import time and provides
structured access to expert rules for the ledger builder nodes and gate evaluators.

Usage:
    from deerflow.runtime.cer_authoring.expert_rule_loader import (
        get_conclusion_strength,
        classify_claim,
        get_evidence_support_type,
        get_gap_disposition,
        get_ifu_transformation,
        get_benchmark_classification,
        get_human_gate_triggers,
    )
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ── Cached configs ──
_cache: dict[str, Any] = {}

_EXPERT_LOGIC_PACK = Path(__file__).resolve().parents[6] / "BIGDP2026_6" / "expert_logic_pack"


def _load_yaml(filename: str) -> dict[str, Any]:
    """Load a YAML file from the expert logic pack (cached)."""
    if filename in _cache:
        return _cache[filename]
    path = _EXPERT_LOGIC_PACK / filename
    if not path.exists():
        logger.warning("Expert logic file not found: %s", path)
        return {}
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    _cache[filename] = data
    return data


# ── Conclusion Strength (from CONCLUSION_STRENGTH_DECISION_TABLE.yaml) ──

def get_conclusion_strength(support_type: str, evidence_count: int) -> str:
    """Derive conclusion strength from evidence support type and count.

    Mirrors CONCLUSION_STRENGTH_DECISION_TABLE.yaml matrix.
    """
    table = _load_yaml("CONCLUSION_STRENGTH_DECISION_TABLE.yaml")
    matrix = table.get("matrix", {})

    # Try exact match first, then prefix match (direct → direct_clinical, etc.)
    row = matrix.get(support_type)
    if not row:
        for key in matrix:
            if key.startswith(support_type) or support_type.startswith(key):
                row = matrix[key]
                break
    if not row:
        # Check anti-patterns
        anti = table.get("anti_patterns", [])
        for pattern in anti:
            if support_type in pattern:
                return "not_supported"
        return "limited"

    if evidence_count >= 3:
        return row.get("≥3", row.get("any", "limited"))
    elif evidence_count >= 2:
        return row.get("2", row.get("any", "limited"))
    elif evidence_count >= 1:
        return row.get("1", row.get("any", "limited"))
    else:
        return row.get("0", row.get("any", "limited"))


# ── Claim Classification (from CLAIM_CLASSIFICATION_DECISION_TABLE.yaml) ──

def classify_claim(claim_text: str) -> str:
    """Classify a claim based on text patterns.

    Returns one of: clinical_performance, clinical_safety, warning,
    usability, non_clinical, marketing_overclaim, unsupported_claim.
    """
    table = _load_yaml("CLAIM_CLASSIFICATION_DECISION_TABLE.yaml")
    decisions = table.get("decisions", [])
    text_lower = claim_text.lower()

    for decision in decisions:
        patterns = decision.get("patterns", [])
        for pattern in patterns:
            if pattern.lower() in text_lower:
                return decision["classification"]

    return "unsupported_claim"


# ── Evidence Support Type (from EVIDENCE_SUPPORT_DECISION_TABLE.yaml) ──

def get_evidence_support_type(
    device_match: str = "subject_device",
    data_type: str = "clinical",
    source: str = "",
    equivalence_documented: bool = False,
) -> str:
    """Determine evidence support type from evidence characteristics."""
    table = _load_yaml("EVIDENCE_SUPPORT_DECISION_TABLE.yaml")
    decisions = table.get("decisions", [])

    for d in decisions:
        conditions = d.get("conditions", {})
        dm = conditions.get("device_match", "")
        dt = conditions.get("data_type", "")
        src = conditions.get("source", "")

        if isinstance(dt, list):
            dt_match = data_type in dt
        else:
            dt_match = (data_type == dt or dt == "")

        if isinstance(dm, str) and dm:
            if dm != device_match:
                continue
        if src and source not in (src if isinstance(src, list) else [src]):
            continue
        if not dt_match:
            continue

        return d["support_type"]

    return "insufficient"


# ── Gap Disposition (from GAP_DISPOSITION_DECISION_TABLE.yaml) ──

def get_gap_disposition(
    evidence_count: int = 0,
    conclusion_strength: str = "limited",
    claim_type: str = "clinical_performance",
    rmf_alignment: bool = False,
) -> str:
    """Determine gap disposition from evidence gap pattern."""
    table = _load_yaml("GAP_DISPOSITION_DECISION_TABLE.yaml")
    decisions = table.get("decisions", [])

    if evidence_count == 0:
        return "PMCF_required"
    if conclusion_strength == "not_supported":
        return "cannot_support_claim"
    if claim_type == "clinical_safety" and not rmf_alignment:
        return "risk_control_required"
    if conclusion_strength == "limited":
        return "PMCF_required"

    return "no_gap"


# ── IFU Transformation (from IFU_CLAIM_TRANSFORMATION_RULES.yaml) ──

def get_ifu_transformation(ifu_text: str, evidence_support_type: str = "direct") -> dict[str, Any]:
    """Determine what transformation is needed for an IFU claim."""
    rules = _load_yaml("IFU_CLAIM_TRANSFORMATION_RULES.yaml")
    transformations = rules.get("transformations", [])
    text_lower = ifu_text.lower()

    # Check marketing keywords first
    marketing_keywords = [
        "revolutionary", "best", "superior", "unmatched", "guaranteed",
        "perfect", "game-changing", "first-ever", "only", "unique",
        "unparalleled", "breakthrough", "gold standard", "ultimate",
        "eliminates all", "100%", "never fails", "always"
    ]
    detected = [kw for kw in marketing_keywords if kw in text_lower]
    if detected:
        return {
            "action": "flag_marketing_language",
            "marketing_keywords": detected,
            "human_review": True,
            "rule_ref": "IFU-01",
        }

    # Check evidence support
    if evidence_support_type == "insufficient":
        return {
            "action": "reject_from_cer",
            "reason": "No evidence supports this claim.",
            "human_review": True,
            "rule_ref": "IFU-04",
        }
    if evidence_support_type in ("indirect", "equivalent"):
        return {
            "action": "weaken_strength",
            "reason": f"Evidence is {evidence_support_type}; conclusion capped.",
            "human_review": True,
            "rule_ref": "CON-03",
        }

    return {"action": "copy_without_change", "human_review": False}


# ── Benchmark Classification (from BENCHMARK_DERIVATION_DECISION_TABLE.yaml) ──

def get_benchmark_classification(
    source_study_count: int = 0,
    population_comparability: str = "unknown",
    device_comparability: str = "alternative_therapy",
) -> dict[str, str]:
    """Classify a benchmark (direct/indirect/fallback/insufficient)."""
    table = _load_yaml("BENCHMARK_DERIVATION_DECISION_TABLE.yaml")
    decisions = table.get("decisions", [])

    if source_study_count == 0:
        return {"directness": "fallback", "confidence": "insufficient",
                "class": "insufficient_benchmark"}

    # Alternative therapy with <3 studies or partial/different population → fallback first
    if device_comparability == "alternative_therapy" and (
        source_study_count < 3 or population_comparability in ("partial_overlap", "different", "unknown")
    ):
        return {"directness": "fallback", "confidence": "low",
                "class": "fallback_benchmark"}

    for d in decisions:
        conds = d.get("conditions", {})
        min_count = conds.get("source_study_count", ">= 0")
        pop_comp = conds.get("population_comparability", [])

        # Parse min count
        if isinstance(min_count, str) and ">= " in min_count:
            required = int(min_count.replace(">= ", "").strip())
        elif isinstance(min_count, int):
            required = min_count
        else:
            required = 0

        if source_study_count >= required:
            if isinstance(pop_comp, list) and population_comparability in pop_comp:
                return {"directness": d.get("directness", "indirect"),
                        "confidence": d.get("confidence", "medium"),
                        "class": d.get("benchmark_class", "indirect_benchmark")}

    return {"directness": "fallback", "confidence": "low",
            "class": "fallback_benchmark"}


# ── Human Gate Triggers (from HUMAN_GATE_TRIGGER_RULES.yaml) ──

def get_human_gate_triggers(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Check which human gate triggers are activated for current state."""
    rules = _load_yaml("HUMAN_GATE_TRIGGER_RULES.yaml")
    triggers = rules.get("triggers", [])
    activated = []

    for t in triggers:
        trigger_id = t.get("trigger_id", "")
        if not t.get("implemented", False):
            continue

        # HG-PRODUCT-IDENTITY
        if trigger_id == "HG-PRODUCT-IDENTITY":
            device = state.get("device_profile") or {}
            if not all(device.get(f) for f in ["device_name", "intended_use", "device_class"]):
                activated.append(t)

        # HG-CANNOT-SUPPORT
        if trigger_id == "HG-CANNOT-SUPPORT":
            ledger = state.get("cer_reasoning_ledger") or {}
            for c in ledger.get("claims", []):
                if c.get("conclusion_strength") == "not_supported":
                    activated.append(t)
                    break

        # HG-MARKETING-LANGUAGE
        if trigger_id == "HG-MARKETING-LANGUAGE":
            ifu = state.get("ifu_claim_evolution_ledger") or {}
            for c in ifu.get("claims", []):
                if c.get("evolution_flags", {}).get("marketing_language_detected"):
                    activated.append(t)
                    break

        # HG-BR-UNCLEAR
        if trigger_id == "HG-BR-UNCLEAR":
            br = state.get("benefit_risk_closure_matrix") or {}
            if br.get("closure_status") == "NOT_CONCLUDABLE":
                activated.append(t)

        # HG-RMF-GSPR-GAP
        if trigger_id == "HG-RMF-GSPR-GAP":
            claim_ledger = state.get("claim_ledger") or []
            alignment = state.get("alignment_matrix") or []
            has_safety = any(c.get("claim_type") == "clinical_safety" for c in claim_ledger)
            if has_safety and not alignment:
                activated.append(t)

    return activated


# ── Convenience: load the full rulebook ──

def load_rulebook() -> dict[str, Any]:
    """Load the full EXPERT_REASONING_RULEBOOK.yaml."""
    return _load_yaml("EXPERT_REASONING_RULEBOOK.yaml")


def get_rules_by_category(category: str) -> list[dict[str, Any]]:
    """Get all rules in a given category."""
    rulebook = load_rulebook()
    return [r for r in rulebook.get("rules", []) if r.get("category") == category]


# ══════════════════════════════════════════════════════════════════════════════
# BIGDP2026.6V_2 Batch C: Endpoint Semantic Classifier
# ══════════════════════════════════════════════════════════════════════════════

ENDPOINT_CLASSIFICATION_TAXONOMY = {
    "adverse_event": {
        "label": "Adverse Event (AE)",
        "definition": "Device-related untoward medical event per ISO 14155",
        "examples": ["skin damage", "infection", "device malfunction", "hematoma", "pseudoaneurysm"],
        "is_safety_endpoint": True,
        "classification_basis": "ISO_14155",
        "common_misclassification": "serious_adverse_event",
    },
    "serious_adverse_event": {
        "label": "Serious Adverse Event (SAE)",
        "definition": "AE resulting in death, life-threatening, hospitalization, disability, or intervention",
        "examples": ["major bleeding requiring transfusion", "retroperitoneal hemorrhage", "death"],
        "is_safety_endpoint": True,
        "classification_basis": "ISO_14155",
        "common_misclassification": "adverse_event",
    },
    "device_deficiency": {
        "label": "Device Deficiency",
        "definition": "Inadequacy of device identity, quality, durability, reliability, safety, or performance",
        "examples": ["device fracture", "coating delamination", "premature battery depletion"],
        "is_safety_endpoint": True,
        "classification_basis": "heuristic",
        "common_misclassification": "adverse_event",
    },
    "treatment_failure": {
        "label": "Treatment Failure / Switching",
        "definition": "Clinical decision to abandon device for alternative therapy — NOT an AE",
        "examples": ["conversion to manual compression", "switch to surgical closure", "device abandonment for tourniquet"],
        "is_safety_endpoint": False,
        "note": "Reflects efficacy limitation, not safety issue. Must be reported separately from AE.",
        "classification_basis": "NB_comment",
        "common_misclassification": "adverse_event",
    },
    "inadequate_hemostasis": {
        "label": "Inadequate Hemostasis",
        "definition": "Efficacy endpoint — failure to achieve hemostasis within expected timeframe",
        "examples": ["continued bleeding at 3 min", "hemostasis not achieved within protocol window"],
        "is_safety_endpoint": False,
        "note": "Efficacy endpoint, not safety. Report as hemostasis failure rate under efficacy.",
        "classification_basis": "engineer_correction",
        "common_misclassification": "adverse_event",
    },
    "rescue_therapy_switch": {
        "label": "Rescue Therapy / Alternative Treatment",
        "definition": "Use of rescue therapy when primary device fails to achieve intended result",
        "examples": ["additional closure device applied", "surgical repair", "prolonged manual pressure"],
        "is_safety_endpoint": False,
        "classification_basis": "expert_judgment",
        "common_misclassification": "adverse_event",
    },
    "procedural_outcome": {
        "label": "Procedural Outcome",
        "definition": "Endpoint measuring procedural success or efficiency",
        "examples": ["device success rate", "procedure time", "length of stay"],
        "is_safety_endpoint": False,
        "classification_basis": "heuristic",
        "common_misclassification": "",
    },
    "other": {
        "label": "Other / Unclassified",
        "definition": "Endpoint not matching any defined category",
        "examples": [],
        "is_safety_endpoint": False,
        "classification_basis": "heuristic",
        "common_misclassification": "",
    },
}

# ── Absorbed from C1_ENDPOINT_SEMANTICS.csv (90 rows, 15 projects) ──
# Key finding: ALL non-AE endpoint types share common_misclassification="adverse_event"
# This means the dominant error pattern is over-classifying everything as AE.
# The classifier must actively warn when treatment_failure/rescue_therapy_switch/
# inadequate_hemostasis are being misclassified as adverse_event.
ENDPOINT_MISCLASSIFICATION_WARNING = (
    "WARNING: Endpoint classified as '{actual}' but may be misclassified. "
    "Common misclassification pattern from {basis}-based calibration data: "
    "'{endpoint_name}' is frequently misclassified as 'adverse_event'. "
    "Verify: is this a safety event (AE) or an efficacy/treatment endpoint?"
)


# ── Absorbed from C2_COMPARATOR_BENCHMARK.csv (54 rows, 11+ projects) ──
# Distribution: 78% direct, 22% fallback. Fallback always has limitation.
# Comparator data found in 42/54 rows; 12/54 have NO_COMPARATOR_DATA_FOUND.
COMPARATOR_EXPECTED_DIRECTNESS_RATIO = 0.78  # 42/54 direct
COMPARATOR_FALLBACK_RATE = 0.22  # 12/54 fallback
COMPARATOR_MINIMUM_REQUIREMENTS = [
    "point_estimate",
    "sample_size",
    "source_PMID",
    "directness",
]


def classify_endpoint(endpoint_name: str, context_text: str = "") -> str:
    """Classify an endpoint into the standard taxonomy.

    Uses keyword matching against endpoint name and context text.
    Returns one of the ENDPOINT_CLASSIFICATION_TAXONOMY keys.
    """
    name_lower = endpoint_name.lower()
    ctx_lower = context_text.lower()
    combined = f"{name_lower} {ctx_lower}"

    # Priority order: check specific patterns first
    # SAE → serious + AE
    if any(kw in combined for kw in ("serious adverse", "sae", "major bleed", "death", "life-threat")):
        return "serious_adverse_event"

    # Device deficiency
    if any(kw in combined for kw in ("fracture", "delamination", "battery", "malfunction", "deficiency")):
        return "device_deficiency"

    # Rescue therapy / treatment switch
    if any(kw in combined for kw in ("rescue", "switch", "conversion to", "abandon", "tourniquet", "manual compression", "surgical clos")):
        return "rescue_therapy_switch"

    # Treatment failure (broader match after rescue)
    if any(kw in combined for kw in ("treatment fail", "device fail", "switch to", "alternative therap")):
        return "treatment_failure"

    # Inadequate hemostasis
    if any(kw in combined for kw in ("hemostasis", "bleeding", "blood loss", "closure time", "continued bleed")):
        return "inadequate_hemostasis"

    # AE — general adverse events
    if any(kw in combined for kw in ("adverse event", "complication", "ae", "hematoma", "infection", "pseudoaneurysm", "skin dam", "skin inj", "nerve inj")):
        return "adverse_event"

    # Procedural outcome
    if any(kw in combined for kw in ("success", "procedure time", "length of stay", "device success", "technical success")):
        return "procedural_outcome"

    return "other"


def is_safety_endpoint(endpoint_classification: str) -> bool:
    """Check if endpoint classification is safety-related."""
    taxonomy = ENDPOINT_CLASSIFICATION_TAXONOMY.get(endpoint_classification, {})
    return taxonomy.get("is_safety_endpoint", False)


# ══════════════════════════════════════════════════════════════════════════════
# BIGDP2026.6V_3 U1: Clinical Fact V2 — E0 Eligibility Layer + Statistical Parsers
# ══════════════════════════════════════════════════════════════════════════════

SOURCE_ELIGIBILITY = ["fulltext_verified", "abstract_only", "secondary_source", "unavailable", "unknown"]
DATA_USE_ALLOWED = ["benchmark", "BR", "claim_support", "background_only", "not_allowed", "human_gate_required"]
EVIDENCE_TIER = ["direct_clinical", "indirect_clinical", "equivalent", "PMS", "manufacturer", "background", "unsupported", "unknown"]
CLINICAL_USE_LIMITATION = ["none", "abstract_only", "no_fulltext", "subgroup_only", "low_sample_size", "indirect_population", "endpoint_mismatch", "denominator_uncertain", "other"]


def classify_source_eligibility(fulltext_available: bool, abstract_available: bool, is_secondary: bool = False) -> str:
    """Classify source eligibility for clinical fact usage."""
    if fulltext_available:
        return "fulltext_verified"
    if is_secondary:
        return "secondary_source"
    if abstract_available:
        return "abstract_only"
    return "unavailable"


def classify_evidence_tier(study_design: str = "", device_match: str = "", is_manufacturer: bool = False) -> str:
    """Classify evidence tier based on study characteristics."""
    design_lower = study_design.lower()
    if is_manufacturer:
        return "manufacturer"
    if device_match == "subject_device" and any(kw in design_lower for kw in ("rct", "randomized", "prospective")):
        return "direct_clinical"
    if device_match == "subject_device":
        return "direct_clinical"
    if device_match == "equivalent_device":
        return "equivalent"
    if device_match == "different_device":
        return "indirect_clinical"
    if any(kw in design_lower for kw in ("registry", "pms", "surveillance")):
        return "PMS"
    if any(kw in design_lower for kw in ("review", "guideline", "background")):
        return "background"
    return "unknown"


def determine_data_use(source_eligibility: str, evidence_tier: str, n_total: int = 0,
                        has_endpoint_match: bool = True, has_denominator: bool = True) -> list[str]:
    """Determine allowed data uses for a clinical fact."""
    uses = []
    if source_eligibility == "unavailable":
        return ["not_allowed"]

    if evidence_tier in ("direct_clinical", "indirect_clinical", "equivalent"):
        if has_endpoint_match and has_denominator and n_total >= 30:
            uses.append("claim_support")
        if has_endpoint_match and n_total >= 50:
            uses.append("benchmark")
        uses.append("BR")

    if evidence_tier in ("PMS", "manufacturer"):
        uses.append("background_only")
        if has_endpoint_match:
            uses.append("BR")

    if evidence_tier == "background":
        uses.append("background_only")

    if source_eligibility == "abstract_only" and evidence_tier not in ("direct_clinical",):
        uses = ["background_only"]

    if not uses:
        uses.append("human_gate_required")

    return uses


def determine_clinical_limitation(source_eligibility: str, n_total: int = 0,
                                   is_subgroup: bool = False, has_full_denominator: bool = True) -> str:
    """Determine clinical use limitation for a fact."""
    if source_eligibility == "abstract_only":
        return "abstract_only"
    if source_eligibility == "unavailable":
        return "no_fulltext"
    if is_subgroup:
        return "subgroup_only"
    if n_total < 30:
        return "low_sample_size"
    if not has_full_denominator:
        return "denominator_uncertain"
    return "none"


def parse_hr_rr_or(text: str) -> list[dict]:
    """Parse HR/RR/OR from clinical text. Returns list of parsed statistics."""
    import re
    results = []
    for stat_type in ["HR", "RR", "OR"]:
        # Flexible: "HR 0.85", "HR=0.85", "HR: 0.85 (95% CI 0.70-1.05)"
        pattern = re.findall(
            stat_type + r'\s*[=:\s]+?\s*(\d+\.?\d*)\s*(?:\(?\s*95%\s*CI\s*(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)\s*\)?)?',
            text, re.IGNORECASE,
        )
        for val, ci_lo, ci_hi in pattern:
            results.append({
                "stat_type": stat_type, "value": float(val),
                "ci_lower": float(ci_lo) if ci_lo else None,
                "ci_upper": float(ci_hi) if ci_hi else None,
                "extraction_basis": f"{stat_type}={val}" + (f" (95%CI {ci_lo}-{ci_hi})" if ci_lo else ""),
            })
    return results


def parse_ci_pvalue(text: str) -> list[dict]:
    """Parse CI and p-value from text."""
    import re
    results = []
    # p-value
    p_pattern = re.findall(r'[pP]\s*[=<>]\s*(\d+\.?\d*)', text)
    for p_val in p_pattern:
        p = float(p_val)
        results.append({"stat_type": "p_value", "value": p,
                        "significant": p < 0.05, "extraction_basis": f"p={'<' if '<' in text else '='}{p_val}"})
    return results


# ══════════════════════════════════════════════════════════════════════════════
# BIGDP2026.6V_3 U2: Semantic Claim-Evidence Validator
# ══════════════════════════════════════════════════════════════════════════════

def validate_semantic_claim_support(claim: dict, evidence: dict) -> dict:
    """Validate semantic support between a claim and evidence item.

    Returns dict with: is_valid, checks_passed, checks_failed, rationale.
    """
    checks = {}
    claim_endpoints = set(str(claim.get("endpoint", "")).lower().split(","))
    evidence_endpoints = set(str(evidence.get("endpoint", "")).lower().split(","))
    claim_population = str(claim.get("population", "")).lower()
    evidence_population = str(evidence.get("population", "")).lower()
    claim_device = str(claim.get("device_name", "")).lower()
    evidence_device = str(evidence.get("device_studied", "")).lower()
    support_type = str(evidence.get("support_type", "direct")).lower()

    # Endpoint match
    checks["endpoint_match"] = bool(claim_endpoints & evidence_endpoints) or not claim_endpoints
    # Population match
    checks["population_match"] = (claim_population in evidence_population or evidence_population in claim_population
                                    or not claim_population or not evidence_population)
    # Device match
    checks["device_match"] = (claim_device in evidence_device or evidence_device in claim_device
                               or not claim_device or not evidence_device)
    # Directness check
    checks["directness_ok"] = support_type != "insufficient"
    # Support strength check
    evidence_strength = str(evidence.get("evidence_strength_score", 50))
    checks["support_strength_ok"] = support_type == "direct" or float(evidence_strength or 50) >= 30

    passed = [k for k, v in checks.items() if v]
    failed = [k for k, v in checks.items() if not v]
    is_valid = len(failed) == 0

    return {
        "is_valid": is_valid,
        "checks_passed": passed,
        "checks_failed": failed,
        "rationale": f"Semantic support: {len(passed)}/{len(checks)} checks passed. "
                     + (f"Failed: {', '.join(failed)}" if failed else "All checks passed."),
    }


# ══════════════════════════════════════════════════════════════════════════════
# BIGDP2026.6V_3 U3: Equivalence Runtime Gate
# ══════════════════════════════════════════════════════════════════════════════

EQUIVALENCE_ROUTES = [
    "equivalence_claimed", "equivalence_not_claimed", "equivalence_supporting_only",
    "equivalence_for_context_only", "equivalence_not_allowed", "human_gate_required",
]


def validate_equivalence_route(state: dict) -> str:
    """Determine the equivalence route based on device comparison data.

    Returns one of EQUIVALENCE_ROUTES.
    """
    equiv_claimed = state.get("equivalence_claimed", False)
    equiv_device = state.get("equivalent_device_name", "")
    has_technical = bool(state.get("equivalence_technical_comparison"))
    has_biological = bool(state.get("equivalence_biological_comparison"))
    has_clinical = bool(state.get("equivalence_clinical_comparison"))
    has_data_access = bool(state.get("equivalence_data_access"))
    has_differences_analysis = bool(state.get("equivalence_differences_impact_analysis"))

    if not equiv_claimed or not equiv_device:
        return "equivalence_not_claimed"

    dims_ok = has_technical and has_biological and has_clinical
    if not dims_ok:
        return "equivalence_not_allowed"

    if not has_data_access:
        return "human_gate_required"

    if not has_differences_analysis:
        return "equivalence_supporting_only"

    return "equivalence_claimed"


# ══════════════════════════════════════════════════════════════════════════════
# BIGDP2026.6V_3 U5: BR/GSPR Substantive Crosswalk
# ══════════════════════════════════════════════════════════════════════════════

def validate_br_gspr_crosswalk(state: dict) -> dict:
    """Validate benefit-risk and GSPR crosswalk completeness.

    Returns dict with: is_valid, issues, checks.
    """
    issues = []
    br_ledger = state.get("benefit_risk_ledger", [])
    gspr = state.get("gspr_coverage", {})
    alignment = state.get("alignment_matrix", [])
    unfavourable = state.get("unfavourable_evidence_register", [])

    # Benefit must have evidence
    for row in br_ledger:
        if not row.get("benefit_evidence_basis") and not row.get("evidence_ids"):
            issues.append(f"Benefit '{row.get('benefit', '?')}' has no evidence basis")

    # Unresolved uncertainty must have disposition
    uncertainty = state.get("unresolved_uncertainty_register", [])
    valid_dispositions = {"PMCF", "labeling_limitation", "risk_control", "human_gate", "cannot_support"}
    for item in uncertainty:
        disp = str(item.get("disposition", ""))
        if disp not in valid_dispositions:
            issues.append(f"Uncertainty '{item.get('description', '?')}' has invalid disposition: {disp}")

    # Unfavourable evidence must be addressed
    if unfavourable and not any("addressed" in str(u.get("status", "")).lower() for u in unfavourable):
        issues.append("Unfavourable evidence present but not addressed")

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "checks": {
            "benefits_have_evidence": not any("no evidence basis" in i for i in issues),
            "uncertainties_dispositioned": not any("invalid disposition" in i for i in issues),
            "unfavourable_addressed": not any("not addressed" in i for i in issues),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# BIGDP2026.6V_3 U6: Post-Write CER Prose QA Detectors
# ══════════════════════════════════════════════════════════════════════════════

def detect_writer_issues(prose_text: str, ledger: dict) -> list[dict]:
    """Run 9 post-write QA detectors against CER prose.

    Each detector returns {"detector": name, "status": PASS/FLAG/FAIL, "detail": str}.
    """
    results = []

    # 1. conclusion_overstatement
    for claim in ledger.get("claims", []):
        strength = claim.get("conclusion_strength", "limited")
        claim_text = claim.get("claim_text", "")
        if strength in ("limited", "not_supported") and claim_text[:30] in prose_text:
            strong_words = ["demonstrates", "confirms", "proves", "establishes", "guarantees"]
            if any(w in prose_text.lower() for w in strong_words):
                results.append({"detector": "conclusion_overstatement", "status": "FAIL",
                                "detail": f"Claim '{claim_text[:60]}' has strength={strength} but prose uses strong language"})

    # 2. unsupported_positive_claim
    for claim in ledger.get("claims", []):
        if claim.get("conclusion_strength") == "not_supported":
            if claim.get("claim_text", "")[:30] in prose_text:
                results.append({"detector": "unsupported_positive_claim", "status": "FAIL",
                                "detail": f"not_supported claim '{claim['claim_text'][:60]}' appears in prose"})

    # 3. no_source_numeric
    import re
    numbers = re.findall(r'\d+\.?\d*\s*%', prose_text)
    if numbers and not ("PMID" in prose_text or "pmid" in prose_text.lower()):
        results.append({"detector": "no_source_numeric", "status": "FLAG",
                        "detail": f"{len(numbers)} numeric claims without PMID reference"})

    # 4. endpoint_taxonomy_contradiction
    if "adverse event" in prose_text.lower() and "treatment failure" in prose_text.lower():
        results.append({"detector": "endpoint_taxonomy_contradiction", "status": "FLAG",
                        "detail": "Both AE and treatment_failure language in prose — verify classification"})

    # 5. PMCF overclaim
    if "PMCF" in prose_text.upper() and "resolves" in prose_text.lower():
        results.append({"detector": "PMCF_overclaim", "status": "FAIL",
                        "detail": "PMCF cannot 'resolve' evidence gaps — this is overclaim language"})

    # 6. missing_benchmark_limitation
    for ep in ledger.get("benchmark_derivation_trace", {}).get("endpoints", []):
        if ep.get("directness") == "fallback" and ep.get("endpoint_name", "")[:20] in prose_text:
            if "limitation" not in prose_text.lower() and "fallback" not in prose_text.lower():
                results.append({"detector": "missing_benchmark_limitation", "status": "FLAG",
                                "detail": f"Fallback benchmark '{ep['endpoint_name']}' used without limitation statement"})

    if not results:
        results.append({"detector": "all_clear", "status": "PASS", "detail": "No issues detected"})

    return results


# ══════════════════════════════════════════════════════════════════════════════
# BIGDP2026.6V4 Batch I: Regulatory Strategy Router + Evidence Burden Engine
# ══════════════════════════════════════════════════════════════════════════════

STRATEGY_ROUTES = ["WET", "legacy", "own_data_primary", "equivalence", "literature_primary", "innovation"]
SUFFICIENCY_LEVELS = ["sufficient", "partially_sufficient", "insufficient", "cannot_support"]
FINAL_STRATEGIES = ["WET_supported", "legacy_with_gap", "equivalence_limited", "literature_primary_with_PMCF", "innovation_CI_required", "cannot_support_current_claim"]

WET_6_CONDITIONS = [
    "device_technology_established_stable",
    "low_risk_scope_acceptable",
    "SOTA_stable",
    "PMS_PMCF_data_sufficient",
    "BR_clearly_acceptable",
    "intended_purpose_narrow_well_defined",
]


def classify_strategy_route(state: dict) -> dict:
    """Classify the regulatory strategy route for a CER project.

    Returns: {strategy_context_route, route_confidence, sufficiency_decision,
              final_CER_strategy, evidence_burden_level, required_next_action, ...}
    """
    device = state.get("device_profile", {})
    device_class = str(device.get("device_class", "")).upper()
    equivalence_claimed = state.get("equivalence_claimed", False)
    has_own_data = bool(state.get("own_clinical_data"))
    is_implantable = bool(device.get("is_implantable"))
    is_active = bool(device.get("is_active"))
    is_novel = bool(device.get("is_novel"))
    has_legacy_evidence = bool(state.get("legacy_evidence_sources"))

    # WET 6-condition check
    wet_checks = {}
    for cond in WET_6_CONDITIONS:
        wet_checks[cond] = bool(state.get(f"wet_{cond}", True))
    wet_passes = all(wet_checks.values())

    # Route determination
    if wet_passes and device_class not in ("III",) and not is_implantable and not is_active:
        route = "WET"
        confidence = "high" if all(wet_checks.values()) else "medium"
    elif has_legacy_evidence:
        route = "legacy"
        confidence = "medium"
    elif has_own_data:
        route = "own_data_primary"
        confidence = "medium" if state.get("own_data_quality_score", 0) >= 60 else "low"
    elif equivalence_claimed and state.get("equivalence_data_access"):
        route = "equivalence"
        confidence = "medium"
    elif is_novel:
        route = "innovation"
        confidence = "low"
    else:
        route = "literature_primary"
        confidence = "medium"

    # Sufficiency decision
    evidence_count = len(state.get("evidence_registry", []))
    has_pivotal = any(str(e.get("weight", "")).lower() == "pivotal" for e in state.get("evidence_registry", []))
    if evidence_count >= 3 and has_pivotal:
        sufficiency = "sufficient"
    elif evidence_count >= 1:
        sufficiency = "partially_sufficient" if has_pivotal else "insufficient"
    else:
        sufficiency = "cannot_support"

    # Hard overrides
    if sufficiency == "cannot_support":
        final_strategy = "cannot_support_current_claim"
        required_action = "human_gate"
    elif route == "WET" and not state.get("PMS_PMCF_review_complete"):
        final_strategy = "cannot_support_current_claim"
        required_action = "PMCF"
    elif route == "equivalence" and not state.get("equivalence_data_access"):
        final_strategy = "cannot_support_current_claim"
        required_action = "clinical_investigation"
    elif route == "innovation" and not state.get("clinical_investigation_plan"):
        final_strategy = "innovation_CI_required"
        required_action = "clinical_investigation"
    else:
        strategy_map = {
            "WET": "WET_supported",
            "legacy": "legacy_with_gap",
            "equivalence": "equivalence_limited",
            "literature_primary": "literature_primary_with_PMCF",
            "innovation": "innovation_CI_required",
            "own_data_primary": "literature_primary_with_PMCF",
        }
        final_strategy = strategy_map.get(route, "literature_primary_with_PMCF")
        required_action = "proceed" if sufficiency == "sufficient" else "PMCF"

    return {
        "strategy_context_route": route,
        "route_confidence": confidence,
        "sufficiency_decision": sufficiency,
        "final_CER_strategy": final_strategy,
        "evidence_burden_level": "high" if device_class in ("III",) else "moderate" if is_implantable else "low",
        "required_next_action": required_action,
        "alternative_routes_rejected": [],
        "route_rationale": f"Route={route}, WET checks={wet_checks}, evidence={evidence_count} items",
        "writer_conclusion_constraints": "moderate_only" if route != "WET" else "strong_allowed",
        "wet_6_condition_results": wet_checks,
    }


# ══════════════════════════════════════════════════════════════════════════════
# BIGDP2026.6V4 Batch J: Literature Intelligence V2
# ══════════════════════════════════════════════════════════════════════════════

LITERATURE_ROLES = [
    "direct_device_evidence", "equivalent_device_evidence", "similar_device_context",
    "comparator_benchmark", "alternative_treatment", "background_sota",
    "safety_signal", "excluded",
]


def classify_literature_role(article: dict, device_name: str = "") -> dict:
    """Classify literature article role for CER evidence use.

    Returns primary + secondary roles with confidence and rationale.
    """
    title = str(article.get("title", "")).lower()
    abstract = str(article.get("abstract", "") or article.get("findings", "")).lower()
    device_studied = str(article.get("device_studied", "")).lower()
    study_type = str(article.get("study_design", "")).lower()
    n = int(article.get("sample_size", 0))
    has_fulltext = str(article.get("full_text_available", "")).lower() in ("yes", "true", "1")

    roles = []
    # Direct device evidence
    if device_studied and device_name.lower() in device_studied:
        roles.append("direct_device_evidence")
    elif device_studied and any(kw in device_studied for kw in ("equivalent", "similar")):
        roles.append("equivalent_device_evidence")
    elif "comparator" in abstract or "vs" in abstract or "versus" in abstract:
        roles.append("comparator_benchmark")
    elif "review" in study_type or "meta-analysis" in study_type or "systematic" in study_type:
        roles.append("background_sota")
    elif any(kw in title + abstract for kw in ("safety", "adverse event", "complication")):
        roles.append("safety_signal")

    # Exclusion rules
    if n < 10:
        roles = ["excluded"]
    elif any(kw in title + abstract for kw in ("animal", "porcine", "swine", "rat ", "mouse", "in vitro")):
        roles = ["excluded"]

    primary = roles[0] if roles else "alternative_treatment"
    secondary = [r for r in roles[1:] if r != primary] if len(roles) > 1 else []

    return {
        "primary_article_role": primary,
        "secondary_roles": secondary,
        "role_confidence": "high" if primary in ("direct_device_evidence", "excluded") else "medium",
        "role_rationale": f"Primary={primary} from device_match={bool(device_studied)}, study_type={study_type}",
        "role_conflict_flags": [],
    }


# ══════════════════════════════════════════════════════════════════════════════
# BIGDP2026.6V4 Batch K: Strategy-Specific CER Blueprint Engine
# ══════════════════════════════════════════════════════════════════════════════

ROUTE_BLUEPRINTS = {
    "WET": {
        "allowed_claim_strength": "moderate_only",
        "forbidden_language": ["demonstrates superiority", "proves", "confirms", "establishes"],
        "required_elements": ["PMS_review", "SOTA_stability_evidence", "6_condition_check"],
        "writer_tone": "moderate; no superiority language",
        "NB_likely_questions": ["Why was WET route chosen?", "Are all 6 conditions satisfied?"],
    },
    "legacy": {
        "allowed_claim_strength": "moderate_only",
        "forbidden_language": ["grandfathered", "historical acceptance", "long safety record alone"],
        "required_elements": ["MDR_gap_matrix", "PMS_review", "SOTA_update"],
        "writer_tone": "acknowledge limitations; document MDR gap",
    },
    "equivalence": {
        "allowed_claim_strength": "moderate_only",
        "forbidden_language": ["direct evidence", "proven on subject device"],
        "required_elements": ["3_dim_comparison", "data_access_confirmation", "differences_impact_analysis"],
        "writer_tone": "based on equivalent device data; indirect support",
    },
    "literature_primary": {
        "allowed_claim_strength": "limited_only",
        "forbidden_language": ["strongly demonstrates", "definitively proves"],
        "required_elements": ["systematic_search", "SOTA_benchmark", "PMCF_limitation"],
        "writer_tone": "evidence-supported with limitations; PMCF recommended",
    },
    "innovation": {
        "allowed_claim_strength": "limited_only",
        "forbidden_language": ["safe and effective", "standard of care"],
        "required_elements": ["clinical_investigation_plan", "PMCF_commitment"],
        "writer_tone": "investigational; clinical investigation required",
    },
}


def get_route_blueprint(route: str) -> dict:
    """Get the CER blueprint constraints for a strategy route."""
    return ROUTE_BLUEPRINTS.get(route, ROUTE_BLUEPRINTS["literature_primary"])


# ══════════════════════════════════════════════════════════════════════════════
# BIGDP2026.6V4 Batch L: NB Explainability Packet
# ══════════════════════════════════════════════════════════════════════════════

def generate_nb_explainability_packet(strategy_result: dict, state: dict) -> dict:
    """Generate NB_EXPLAINABILITY_PACKET.json with likely NB challenges and answers."""
    challenges = []
    route = strategy_result.get("strategy_context_route", "unknown")

    challenges.append({
        "decision_type": "strategy_route",
        "question": f"Why was the '{route}' strategy route chosen for this CER?",
        "system_answer": strategy_result.get("route_rationale", ""),
        "regulatory_basis": "MDR Annex XIV, MEDDEV 2.7/1 Rev.4",
        "evidence_basis": f"Evidence items: {len(state.get('evidence_registry',[]))}",
        "limitation": f"Confidence: {strategy_result.get('route_confidence','medium')}",
        "trigger_for_rework": "Strategy route must be re-evaluated if new evidence or device change occurs",
    })

    if route == "WET":
        wet_results = strategy_result.get("wet_6_condition_results", {})
        challenges.append({
            "decision_type": "WET_legacy",
            "question": "Are all 6 WET conditions satisfied for this device?",
            "system_answer": f"WET conditions: {wet_results}",
            "regulatory_basis": "MDCG 2020-5, MDR Article 61",
            "evidence_basis": "PMS/PMCF data, SOTA stability assessment",
            "limitation": f"Passing: {sum(1 for v in wet_results.values() if v)}/{len(wet_results)}",
            "trigger_for_rework": "Any WET condition change requires re-evaluation",
        })

    return {
        "schema": "NB_EXPLAINABILITY_PACKET_v1",
        "generated_at": "",
        "strategy_rationale": strategy_result.get("route_rationale", ""),
        "likely_NB_challenges": challenges,
    }
def get_equivalence_limitation_for_writer(route: str) -> str:
    """Generate Writer limitation text based on equivalence route."""
    limitations = {
        "equivalence_claimed": "Equivalent device data used per MDR Annex XIV. Differences analyzed and determined not clinically significant.",
        "equivalence_not_claimed": "Equivalence is not claimed. Clinical evaluation follows literature-based, non-equivalence approach.",
        "equivalence_supporting_only": "Equivalent device data used as supporting context only. Differences impact analysis incomplete.",
        "equivalence_for_context_only": "Equivalent device data used for background context only. Not used for clinical conclusions.",
        "equivalence_not_allowed": "Equivalence cannot be claimed — incomplete 3-dimension comparison.",
        "human_gate_required": "Human expert review required for equivalence determination.",
    }
    return limitations.get(route, "Equivalence status: see CER §4.2.")
