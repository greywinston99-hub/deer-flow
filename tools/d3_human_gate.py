"""
Phase C Step 9 — D3 Human Gate Integration
Unified human gate packet format, auto-generation from crosswalk data, and KB writeback.
All determinations are advisory. Human reviewer retains final authority.
"""

import json, os, sys, re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from copy import deepcopy

# ============================================================
# UNIFIED HUMAN GATE PACKET FORMAT (D3 Schema v1)
# ============================================================

D3_SCHEMA = {
    "schema": "d3_human_gate_packet",
    "version": "v1",
    "description": "Unified human review packet for NB-AI crosswalk findings. Each finding includes evidence, regulatory anchor, severity, and recommended action. Human reviewer marks decision (YES=AI correct, NO=AI wrong, PARTIAL=partial match, UNCLEAR=needs clarification).",
    "fields": {
        "packet_id": "Unique packet identifier",
        "project_id": "Source project (e.g., PROJECT_017)",
        "generated_at": "ISO timestamp of generation",
        "total_findings": "Number of findings in this packet",
        "human_review_status": "pending | in_progress | completed",
        "human_reviewer": "Name/ID of human reviewer (filled after review)",
        "human_review_completed_at": "ISO timestamp of review completion",
        "findings": "Array of finding items (see finding_item schema)",
    },
    "finding_item": {
        "finding_id": "Unique finding ID within packet",
        "finding_text": "AI-generated finding or crosswalk text",
        "evidence": {
            "nb_observation_id": "Reference to original NB observation",
            "nb_question_text": "Original NB question text",
            "nb_category": "NB-assigned category",
            "nb_round": "NB review round",
            "ai_response_text": "AI's response or matching text",
            "match_quality": "STRONG | MODERATE | WEAK | NO_MATCH",
            "overlap_terms": "Key overlapping terms between AI and NB",
        },
        "regulatory_anchor": {
            "mdr_article": "Relevant MDR article (e.g., Art 61(4))",
            "standard": "Relevant harmonized standard (e.g., EN 60601-2-2)",
            "guideline": "Relevant MDCG or other guideline",
            "gspar": "Relevant GSPR number (e.g., GSPR 1, GSPR 23.4)",
        },
        "severity": {
            "level": "CRITICAL | MAJOR | MINOR | INFO",
            "rationale": "Why this severity was assigned",
            "regulatory_impact": "NON_COMPLIANCE | CONDITIONAL_APPROVAL | MINOR_FINDING | NO_IMPACT",
        },
        "recommended_action": {
            "action_type": "PROVIDE_EVIDENCE | CLARIFY_SCOPE | UPDATE_DOCUMENT | CLINICAL_INVESTIGATION | PMCF_EXTENSION | HUMAN_JUDGMENT_REQUIRED",
            "description": "What the manufacturer should do",
            "timeline": "IMMEDIATE | NEXT_ROUND | BEFORE_APPROVAL | ONGOING",
        },
        "kb_feedback": {
            "concern_category": "Category for KB indexing",
            "canonical_concern": "Normalized concern text for KB lookup",
            "device_type": "Affected device type",
        },
        "human_decision": {
            "decision": "PENDING | YES | NO | PARTIAL | UNCLEAR",
            "notes": "Human reviewer notes",
            "kb_update": "CONFIRM | REJECT | MODIFY | NO_ACTION",
            "corrected_category": "If NO/PARTIAL: corrected category",
            "reviewed_at": "Timestamp of human decision",
        },
    },
}

# ============================================================
# REGULATORY ANCHOR MAPPING
# ============================================================

CATEGORY_REGULATORY_ANCHOR = {
    "IFU_Labeling_Gap": {
        "mdr_article": "Annex I GSPR 23.1-23.4",
        "standard": "EN 1041, ISO 15223-1",
        "guideline": "MDCG 2019-9",
        "gspar": "GSPR 23",
    },
    "Clinical_Evidence_Insufficiency": {
        "mdr_article": "Art 61, Annex XIV Part A",
        "standard": "MEDDEV 2.7/1 Rev 4, MDCG 2020-6",
        "guideline": "MDCG 2020-5, MDCG 2020-6",
        "gspar": "GSPR 1, GSPR 6",
    },
    "Risk_Management_Gap": {
        "mdr_article": "Annex I GSPR 1-5",
        "standard": "EN ISO 14971:2019+A11:2021",
        "guideline": "MDCG 2019-16",
        "gspar": "GSPR 1-5",
    },
    "Biocompatibility": {
        "mdr_article": "Annex I GSPR 10",
        "standard": "EN ISO 10993 series",
        "guideline": "MDCG 2020-6 Sec 5.2.3",
        "gspar": "GSPR 10",
    },
    "GSPR_Standards_Compliance": {
        "mdr_article": "Annex I GSPR",
        "standard": "Various harmonized standards",
        "guideline": "MDCG 2019-16",
        "gspar": "GSPR 1-23",
    },
    "Software_Cybersecurity": {
        "mdr_article": "Annex I GSPR 17",
        "standard": "IEC 62304, IEC 81001-5-1",
        "guideline": "MDCG 2019-16, MDCG 2020-1",
        "gspar": "GSPR 17",
    },
    "Sterilization_Reprocessing": {
        "mdr_article": "Annex I GSPR 11.1-11.7",
        "standard": "EN ISO 11135, EN ISO 11137",
        "guideline": "MDCG 2020-6",
        "gspar": "GSPR 11",
    },
    "Usability_Human_Factors": {
        "mdr_article": "Annex I GSPR 5",
        "standard": "EN 62366-1, IEC 62366-2",
        "guideline": "MDCG 2019-16",
        "gspar": "GSPR 5",
    },
    "General_Regulatory": {
        "mdr_article": "MDR Art 10, Annex I",
        "standard": "EN ISO 13485",
        "guideline": "MDCG 2019-16",
        "gspar": "GSPR 1-4",
    },
    "Electrical_Safety_EMC": {
        "mdr_article": "Annex I GSPR 10, 11",
        "standard": "EN 60601-1, EN 60601-1-2",
        "guideline": "MDCG 2019-16",
        "gspar": "GSPR 10, 11",
    },
    "Manufacturing_Process_Control": {
        "mdr_article": "Annex I GSPR 4, Art 10(9)",
        "standard": "EN ISO 13485 §7.5.2",
        "guideline": "MDCG 2019-16",
        "gspar": "GSPR 4",
    },
    "Design_Verification_Validation": {
        "mdr_article": "Annex I GSPR 5, Annex II",
        "standard": "EN ISO 13485 §7.3",
        "guideline": "MDCG 2019-16",
        "gspar": "GSPR 5",
    },
    "Material_Chemical_Characterization": {
        "mdr_article": "Annex I GSPR 10.1-10.4",
        "standard": "ISO 10993-18, ISO 10993-17",
        "guideline": "MDCG 2020-6",
        "gspar": "GSPR 10",
    },
    "PMCF_Plan": {
        "mdr_article": "Art 61(11), Annex XIV Part B",
        "standard": "MDCG 2020-7, MDCG 2020-8",
        "guideline": "MEDDEV 2.12/2 Rev 2",
        "gspar": "GSPR 1",
    },
    "Benefit_Risk": {
        "mdr_article": "Art 61(1), Annex I GSPR 1",
        "standard": "MDCG 2020-6",
        "guideline": "ISO 14971",
        "gspar": "GSPR 1",
    },
    "Equivalence_Justification": {
        "mdr_article": "Art 61(4)-(5), Annex XIV Part A",
        "standard": "MDCG 2020-5",
        "guideline": "MEDDEV 2.7/1 Rev 4 A1",
        "gspar": "GSPR 1",
    },
}


def get_regulatory_anchor(category: str) -> dict:
    """Map a concern category to its regulatory anchor."""
    for key, anchor in CATEGORY_REGULATORY_ANCHOR.items():
        if key.lower().replace("_", "") in category.lower().replace("_", "").replace(" ", ""):
            return anchor
    return CATEGORY_REGULATORY_ANCHOR.get("General_Regulatory", {})


def get_severity_from_quality(match_quality: str, category: str) -> dict:
    """Infer severity from match quality and category."""
    severity_map = {
        "STRONG": {
            "level": "MAJOR",
            "rationale": "Strong alignment with NB concern — indicates genuine regulatory gap",
            "regulatory_impact": "CONDITIONAL_APPROVAL" if "label" in category.lower() or "ifu" in category.lower() else "MINOR_FINDING",
        },
        "MODERATE": {
            "level": "MINOR",
            "rationale": "Partial alignment — AI found a relevant but not exact match",
            "regulatory_impact": "MINOR_FINDING",
        },
        "WEAK": {
            "level": "INFO",
            "rationale": "Weak signal — may indicate emerging concern or noise",
            "regulatory_impact": "NO_IMPACT",
        },
        "NO_MATCH": {
            "level": "INFO",
            "rationale": "AI didn't identify this NB concern — potential blind spot",
            "regulatory_impact": "NO_IMPACT",
        },
    }
    default = severity_map.get(match_quality, {"level": "INFO", "rationale": "Unknown", "regulatory_impact": "NO_IMPACT"})

    # Elevate for clinical evidence and risk management
    if category in ("Clinical_Evidence_Insufficiency", "Risk_Management_Gap", "Software_Cybersecurity"):
        if match_quality in ("STRONG", "MODERATE"):
            default = {"level": "CRITICAL", "rationale": f"{category} concern with {match_quality} alignment — may affect safety/performance", "regulatory_impact": "NON_COMPLIANCE"}

    return default


def get_recommended_action(category: str, match_quality: str) -> dict:
    """Recommend manufacturer action based on category and match quality."""
    if match_quality in ("STRONG", "MODERATE"):
        if category in ("Clinical_Evidence_Insufficiency", "Equivalence_Justification"):
            return {"action_type": "CLINICAL_INVESTIGATION", "description": "Consider clinical investigation or expanded literature review", "timeline": "BEFORE_APPROVAL"}
        elif category in ("PMCF_Plan",):
            return {"action_type": "PMCF_EXTENSION", "description": "Expand PMCF plan with proactive data sources", "timeline": "NEXT_ROUND"}
        elif category in ("IFU_Labeling_Gap", "General_Regulatory"):
            return {"action_type": "UPDATE_DOCUMENT", "description": "Update IFU/labeling/technical documentation", "timeline": "NEXT_ROUND"}
        elif category in ("Risk_Management_Gap",):
            return {"action_type": "PROVIDE_EVIDENCE", "description": "Provide risk-benefit analysis or risk control evidence", "timeline": "NEXT_ROUND"}
        elif category in ("Software_Cybersecurity",):
            return {"action_type": "PROVIDE_EVIDENCE", "description": "Provide software lifecycle documentation or cybersecurity risk assessment", "timeline": "BEFORE_APPROVAL"}
        elif category in ("Biocompatibility", "Material_Chemical_Characterization"):
            return {"action_type": "PROVIDE_EVIDENCE", "description": "Provide biocompatibility test reports or material characterization data", "timeline": "BEFORE_APPROVAL"}
        else:
            return {"action_type": "PROVIDE_EVIDENCE", "description": "Provide supporting evidence for this concern", "timeline": "NEXT_ROUND"}
    elif match_quality == "WEAK":
        return {"action_type": "CLARIFY_SCOPE", "description": "Clarify scope or provide additional context", "timeline": "NEXT_ROUND"}
    else:
        return {"action_type": "HUMAN_JUDGMENT_REQUIRED", "description": "AI missed this NB concern — human reviewer must assess relevance", "timeline": "IMMEDIATE"}


# Known project-to-device mapping (synchronized with knowledge_extractor.py)
_PROJECT_DEVICE_TYPES = {
    "PROJECT_012": "SPECT_CT_System",
    "PROJECT_013": "Powered_Surgical_Stapler",
    "PROJECT_017": "HF_Surgical_Generator",
    "PROJECT_025": "Enteral_Feeding_Sets",
    "PROJECT_030": "Vascular_Catheter",
    "PROJECT_031": "Insulin_Pump",
    "PROJECT_037": "Surgical_Gloves",
    "PROJECT_038": "Connecting_Tube",
    "PROJECT_041": "Cold_Pack",
    "PROJECT_002": "Cardiovascular_Imaging_Software",
    "PROJECT_019": "Photodynamic_Therapy_Device",
    "PROJECT_023": "VAD_Controller_System",
    "PROJECT_029": "VAD_Controller_System",
    "PROJECT_039": "Orthopedic_Joint_Implant",
}


def _infer_device_type(project_id: str, crosswalk_data: dict, item: dict) -> str:
    """Infer device type from multiple sources."""
    # 1. From item directly
    dt = item.get("device_type", "")
    if dt:
        return dt
    # 2. From crosswalk data
    dt = crosswalk_data.get("device_type", "")
    if dt:
        return dt
    # 3. From known project mapping
    return _PROJECT_DEVICE_TYPES.get(project_id, "UNKNOWN")


# ============================================================
# PACKET GENERATION
# ============================================================

def generate_human_gate_packet(project_id: str, crosswalk_data: dict,
                                nb_observations_data: Optional[dict] = None) -> dict:
    """Generate a D3 human gate packet from crosswalk data."""
    details = crosswalk_data.get("details", crosswalk_data.get("results", []))
    if not details:
        return {"error": "No crosswalk details found", "project_id": project_id}

    findings = []
    for i, item in enumerate(details):
        finding_id = item.get("nb_id", item.get("finding_id", f"{project_id}-{i:04d}"))
        finding_text = item.get("best_ao_text", item.get("finding_text", item.get("text", "")))
        nb_text = item.get("nb_question", item.get("text", ""))
        category = item.get("nb_category", item.get("category", "General_Regulatory"))
        match_quality = item.get("match_quality", "NO_MATCH")
        overlap = item.get("overlap_terms", [])

        finding = {
            "finding_id": finding_id,
            "finding_text": str(finding_text)[:500],
            "evidence": {
                "nb_observation_id": finding_id,
                "nb_question_text": str(nb_text)[:500],
                "nb_category": category,
                "nb_round": item.get("nb_round", item.get("round", "")),
                "ai_response_text": str(finding_text)[:500],
                "match_quality": match_quality,
                "overlap_terms": overlap[:10] if isinstance(overlap, list) else [],
            },
            "regulatory_anchor": get_regulatory_anchor(category),
            "severity": get_severity_from_quality(match_quality, category),
            "recommended_action": get_recommended_action(category, match_quality),
            "kb_feedback": {
                "concern_category": category,
                "canonical_concern": _normalize_concern(nb_text, category),
                "device_type": _infer_device_type(project_id, crosswalk_data, item),
            },
            "human_decision": {
                "decision": "PENDING",
                "notes": "",
                "kb_update": "NO_ACTION",
                "corrected_category": "",
                "reviewed_at": "",
            },
        }
        findings.append(finding)

    packet = {
        "schema": "d3_human_gate_packet",
        "version": "v1",
        "packet_id": f"D3-{project_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "project_id": project_id,
        "generated_at": datetime.now().isoformat(),
        "total_findings": len(findings),
        "human_review_status": "pending",
        "human_reviewer": "",
        "human_review_completed_at": "",
        "findings": findings,
        "summary": {
            "STRONG": sum(1 for f in findings if f["evidence"]["match_quality"] == "STRONG"),
            "MODERATE": sum(1 for f in findings if f["evidence"]["match_quality"] == "MODERATE"),
            "WEAK": sum(1 for f in findings if f["evidence"]["match_quality"] == "WEAK"),
            "NO_MATCH": sum(1 for f in findings if f["evidence"]["match_quality"] == "NO_MATCH"),
            "CRITICAL": sum(1 for f in findings if f["severity"]["level"] == "CRITICAL"),
            "MAJOR": sum(1 for f in findings if f["severity"]["level"] == "MAJOR"),
            "MINOR": sum(1 for f in findings if f["severity"]["level"] == "MINOR"),
            "INFO": sum(1 for f in findings if f["severity"]["level"] == "INFO"),
        },
    }

    return packet


def _normalize_concern(text: str, category: str) -> str:
    """Normalize concern text for KB lookup."""
    if not text:
        return ""
    # Truncate and clean
    text = str(text)[:200].strip()
    text = re.sub(r'\d+[\.\)]\s*', '', text)  # Remove leading numbers
    text = re.sub(r'[Pp]lease\s+(provide|submit|send|attach|upload|add|specify|clarify|explain|describe|confirm|check|ensure|review|update|revise|amend|consider|justify|detail)\s+', '', text)
    words = text.split()
    if len(words) > 15:
        text = ' '.join(words[:15]) + '...'
    return text


# ============================================================
# KB WRITEBACK PATH
# ============================================================

def apply_human_decisions(packet: dict, kb_path: str) -> dict:
    """Apply human reviewer decisions to update KB CONFIRMED status."""
    try:
        with open(kb_path, 'r', encoding='utf-8') as f:
            kb = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {"error": f"Cannot read KB: {e}", "updates_applied": 0}

    device_types = kb.get("device_types", {})
    updates_log = []
    applied = 0

    for finding in packet.get("findings", []):
        hd = finding.get("human_decision", {})
        decision = hd.get("decision", "PENDING")
        kb_update = hd.get("kb_update", "NO_ACTION")

        if decision == "PENDING" or kb_update == "NO_ACTION":
            continue

        kb_feedback = finding.get("kb_feedback", {})
        device_type = kb_feedback.get("device_type", "")
        concern = kb_feedback.get("canonical_concern", "")
        category = kb_feedback.get("concern_category", "")

        if device_type not in device_types or not concern:
            continue

        dt_entry = device_types[device_type]
        concerns = dt_entry.get("typical_nb_concerns", [])

        # Find matching concern
        for c in concerns:
            if c.get("concern", "") == concern or c.get("category", "") == category:
                old_maturity = c.get("knowledge_maturity", "")
                old_conf = c.get("confidence", 0)

                if kb_update == "CONFIRM":
                    c["knowledge_maturity"] = "CONFIRMED"
                    c["confidence"] = min(0.98, old_conf + 0.10)
                    c["human_reviewed"] = True
                    c["human_review_date"] = datetime.now().isoformat()
                    updates_log.append(f"CONFIRMED: {concern} ({old_maturity}→CONFIRMED, conf {old_conf}→{c['confidence']})")
                    applied += 1
                elif kb_update == "REJECT":
                    c["knowledge_maturity"] = "REJECTED"
                    c["confidence"] = max(0.30, old_conf - 0.15)
                    c["human_reviewed"] = True
                    c["human_review_date"] = datetime.now().isoformat()
                    c["corrected_category"] = hd.get("corrected_category", "")
                    updates_log.append(f"REJECTED: {concern} ({old_maturity}→REJECTED)")
                    applied += 1
                elif kb_update == "MODIFY":
                    c["knowledge_maturity"] = "MODIFIED"
                    c["confidence"] = max(0.50, old_conf - 0.05)
                    c["human_reviewed"] = True
                    c["human_review_date"] = datetime.now().isoformat()
                    c["corrected_category"] = hd.get("corrected_category", "")
                    updates_log.append(f"MODIFIED: {concern} ({old_maturity}→MODIFIED, new category: {hd.get('corrected_category', '')})")
                    applied += 1
                break

    if applied > 0:
        kb["last_human_review_at"] = datetime.now().isoformat()
        kb["last_human_review_packet"] = packet.get("packet_id", "")
        kb["human_review_log"] = kb.get("human_review_log", []) + updates_log

        with open(kb_path, 'w', encoding='utf-8') as f:
            json.dump(kb, f, ensure_ascii=False, indent=2)

    return {
        "kb_path": kb_path,
        "updates_applied": applied,
        "updates_log": updates_log,
    }


# ============================================================
# MAIN: Generate 017 human gate packet
# ============================================================

def generate_017_packet(crosswalk_path: str, nb_obs_path: str, output_path: str) -> str:
    """Generate D3 human gate packet for PROJECT_017."""
    with open(crosswalk_path, 'r', encoding='utf-8') as f:
        cw = json.load(f)

    nb_data = None
    if os.path.exists(nb_obs_path):
        with open(nb_obs_path, 'r', encoding='utf-8') as f:
            nb_data = json.load(f)

    packet = generate_human_gate_packet("PROJECT_017", cw, nb_data)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(packet, f, ensure_ascii=False, indent=2)

    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 human_gate.py generate-017")
        print("  python3 human_gate.py apply <packet.json> <kb_path>")
        print("  python3 human_gate.py generate <crosswalk.json> <project_id> <output.json>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "generate-017":
        reports_dir = Path.home() / "CER-RAG/00_knowledge_extraction_build/round2_autonomous_loop/10_reports"
        cw_path = reports_dir / "017_crosswalk_matrix.json"
        nb_path = reports_dir / "017_nb_observations.json"
        out_path = reports_dir / "017_d3_human_gate_packet.json"

        result = generate_017_packet(str(cw_path), str(nb_path), str(out_path))
        with open(result) as f:
            packet = json.load(f)
        summary = packet.get("summary", {})
        print(f"D3 Human Gate Packet generated: {result}")
        print(f"  Project: {packet['project_id']}")
        print(f"  Total findings: {packet['total_findings']}")
        print(f"  STRONG: {summary.get('STRONG', 0)} | MODERATE: {summary.get('MODERATE', 0)}")
        print(f"  WEAK: {summary.get('WEAK', 0)} | NO_MATCH: {summary.get('NO_MATCH', 0)}")
        print(f"  CRITICAL: {summary.get('CRITICAL', 0)} | MAJOR: {summary.get('MAJOR', 0)}")
        print(f"  Human review status: {packet['human_review_status']}")

    elif command == "apply":
        packet_path = sys.argv[2]
        kb_path = sys.argv[3]
        with open(packet_path) as f:
            packet = json.load(f)
        result = apply_human_decisions(packet, kb_path)
        print(json.dumps(result, indent=2))

    elif command == "generate":
        cw_path = sys.argv[2]
        project_id = sys.argv[3]
        output = sys.argv[4] if len(sys.argv) > 4 else f"{project_id}_d3_human_gate_packet.json"
        with open(cw_path) as f:
            cw = json.load(f)
        packet = generate_human_gate_packet(project_id, cw)
        with open(output, 'w') as f:
            json.dump(packet, f, ensure_ascii=False, indent=2)
        print(f"Generated: {output} ({packet['total_findings']} findings)")
