"""Behavioral tests for G39 (final draft semantic QA) and related gates.

Verifies: G39 banned string → FAIL, G39 IFU placeholder → FAIL,
G39 clean → PASS, G_CLAIM_TEXT consistency, gate_decision routing.
"""
from deerflow.runtime.cer_authoring.gates import (
    _gate_final_draft_semantic_qa,
    _gate_claim_text_consistency,
    run_authoring_gates,
)


def test_g39_banned_string_fails():
    """G39 must FAIL when banned internal strings appear in rendered body."""
    result = _gate_final_draft_semantic_qa({
        "cer_chapter_drafts": {
            "1 Summary": "Claude generated this report using MCP tools. The DeerFlow system processed it."
        }
    })
    assert result.status == "FAIL", f"Expected FAIL, got {result.status}"
    assert "Claude" in result.message, f"Message should mention banned strings: {result.message}"


def test_g39_ifu_placeholder_fails():
    """G39 must FAIL when IFU placeholder text appears in rendered body."""
    result = _gate_final_draft_semantic_qa({
        "cer_chapter_drafts": {
            "2 Scope": "The device composition is: Not extracted from IFU source text."
        }
    })
    assert result.status == "FAIL", f"Expected FAIL, got {result.status}"
    assert "IFU placeholders" in result.message or "Not extracted" in result.message


def test_g39_clean_text_passes():
    """G39 must PASS when rendered body is clean."""
    result = _gate_final_draft_semantic_qa({
        "cer_chapter_drafts": {
            "1 Summary": "This clinical evaluation assesses the safety and performance of the device.",
            "5 Conclusions": "Based on the available evidence, the device meets GSPR requirements."
        },
        "writer_quality_report": {"writer_quality_pct": 100},
    })
    assert result.status == "PASS", f"Expected PASS, got {result.status}: {result.message}"


def test_g39_no_chapters_defers():
    """G39 must PASS (defer) when no CER chapters exist."""
    result = _gate_final_draft_semantic_qa({})
    assert result.status == "PASS"


def test_claim_text_not_allowed_fails():
    """G_CLAIM_TEXT must FAIL when blocked claim appears with support wording."""
    result = _gate_claim_text_consistency({
        "cer_chapter_drafts": {
            "5 Conclusions": "The evidence demonstrates that C-01 is effective."
        },
        "claim_evidence_matrix": [
            {"claim_id": "C-01", "support_status": "INSUFFICIENT"}
        ]
    })
    assert result.status == "FAIL", f"Expected FAIL, got {result.status}"


def test_claim_text_allowed_passes():
    """G_CLAIM_TEXT must PASS when claims are properly constrained."""
    result = _gate_claim_text_consistency({
        "cer_chapter_drafts": {
            "5 Conclusions": "Preliminary data suggest C-01 may be beneficial."
        },
        "claim_evidence_matrix": [
            {"claim_id": "C-01", "support_status": "STRONG"}
        ]
    })
    assert result.status == "PASS", f"Expected PASS, got {result.status}: {result.message}"


def test_br_unfavourable_blocks_favourable_text():
    """G_CLAIM_TEXT must FAIL when BR is unfavourable but body says favourable."""
    result = _gate_claim_text_consistency({
        "cer_chapter_drafts": {
            "5 Conclusions": "The benefit-risk profile is favourable."
        },
        "benefit_risk_ledger": [
            {"benefit_risk_balance": "unfavourable"}
        ]
    })
    assert result.status == "FAIL", f"Expected FAIL, got {result.status}"


def test_g39_routes_to_controlled_compromise_on_fail():
    """When G39 fails, run_authoring_gates must NOT return PASS_TO_DRAFT_DOCX."""
    report = run_authoring_gates({
        "cer_chapter_drafts": {
            "1 Summary": "Claude generated this. SKILL REFERENCE used."
        },
        "device_profile": {"device_name": "T", "device_type": "C", "device_class": "III"},
    })
    assert report["decision"] != "PASS_TO_DRAFT_DOCX", \
        f"G39 should block PASS_TO_DRAFT on banned strings, got {report['decision']}"


def test_g39_present_in_gate_results():
    """G39 must be in run_authoring_gates results."""
    report = run_authoring_gates({})
    g39_results = [r for r in report["results"] if r.get("gate_id") == "G39"]
    assert len(g39_results) == 1, f"G39 should be in gate results, found {len(g39_results)}"
