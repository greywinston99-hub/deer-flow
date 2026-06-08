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
