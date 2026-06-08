"""V5 Slot Engine — Maps source family groups to canonical slots with confidence bands."""

from __future__ import annotations

import uuid
from typing import Any

from .v5_flavor_profiles import get_flavor_profile


PRIMARY_SLOTS = [
    {
        "slot_type": "IFU",
        "display_name": "Instructions for Use",
        "source_types": {"ifu"},
        "keywords": ["ifu", "instruction for use", "使用说明"],
    },
    {
        "slot_type": "CER_CEP",
        "display_name": "Clinical Evaluation Report / Plan",
        "source_types": {"cer", "cep"},
        "keywords": ["cer", "cep", "clinical evaluation", "临床评价"],
    },
    {
        "slot_type": "RMF_RISK",
        "display_name": "Risk Management File / Risk Analysis",
        "source_types": {"rmf", "risk_related", "risk_analysis"},
        "keywords": ["rmf", "risk", "风险管理", "iso 14971"],
    },
    {
        "slot_type": "PMCF",
        "display_name": "Post-Market Clinical Follow-up",
        "source_types": {"pmcf"},
        "keywords": ["pmcf", "post-market clinical", "上市后临床随访"],
    },
    {
        "slot_type": "PMS_PSUR",
        "display_name": "Post-Market Surveillance / PSUR",
        "source_types": {"pms", "psur"},
        "keywords": ["pms", "psur", "surveillance", "上市后监督"],
    },
    {
        "slot_type": "GSPR",
        "display_name": "General Safety and Performance Requirements",
        "source_types": {"gspr"},
        "keywords": ["gspr", "safety and performance", "通用安全"],
    },
    {
        "slot_type": "SSCP",
        "display_name": "Summary of Safety and Clinical Performance",
        "source_types": {"sscp"},
        "keywords": ["sscp", "summary of safety", "安全性和临床性能摘要"],
    },
    {
        "slot_type": "EQUIVALENCE",
        "display_name": "Equivalence Evidence",
        "source_types": {"equivalence"},
        "keywords": ["equivalence", "等同性", "substantial equivalence"],
    },
    {
        "slot_type": "LITERATURE_SOTA",
        "display_name": "Literature / State of the Art",
        "source_types": {"literature", "sota"},
        "keywords": ["literature", "sota", "state of the art", "文献", "最新技术"],
    },
    {
        "slot_type": "LABELS_PACKAGING",
        "display_name": "Labels / Packaging",
        "source_types": {"labels", "label", "packaging"},
        "keywords": ["label", "packaging", "标签", "包装"],
    },
    {
        "slot_type": "BIOCOMPATIBILITY",
        "display_name": "Biocompatibility",
        "source_types": {"biocompatibility"},
        "keywords": ["biocompatibility", "iso 10993", "生物相容性"],
    },
    {
        "slot_type": "PERFORMANCE",
        "display_name": "Performance / Verification",
        "source_types": {"performance", "clinical_evidence"},
        "keywords": ["performance", "verification", "性能", "验证"],
    },
]

CORE_SLOT_TYPES = {"IFU", "CER_CEP", "RMF_RISK", "PMCF", "GSPR"}

# Competitor brand names that should not be primary canonical sources for the current project.
# These typically appear in equivalence evidence, literature, or competitor IFU files.
COMPETITOR_BRANDS = {
    "kundeninfo", "getinge", "maquet", "abbott", "cardiohelp", "centrimag",
    "thoratec", "heartmate", "heartware", "berlin heart", "jarvik",
}

# Project-specific identifiers that indicate a file is likely owned by the current project.
# These are extracted from the CER_RMF_174 source package (心擎 MDR).
PROJECT_IDENTIFIERS = {
    "dhf_m01", "m01", "ce_dhf_m01", "ce_m01", "rm01", "qd03", "qd02",
}


def _safe_lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _extract_family_type(family_group: dict[str, Any]) -> str:
    return _safe_lower(
        family_group.get("source_type")
        or family_group.get("source_family_type")
        or family_group.get("document_type")
    )


def _score_slot_match(slot_def: dict[str, Any], family_group: dict[str, Any]) -> float:
    family_type = _extract_family_type(family_group)
    direct_types = {t.lower() for t in slot_def.get("source_types", set())}
    keywords = [_safe_lower(k) for k in slot_def.get("keywords", [])]

    score = 0.0
    if family_type in direct_types:
        score += 0.8
    for direct in direct_types:
        if direct and direct in family_type:
            score += 0.15
    for keyword in keywords:
        if keyword and keyword in family_type:
            score += 0.05

    if score <= 0:
        return 0.0

    group_status = _safe_lower(family_group.get("group_status"))
    if "recommended" in group_status:
        score += 0.05
    if "conflict" in group_status or "readability" in group_status:
        score -= 0.05

    # Penalize competitor documents for primary slots — they should go to LITERATURE_SOTA or EQUIVALENCE
    slot_type = slot_def.get("slot_type", "")
    if slot_type in CORE_SLOT_TYPES:
        group_reason = _safe_lower(family_group.get("recommended_canonical_reason", ""))
        group_name = _safe_lower(family_group.get("source_type", ""))
        if any(brand in group_reason for brand in COMPETITOR_BRANDS) or any(brand in group_name for brand in COMPETITOR_BRANDS):
            score -= 0.25

    return max(0.0, min(score, 1.0))


def _band_from_threshold(score: float, params: dict[str, Any]) -> str:
    if score >= params.get("high_confidence_threshold", 0.7):
        return "HIGH"
    if score >= params.get("medium_confidence_threshold", 0.5):
        return "MEDIUM"
    if score >= params.get("low_confidence_threshold", 0.2):
        return "LOW"
    return "MISSING"


def _candidate_confidence(candidate: dict[str, Any]) -> float:
    raw = candidate.get("confidence_score")
    if raw is None:
        raw = candidate.get("confidence")
    if raw is None:
        raw = candidate.get("ranking_score", 0.0)
    return max(0.0, min(float(raw), 1.0))


def _candidate_band(score: float) -> str:
    if score >= 0.85:
        return "HIGH"
    if score >= 0.6:
        return "MEDIUM"
    if score >= 0.3:
        return "LOW"
    return "MISSING"


def _detect_competitor_signals(file_name: str) -> list[str]:
    """Detect competitor brand names in filename that indicate this is not a primary source for the current project."""
    name_lower = _safe_lower(file_name)
    signals = []
    for brand in COMPETITOR_BRANDS:
        if brand in name_lower:
            signals.append(f"COMPETITOR_DOCUMENT:{brand.upper()}")
    return signals


def _project_affinity_score(file_name: str) -> float:
    """Return affinity boost for files that appear to belong to the current project (e.g. contain project codes)."""
    name_lower = _safe_lower(file_name)
    score = 0.0
    for ident in PROJECT_IDENTIFIERS:
        if ident in name_lower:
            score += 0.08
    return min(score, 0.25)


def _normalize_candidate(candidate: dict[str, Any], *, duplicate: bool = False, companion: bool = False) -> dict[str, Any]:
    file_path = candidate.get("file_path") or candidate.get("source_path") or candidate.get("relative_path") or ""
    file_name = candidate.get("file_name") or candidate.get("relative_path") or candidate.get("file_id") or ""
    score = _candidate_confidence(candidate)
    readability = candidate.get("readability_status") or "NEEDS_OPEN_FILE_CHECK"
    integrity = "HASH_PRESENT" if candidate.get("file_hash_sha256") else "METADATA_ONLY"
    negative_signals = list(candidate.get("negative_signals") or candidate.get("warnings") or [])
    size_bytes = int(candidate.get("file_size_bytes") or candidate.get("size_bytes") or 0)
    is_large = bool(candidate.get("is_large_file")) or size_bytes >= 100 * 1024 * 1024
    is_unreadable = bool(candidate.get("is_unreadable")) or readability in {"FAIL", "NEEDS_OPEN_FILE_CHECK"}

    # Detect competitor signals from filename
    competitor_signals = _detect_competitor_signals(file_name)
    negative_signals.extend(competitor_signals)
    negative_signals = list(dict.fromkeys(negative_signals))  # dedupe preserve order

    return {
        "file_id": candidate.get("file_id"),
        "file_path": file_path,
        "file_name": file_name,
        "document_type": candidate.get("auto_classified_type") or candidate.get("document_type") or "unknown",
        "confidence_score": round(score, 3),
        "confidence_band": _candidate_band(score),
        "file_size_bytes": size_bytes or None,
        "version_label": candidate.get("version_label"),
        "evidence_ref": file_path or candidate.get("file_id"),
        "readability_status": readability,
        "integrity_status": integrity,
        "is_large_file": is_large,
        "is_unreadable": is_unreadable,
        "is_duplicate": duplicate,
        "is_companion": companion,
        "negative_signals": negative_signals,
    }


def _normalize_candidates(group: dict[str, Any], key: str, *, duplicate: bool = False, companion: bool = False) -> list[dict[str, Any]]:
    return [
        _normalize_candidate(candidate, duplicate=duplicate, companion=companion)
        for candidate in group.get(key, []) or []
        if candidate.get("file_id")
    ]


def _merge_risk_flags(slot_type: str, group: dict[str, Any], candidate: dict[str, Any] | None) -> list[str]:
    flags: list[str] = []
    group_status = str(group.get("group_status") or "")
    if "CONFLICTING" in group_status:
        flags.append("VERSION_AMBIGUITY")
    if "DUPLICATE" in group_status:
        flags.append("DUPLICATES_PRESENT")
    if "READABILITY" in group_status:
        flags.append("READABILITY_LIMITATION")
    if candidate:
        if candidate.get("is_large_file"):
            flags.append("LARGE_FILE")
        if candidate.get("is_unreadable"):
            flags.append("NEEDS_OPEN_FILE_CHECK")
        if candidate.get("document_type") == "unknown" and slot_type in CORE_SLOT_TYPES:
            flags.append("UNKNOWN_CANNOT_BE_PRIMARY")
        for signal in candidate.get("negative_signals", []):
            normalized = _safe_lower(signal).replace(" ", "_").upper()
            if normalized:
                flags.append(normalized)
    return sorted(set(flags))


def _score_slot_confidence(
    slot_type: str,
    group: dict[str, Any],
    candidate: dict[str, Any] | None,
    match_score: float,
    params: dict[str, Any],
) -> tuple[float, str]:
    base_score = float(group.get("confidence") or 0.0)
    if candidate:
        base_score = max(base_score, float(candidate.get("confidence_score", 0.0)))

    score = base_score * (0.6 + 0.4 * match_score)
    group_status = _safe_lower(group.get("group_status"))
    if "multiple_candidates" in group_status:
        score -= 0.1
    if "conflict" in group_status:
        score -= 0.15
    if "duplicate" in group_status:
        score -= 0.05
    if "low_confidence" in group_status:
        score -= 0.15

    if candidate:
        if candidate.get("is_large_file"):
            score -= 0.2
        if candidate.get("readability_status") == "NEEDS_OPEN_FILE_CHECK":
            score -= 0.2
        if candidate.get("readability_status") == "FAIL":
            score -= 0.35
        if candidate.get("document_type") == "unknown" and slot_type in CORE_SLOT_TYPES:
            score = min(score, params.get("medium_confidence_threshold", 0.5) - 0.01)

        # Project affinity boost: files with project identifiers are more likely to be the primary source
        file_name = candidate.get("file_name") or ""
        score += _project_affinity_score(file_name)

        # Competitor penalty: competitor documents should not be primary canonical sources
        competitor_penalty = 0.0
        for signal in candidate.get("negative_signals", []):
            if str(signal).startswith("COMPETITOR_DOCUMENT"):
                competitor_penalty += 0.30
        if competitor_penalty > 0:
            score -= competitor_penalty
            # Also cap competitor documents at MEDIUM for primary slots
            if slot_type in CORE_SLOT_TYPES and score >= params.get("high_confidence_threshold", 0.7):
                score = min(score, params.get("medium_confidence_threshold", 0.5) + 0.01)

    score = max(0.0, min(round(score, 3), 1.0))
    band = _band_from_threshold(score, params)

    if candidate and candidate.get("is_large_file") and candidate.get("readability_status") != "PASS" and band == "HIGH":
        band = "MEDIUM"
        score = min(score, params.get("high_confidence_threshold", 0.7) - 0.01)
    if candidate and candidate.get("document_type") == "unknown" and band == "HIGH":
        band = "MEDIUM"
        score = min(score, params.get("high_confidence_threshold", 0.7) - 0.01)

    return score, band


def _integrity_status(group: dict[str, Any], candidate: dict[str, Any] | None) -> str:
    if candidate and candidate.get("integrity_status") == "HASH_PRESENT":
        return "HASH_PRESENT"
    if group.get("duplicate_files"):
        return "DUPLICATE_CHAIN_PRESENT"
    if group.get("open_file_required"):
        return "OPEN_FILE_CHECK_REQUIRED"
    return "METADATA_ONLY"


def _readability_status(group: dict[str, Any], candidate: dict[str, Any] | None) -> str:
    if candidate and candidate.get("readability_status"):
        return str(candidate["readability_status"])
    if group.get("open_file_required"):
        return "NEEDS_OPEN_FILE_CHECK"
    return "UNKNOWN"


def _evidence_basis(group: dict[str, Any], candidate: dict[str, Any] | None, risk_flags: list[str]) -> list[str]:
    basis = []
    group_reason = group.get("recommended_canonical_reason")
    if group_reason:
        basis.append(str(group_reason))
    group_status = group.get("group_status")
    if group_status:
        basis.append(f"group_status={group_status}")
    if candidate:
        basis.append(f"candidate={candidate.get('file_name')}")
        if candidate.get("evidence_ref"):
            basis.append(f"evidence={candidate.get('evidence_ref')}")
        if candidate.get("readability_status"):
            basis.append(f"readability={candidate.get('readability_status')}")
    basis.extend([f"risk={flag}" for flag in risk_flags[:3]])
    return basis


def _primary_action_hint(slot_type: str, band: str, risk_flags: list[str], has_candidate: bool) -> str:
    if not has_candidate:
        return f"Request or justify missing {slot_type}"
    if "NEEDS_OPEN_FILE_CHECK" in risk_flags or band in {"LOW", "MISSING"}:
        return f"Run open-file check for {slot_type}"
    if band == "MEDIUM":
        return f"Reviewer should confirm or reselect {slot_type}"
    return f"Stage {slot_type} recommendation for human confirmation"


def _slot_specific_candidate_score(slot_type: str, candidate: dict[str, Any]) -> float:
    """Adjust candidate score based on slot-type-specific relevance."""
    name = _safe_lower(candidate.get("file_name", ""))
    score = float(candidate.get("confidence_score", 0.0))

    if slot_type == "CER_CEP":
        if "clinical evaluation report" in name:
            score += 0.35
        elif "clinical evaluation plan" in name:
            score += 0.20
        elif "cer" in name.split() or "_cer_" in name or name.startswith("cer_") or name.endswith("_cer"):
            score += 0.10
        if "certificate" in name or "iso 13485" in name or "iso 9001" in name or "iso 14001" in name or "authorization" in name:
            score -= 0.5
        if "master technical documentation" in name or "technical document list" in name:
            score -= 0.3

    elif slot_type == "RMF_RISK":
        if "risk management plan" in name or "risk management report" in name:
            score += 0.35
        elif "risk management" in name:
            score += 0.20
        if "iso 14971" in name:
            score += 0.25
        elif "pfmea" in name:
            score += 0.15
        elif "fmea" in name:
            score += 0.10
        if "software release" in name or "software development" in name or "software verification" in name or "software unit test" in name or "software integration test" in name:
            score -= 0.4
        if "design verification report" in name or "design validation" in name or "production flow chart" in name or "work instruction" in name or "installation guide" in name:
            score -= 0.25

    elif slot_type == "IFU":
        if "instructions for use" in name or "ifu" in name.split() or "_ifu_" in name:
            score += 0.15
        if "kundeninfo" in name:
            score -= 0.6

    elif slot_type == "PMCF":
        if "pmcf" in name or "post-market clinical follow" in name:
            score += 0.2
        if "clinical trial protocol" in name and "pmcf" not in name:
            score -= 0.1

    return score


def _make_slot(slot_def: dict[str, Any], family_group: dict[str, Any], params: dict[str, Any], match_score: float) -> dict[str, Any]:
    candidates = _normalize_candidates(family_group, "candidates")
    alternatives = _normalize_candidates(family_group, "alternatives")
    companions = _normalize_candidates(family_group, "companion_files", companion=True)
    duplicates = _normalize_candidates(family_group, "duplicate_files", duplicate=True)
    open_file = _normalize_candidates(family_group, "open_file_required")

    # Reorder candidates based on slot-type-specific relevance
    slot_type = slot_def["slot_type"]
    if candidates:
        candidates = sorted(candidates, key=lambda c: _slot_specific_candidate_score(slot_type, c), reverse=True)
    if alternatives:
        alternatives = sorted(alternatives, key=lambda c: _slot_specific_candidate_score(slot_type, c), reverse=True)

    best_candidate = candidates[0] if candidates else (alternatives[0] if alternatives else None)
    score, band = _score_slot_confidence(slot_def["slot_type"], family_group, best_candidate, match_score, params)
    risk_flags = _merge_risk_flags(slot_def["slot_type"], family_group, best_candidate)
    integrity_status = _integrity_status(family_group, best_candidate)
    readability_status = _readability_status(family_group, best_candidate)
    evidence_basis = _evidence_basis(family_group, best_candidate, risk_flags)
    has_candidate = best_candidate is not None

    status = "RECOMMENDED" if has_candidate else "MISSING"
    if band in {"MISSING", "LOW"} and has_candidate:
        status = "OPEN_FILE_CHECK"

    return {
        "slot_id": f"slot-{slot_def['slot_type'].lower()}-{uuid.uuid4().hex[:8]}",
        "slot_type": slot_def["slot_type"],
        "slot_status": status,
        "recommended_canonical_file_id": best_candidate.get("file_id") if best_candidate else None,
        "recommended_canonical_reason": family_group.get("recommended_canonical_reason")
        or f"Matched {family_group.get('source_type') or family_group.get('source_family_type')} to {slot_def['slot_type']}",
        "confidence_score": round(score, 3),
        "confidence_band": band,
        "evidence_basis": evidence_basis,
        "risk_flags": risk_flags,
        "integrity_status": integrity_status,
        "readability_status": readability_status,
        "integrity_check_summary": f"Integrity={integrity_status}; readability={readability_status}",
        "direct_evidence_link": best_candidate.get("evidence_ref") if best_candidate else None,
        "raw_candidate_count": sum(
            len(family_group.get(key, []) or [])
            for key in ("candidates", "alternatives", "companion_files", "duplicate_files", "open_file_required")
        ),
        "primary_action_hint": _primary_action_hint(slot_def["slot_type"], band, risk_flags, has_candidate),
        "candidates": candidates,
        "alternatives": alternatives,
        "companion_files": companions,
        "duplicate_files": duplicates,
        "open_file_required": open_file,
        "missing_reason": family_group.get("missing_reason"),
    }


def _make_missing_slot(slot_type: str, reason: str) -> dict[str, Any]:
    return {
        "slot_id": f"slot-{slot_type.lower()}-{uuid.uuid4().hex[:8]}",
        "slot_type": slot_type,
        "slot_status": "MISSING",
        "recommended_canonical_file_id": None,
        "recommended_canonical_reason": reason,
        "confidence_score": 0.0,
        "confidence_band": "MISSING",
        "evidence_basis": [reason],
        "risk_flags": ["MISSING_SOURCE"],
        "integrity_status": "NOT_AVAILABLE",
        "readability_status": "NOT_AVAILABLE",
        "integrity_check_summary": "No evidence file available for this slot.",
        "direct_evidence_link": None,
        "raw_candidate_count": 0,
        "primary_action_hint": f"Request or justify missing {slot_type}",
        "candidates": [],
        "alternatives": [],
        "companion_files": [],
        "duplicate_files": [],
        "open_file_required": [],
        "missing_reason": reason,
    }


def build_slots_from_family_groups(
    family_groups: list[dict[str, Any]],
    flavor_name: str = "BALANCED",
) -> list[dict[str, Any]]:
    params = get_flavor_profile(flavor_name)
    slots: list[dict[str, Any]] = []

    for slot_def in PRIMARY_SLOTS:
        matches = []
        for family_group in family_groups:
            match_score = _score_slot_match(slot_def, family_group)
            if match_score > 0:
                matches.append((match_score, family_group))

        matches.sort(key=lambda item: item[0], reverse=True)

        if not matches:
            slots.append(_make_missing_slot(slot_def["slot_type"], "No matching source family found in current package"))
            continue

        # Merge all matching groups so that files from overlapping types
        # (e.g. literature + sota) are preserved in a single slot.
        top_score, top_group = matches[0]
        if len(matches) > 1:
            merged_group = dict(top_group)
            for key in ("candidates", "alternatives", "companion_files", "duplicate_files", "open_file_required"):
                merged_group[key] = list(top_group.get(key) or [])
            for _score, group in matches[1:]:
                for key in ("candidates", "alternatives", "companion_files", "duplicate_files", "open_file_required"):
                    merged_group[key].extend(list(group.get(key) or []))
            slots.append(_make_slot(slot_def, merged_group, params, top_score))
        else:
            slots.append(_make_slot(slot_def, top_group, params, top_score))

    return slots


def build_confidence_heatmap(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    heatmap = []
    for slot in slots:
        negative_signals: list[str] = []
        for candidate in slot.get("candidates", [])[:1]:
            negative_signals.extend(candidate.get("negative_signals", []))
        heatmap.append(
            {
                "slot_type": slot["slot_type"],
                "confidence_band": slot["confidence_band"],
                "confidence_score": slot["confidence_score"],
                "candidate_count": slot.get("raw_candidate_count", len(slot.get("candidates", []))),
                "recommendation_reason": slot.get("recommended_canonical_reason", ""),
                "evidence_basis": slot.get("evidence_basis", []),
                "risk_flags": slot.get("risk_flags", []),
                "integrity_status": slot.get("integrity_status", "UNKNOWN"),
                "readability_status": slot.get("readability_status", "UNKNOWN"),
                "negative_signals": sorted(set(negative_signals)),
            }
        )
    return heatmap
