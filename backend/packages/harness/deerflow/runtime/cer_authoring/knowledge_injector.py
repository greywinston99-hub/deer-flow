"""V5 Knowledge Injector — runtime knowledge injection for HC Gates, nb_precheck, and cer_writing.

Provides three injection points:
1. HC Gate context: defect patterns relevant to each human confirmation gate
2. NB Simulation: BSI/TUV SUD reviewer profiles for pre-submission simulation
3. Per-Section Defenses: CER chapter-specific authoring defense rules

All data sourced from the V5 knowledge layer at runtime.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

# Gate → relevant defect types mapping (V5 enhanced)
_GATE_DEFECT_MAP: dict[str, list[str]] = {
    "intake_pack_review": ["DO-001", "CV-001", "DT-001"],
    "device_profile": ["DO-001", "CV-001", "DT-001"],
    "claim_decomposition": ["DO-001", "CL-001", "CM-001"],
    "pico_derivation": ["EV-001", "CL-001"],
    "sota_search_strategy": ["EV-001", "TR-001"],
    "evidence_appraisal": ["EV-001", "CM-001", "TR-001"],
    "endpoint_extraction": ["EV-001", "CL-001"],
    "prisma_flow_review": ["EV-001", "DT-001"],
    "fulltext_basis_gate": ["EV-001"],
    "sota_endpoint_gate": ["EV-001", "TR-001"],
    "claim_sota_alignment": ["EV-001", "DT-001"],
    "pre_writer_summary": ["DO-001", "EV-001", "BR-001", "DT-001"],
    "cer_draft_review": ["DO-001", "EV-001", "BR-001", "LB-001", "DQ-001"],
    "device_profile_iteration": ["DO-001", "DT-001"],
    "review_quick_scan": ["DQ-001", "DT-001"],
}

# CER chapter → section_id mapping
_CHAPTER_TO_SECTION: dict[str, str] = {
    "CER-02": "§2 Device Description",
    "CER-03": "§3 State of the Art",
    "CER-04": "§4 Clinical Evidence",
    "CER-05": "§5 Benefit-Risk Analysis",
    "CER-06": "§6 GSPR Compliance",
    "CER-07": "§7 PMS/PMCF",
    "CER-09": "IFU/Labeling/SSCP",
}


def _load_asset(filename: str) -> dict[str, Any]:
    """Load a knowledge asset JSON file."""
    try:
        return json.loads((_KNOWLEDGE_DIR / filename).read_text())
    except Exception:
        return {}


def inject_defect_context_for_gate(gate_name: str) -> dict[str, Any]:
    """Return V5 defect context for a specific HC gate.

    Injects into interrupt() payload to give human reviewers
    awareness of what NB auditors typically flag at this decision point.
    """
    defect_types = _GATE_DEFECT_MAP.get(gate_name, [])
    if not defect_types:
        return {}

    dp = _load_asset("defect_patterns.json")
    patterns = dp.get("patterns", [])
    sd = _load_asset("section_defense_rules.json")

    context: dict[str, Any] = {
        "_v5_knowledge": True,
        "gate": gate_name,
        "nb_defects_relevant": [],
    }

    for dt in defect_types:
        # Find matching patterns
        for p in patterns:
            if not isinstance(p, dict):
                continue
            linked = p.get("linked_nb_codes", [])
            if dt in linked:
                v5 = p.get("v5_enrichment", {})
                context["nb_defects_relevant"].append({
                    "defect_type": dt,
                    "v5_findings": v5.get("per_defect_type", {}).get(dt, "?"),
                    "pattern_name": p.get("pattern_name", dt),
                    "nb_would_flag": p.get("description", ""),
                    "authoring_defense": p.get("authoring_defense_rules", [])[:3],
                    "sample_nb_quotes": p.get("sample_nb_quotes", [])[:1],
                })
                break

    # Add section-specific context from section_defense_rules
    chapters = sd.get("chapters", [])
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        ch_defects = ch.get("v5_defect_frequencies", {})
        relevant = {dt: count for dt, count in ch_defects.items() if dt in defect_types}
        if relevant:
            ch_id = ch.get("chapter_id", "")
            context.setdefault("section_context", {})[ch_id] = {
                "section_name": _CHAPTER_TO_SECTION.get(ch_id, ch_id),
                "relevant_v5_defects": relevant,
                "authoring_defense": ch.get("v5_authoring_defense", [])[:3],
            }

    context["_summary"] = (
        f"NB auditors have flagged {sum(len(c.get('sample_nb_quotes',[])) for c in context['nb_defects_relevant'])} "
        f"real issues in {len(context['nb_defects_relevant'])} defect categories at this decision point. "
        f"Review the authoring_defense rules below to preempt these findings."
    )

    return context


def build_nb_simulation_context(nb_body: str | None = None) -> dict[str, Any]:
    """Build NB body simulation context for nb_precheck.

    Returns BSI/TUV SUD reviewer profiles with known patterns,
    to simulate NB review BEFORE document export.
    """
    bp = _load_asset("nb_body_profiles.json")
    profiles = bp.get("profiles", {})

    result: dict[str, Any] = {"_v5_nb_simulation": True, "nb_bodies_available": list(profiles.keys())}

    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        if nb_body and name.lower() != nb_body.lower():
            continue

        reviewers = profile.get("known_reviewers", [])
        result[name] = {
            "review_format": profile.get("review_format_detail", {}),
            "reviewers": [
                {"name": r.get("name", ""), "role": r.get("role", ""), "known_patterns": r.get("patterns", [])}
                for r in reviewers
            ],
            "common_focus": list(profile.get("v5_defect_statistics", {}).keys())[:5],
            "writing_advice": profile.get("writing_advice", {}),
        }

    result["_simulation_guidance"] = (
        f"SIMULATE {nb_body or 'BSI/TUV SUD'} REVIEW: "
        "Check the CER against known reviewer patterns. "
        "Flag any section where the CER would trigger a known NB question pattern."
    )

    return result


def get_per_section_defenses(section_id: str | None = None) -> dict[str, Any]:
    """Return per-section authoring defense rules for cer_writing.

    If section_id is provided, returns only that section's defenses.
    Otherwise returns all sections.
    """
    sd = _load_asset("section_defense_rules.json")
    chapters = sd.get("chapters", [])
    dp = _load_asset("defect_patterns.json")

    result: dict[str, Any] = {"_v5_per_section_defenses": True}
    defenses: dict[str, Any] = {}

    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        ch_id = ch.get("chapter_id", "")
        if section_id and ch_id != section_id:
            continue

        section_name = _CHAPTER_TO_SECTION.get(ch_id, ch_id)
        ch_defenses = ch.get("v5_authoring_defense", [])
        ch_defects = ch.get("v5_defect_frequencies", {})

        # Enrich with defect pattern sample quotes
        enriched_defenses = []
        for d in ch_defenses:
            enriched_defenses.append({"rule": d})
        # Add top defect-specific guidance
        top_defects = sorted(ch_defects.items(), key=lambda x: x[1], reverse=True)[:3]
        for dt, count in top_defects:
            for p in dp.get("patterns", []):
                if not isinstance(p, dict):
                    continue
                if dt in p.get("linked_nb_codes", []):
                    quotes = p.get("sample_nb_quotes", [])
                    if quotes:
                        enriched_defenses.append({
                            "rule": f"NB CHECK ({dt}, {count} known findings): {quotes[0][:200]}"
                        })
                    break

        defenses[ch_id] = {
            "section_name": section_name,
            "v5_defect_count": sum(ch_defects.values()),
            "top_defects": top_defects,
            "defense_rules": enriched_defenses,
        }

    result["sections"] = defenses
    return result


def get_v5_knowledge_summary() -> dict[str, Any]:
    """Return a summary of all V5 knowledge available."""
    dp = _load_asset("defect_patterns.json")
    sd = _load_asset("section_defense_rules.json")
    bp = _load_asset("nb_body_profiles.json")
    rp = _load_asset("remediation_playbook.json")

    return {
        "_v5_summary": True,
        "defect_patterns": len(dp.get("patterns", [])),
        "nb_defect_codes": dp.get("nb_linked_patterns", 0),
        "section_defenses": len(sd.get("chapters", [])),
        "nb_bodies_profiled": len(bp.get("profiles", {})),
        "remediation_templates": len(rp.get("playbook", {}) if isinstance(rp.get("playbook", {}), dict) else []),
    }
