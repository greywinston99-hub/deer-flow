"""Targeted W1 tests for CER Writer Remediation Gates.

Gate 1 — Device Identity Body Consistency
Gate 3 — Evidence-to-Conclusion Consistency
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from deerflow.runtime.cer_authoring.writer_remediation.writer_gates import (
    evaluate_device_domain_consistency_gate,
    evaluate_evidence_conclusion_gate,
    evaluate_ifu_consumption_gate,
    evaluate_body_cleanliness_gate,
    evaluate_remediated_qa_gate,
    run_all_writer_gates,
)
from deerflow.runtime.cer_authoring.writer_remediation.quarantine import (
    route_to_quarantine,
)

# ── Contaminated draft paths ─────────────────────────────────────────────────

PILOT_01_ROOT = Path("/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_01启灏/02_AI_BASELINE_OUTPUT_FREEZE")
PILOT_02_ROOT = Path("/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/02_AI_BASELINE_OUTPUT_FREEZE")
PILOT_03_ROOT = Path("/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_03 永新-软件/02_AI_BASELINE_OUTPUT_FREEZE")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_draft(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


# ── Gate 1: Device Domain Consistency ───────────────────────────────────────


class TestGate1DomainConsistency:
    """Gate 1 — forbidden term detection in non-exception contexts."""

    def test_f1_cardiac_stabilizer_contains_ureteroscope_hard_fail(self):
        """F1: Cardiac stabilizer report with ureteroscope/UAS → HARD FAIL."""
        cer_text = _load_draft(PILOT_02_ROOT / "CER_draft.md")
        device_profile = _load_json(PILOT_02_ROOT / "device_profile.json")

        result = evaluate_device_domain_consistency_gate(cer_text, device_profile)

        assert result["status"] == "HARD_FAIL", (
            f"Expected HARD_FAIL for cardiac stabilizer with forbidden urology terms. "
            f"Got {result['status']}: {result.get('message', '')}"
        )
        assert len(result["findings"]) > 0, "Should have at least one forbidden term finding"
        # Verify the finding is for a urology-related forbidden term
        forbidden_found = {f["term"] for f in result["findings"]}
        assert forbidden_found & {"ureteroscope", "UAS", "ureteral access sheath", "urinary tract", "stone burden", "endourology", "guidewire"}, (
            f"Expected urology forbidden terms but found: {forbidden_found}"
        )
        assert result["quarantine"] is True

    def test_f2_plasma_electrode_contains_ureteroscopy_hard_fail(self):
        """F2: Plasma electrode report with ureteroscopy/UAS → HARD FAIL."""
        cer_text = _load_draft(PILOT_01_ROOT / "CER_draft.md")
        device_profile = _load_json(PILOT_01_ROOT / "device_profile.json")

        result = evaluate_device_domain_consistency_gate(cer_text, device_profile)

        assert result["status"] == "HARD_FAIL", (
            f"Expected HARD_FAIL for plasma electrode with forbidden urology terms. "
            f"Got {result['status']}: {result.get('message', '')}"
        )
        assert len(result["findings"]) > 0
        forbidden_found = {f["term"] for f in result["findings"]}
        assert forbidden_found & {"ureteroscope", "UAS", "ureteral access sheath", "urinary tract", "stone burden", "endourology", "guidewire"}, (
            f"Expected urology forbidden terms but found: {forbidden_found}"
        )
        assert result["quarantine"] is True

    def test_f4_forbidden_term_in_exclusion_context_flag_not_hard_fail(self):
        """F4: Forbidden term in explicit exclusion context → flag/warning, NOT HARD FAIL."""
        cer_text = (
            "# Summary\n\n"
            "The device is intended for cardiac tissue stabilization during CABG.\n\n"
            "# 3 Clinical Background\n\n"
            "This device is not applicable to ureteroscopic procedures and "
            "differs from ureteral access sheath technology. "
            "Unlike urological endoscopy, this approach targets the cardiac surface.\n\n"
            "# 5 Conclusions\n\n"
            "Cardiac stabilizer is safe and effective for its intended use.\n"
        )
        device_profile = {
            "device_name": "Cardiac Tissue Stabilizer",
            "device_domain": "cardiac_tissue_stabilizer",
        }

        result = evaluate_device_domain_consistency_gate(cer_text, device_profile)

        assert result["status"] == "PASS", (
            f"Forbidden terms in exclusion context should NOT trigger HARD FAIL. "
            f"Got {result['status']}: {result.get('message', '')}. "
            f"Findings: {result.get('findings', [])}"
        )

    def test_f5_clean_minimal_fixture_pass(self):
        """F5: Clean cardiac stabilizer report → PASS."""
        cer_text = (
            "# Summary\n\n"
            "This CER evaluates the Cardiac Tissue Stabilizer for its intended use "
            "in coronary artery bypass grafting (CABG) on the beating heart. "
            "The device provides mechanical stabilization of the target vessel "
            "during off-pump anastomosis procedures.\n\n"
            "# 2.1 Device Description\n\n"
            "The cardiac tissue stabilizer is a mechanical device used during "
            "cardiac surgery to stabilize the heart surface. It uses suction "
            "stabilization to immobilize the target vessel during CABG.\n\n"
            "# 3 Clinical Background\n\n"
            "Coronary artery disease (CAD) affects millions of patients worldwide. "
            "Off-pump CABG avoids cardiopulmonary bypass (CPB) and its associated risks.\n\n"
            "# 4 Device Under Evaluation\n\n"
            "The heart stabilizer enables safe anastomosis on beating heart tissue. "
            "Clinical data from published studies demonstrate acceptable outcomes.\n\n"
            "# 5 Conclusions\n\n"
            "The cardiac tissue stabilizer is safe and effective for its intended purpose. "
            "Current evidence supports its clinical use in CABG procedures.\n"
        )
        device_profile = {
            "device_name": "Cardiac Tissue Stabilizer",
            "device_domain": "cardiac_tissue_stabilizer",
        }

        result = evaluate_device_domain_consistency_gate(cer_text, device_profile)

        assert result["status"] == "PASS", (
            f"Clean cardiac stabilizer report should PASS. "
            f"Got {result['status']}: {result.get('message', '')}. "
            f"Findings: {result.get('findings', [])}"
        )
        assert result["quarantine"] is False

    def test_f6_imaging_software_with_physical_device_terms_hard_fail(self):
        """Imaging software + physical device template terms → HARD FAIL."""
        cer_text = (
            "# Summary\n\n"
            "This medical imaging software provides DICOM image processing.\n\n"
            "# 2.1 Device Description\n\n"
            "The device consists of a catheter assembly with sterile packaging. "
            "The implant requires biocompatibility testing. "
            "Sterile shelf life is 2 years. Surgical access is required.\n\n"
            "# 5 Conclusions\n\n"
            "The software is effective for image analysis.\n"
        )
        device_profile = {
            "device_name": "Medical Imaging Software",
            "device_domain": "medical_imaging_software",
        }

        result = evaluate_device_domain_consistency_gate(cer_text, device_profile)

        assert result["status"] == "HARD_FAIL", (
            f"Imaging software with physical device terms should HARD_FAIL. "
            f"Got {result['status']}"
        )
        assert result["quarantine"] is True


# ── Gate 3: Evidence-to-Conclusion Consistency ──────────────────────────────


class TestGate3EvidenceConclusion:
    """Gate 3 — evidence-conclusion phrase consistency."""

    def test_insufficient_claim_with_support_language_hard_fail(self):
        """INSUFFICIENT claim + 'clinical data support' in Summary → HARD FAIL."""
        cer_text = (
            "# Summary\n\n"
            "The clinical data support the safety and performance of the device. "
            "The evidence demonstrates acceptable outcomes for the intended use.\n\n"
            "# 5 Conclusions\n\n"
            "The device is consistent with the state of the art and clinical "
            "data partially support its benefit-risk profile.\n"
        )
        claim_support_matrix = {
            "C-01": {
                "claim_id": "C-01",
                "support_level": "INSUFFICIENT",
                "max_conclusion_strength": "INSUFFICIENT",
            },
            "C-02": {
                "claim_id": "C-02",
                "support_level": "INSUFFICIENT",
                "max_conclusion_strength": "INSUFFICIENT",
            },
        }

        result = evaluate_evidence_conclusion_gate(cer_text, claim_support_matrix)

        assert result["status"] == "HARD_FAIL", (
            f"INSUFFICIENT claim with 'clinical data support' should HARD_FAIL. "
            f"Got {result['status']}: {result.get('message', '')}"
        )
        assert len(result["findings"]) > 0, "Should have forbidden phrase findings"
        assert result["quarantine"] is True

    def test_insufficient_claim_with_does_not_support_pass(self):
        """INSUFFICIENT claim + 'does not support' → PASS (negation)."""
        cer_text = (
            "# Summary\n\n"
            "The current evidence does not support a conclusion of safety. "
            "Available clinical data does not demonstrate acceptable performance. "
            "The evidence does not confirm the benefit-risk acceptability.\n\n"
            "# 5 Conclusions\n\n"
            "No conclusion can be drawn at this stage. Further clinical evidence is required.\n"
        )
        claim_support_matrix = {
            "C-01": {
                "claim_id": "C-01",
                "support_level": "INSUFFICIENT",
                "max_conclusion_strength": "INSUFFICIENT",
            },
        }

        result = evaluate_evidence_conclusion_gate(cer_text, claim_support_matrix)

        assert result["status"] == "PASS", (
            f"Negated forbidden phrases should PASS Gate 3. "
            f"Got {result['status']}: {result.get('message', '')}. "
            f"Hard fail findings: {result.get('findings', [])}"
        )

    def test_retrieval_incomplete_with_favourable_wording_hard_fail(self):
        """retrieval_incomplete + favourable benefit-risk wording → HARD FAIL."""
        cer_text = (
            "# Summary\n\n"
            "The clinical data support the intended use. The evidence demonstrates "
            "favourable clinical outcomes and adequate safety performance.\n\n"
            "# 5 Conclusions\n\n"
            "Based on the evidence, the device has an acceptable benefit-risk profile.\n"
        )
        claim_support_matrix = {
            "C-01": {
                "claim_id": "C-01",
                "support_level": "retrieval_incomplete",
                "max_conclusion_strength": "INSUFFICIENT",
            },
        }

        result = evaluate_evidence_conclusion_gate(cer_text, claim_support_matrix)

        assert result["status"] == "HARD_FAIL", (
            f"retrieval_incomplete with favourable wording should HARD_FAIL. "
            f"Got {result['status']}: {result.get('message', '')}"
        )
        assert result["quarantine"] is True

    def test_allowed_use_blocked_treated_as_insufficient(self):
        """ALLOWED_USE_BLOCKED claim → treated as INSUFFICIENT for Gate 3."""
        cer_text = (
            "# Summary\n\n"
            "The clinical data support the safety claim. Evidence demonstrates "
            "acceptable performance for the intended purpose.\n\n"
            "# 5 Conclusions\n\n"
            "The device has a favourable benefit-risk profile.\n"
        )
        claim_support_matrix = {
            "C-01": {
                "claim_id": "C-01",
                "support_level": "ALLOWED_USE_BLOCKED",
            },
        }

        result = evaluate_evidence_conclusion_gate(cer_text, claim_support_matrix)

        assert result["status"] == "HARD_FAIL", (
            f"ALLOWED_USE_BLOCKED claim with supportive wording should HARD_FAIL. "
            f"Got {result['status']}"
        )
        assert result["quarantine"] is True

    def test_clean_conclusion_with_inadequate_evidence_pass(self):
        """Clean conclusion: INSUFFICIENT evidence, honest wording → PASS."""
        cer_text = (
            "# Summary\n\n"
            "The current evidence is insufficient to conclude safety or performance. "
            "No conclusion can be drawn at this stage. Further clinical evidence "
            "is required to establish the benefit-risk profile.\n\n"
            "# 5 Conclusions\n\n"
            "The claim is held pending additional data. Available evidence does not "
            "support a favourable conclusion.\n"
        )
        claim_support_matrix = {
            "C-01": {
                "claim_id": "C-01",
                "support_level": "INSUFFICIENT",
                "max_conclusion_strength": "INSUFFICIENT",
            },
        }

        result = evaluate_evidence_conclusion_gate(cer_text, claim_support_matrix)

        assert result["status"] == "PASS", (
            f"Honest INSUFFICIENT conclusion should PASS. "
            f"Got {result['status']}: {result.get('message', '')}. "
            f"Hard fail: {result.get('findings', [])}"
        )

    def test_contaminated_midaosi_report_evidence_conclusion_hard_fail(self):
        """Real contaminated 米道斯 report → Gate 3 HARD FAIL (all claims INSUFFICIENT but body says 'partially support')."""
        cer_text = _load_draft(PILOT_02_ROOT / "CER_draft.md")
        claim_support_matrix = _load_json(PILOT_02_ROOT / "claim_support_matrix.json")

        result = evaluate_evidence_conclusion_gate(cer_text, claim_support_matrix)

        assert result["status"] == "HARD_FAIL", (
            f"Contaminated 米道斯 report should HARD FAIL on Gate 3. "
            f"Got {result['status']}: {result.get('message', '')}"
        )
        assert len(result["findings"]) > 0
        assert result["quarantine"] is True


# ── Quarantine Routing ───────────────────────────────────────────────────────


class TestQuarantineRouting:
    """Quarantine routing for gate-failed reports."""

    def test_gate_fail_routes_to_quarantine_not_release(self, tmp_path):
        """Gate HARD FAIL → report goes to quarantine, not release output."""
        cer_text = (
            "# Summary\n\n"
            "The ureteroscope is used during cardiac surgery.\n"
            "# 5 Conclusions\n\n"
            "The device is effective.\n"
        )
        device_profile = {
            "device_name": "Test Cardiac Stabilizer",
            "device_domain": "cardiac_tissue_stabilizer",
        }

        gate_results = run_all_writer_gates(cer_text, device_profile)

        assert gate_results["quarantine"] is True
        assert gate_results["overall_status"] == "HARD_FAIL"

        # Run quarantine routing
        q_result = route_to_quarantine(
            tmp_path, cer_text, gate_results, report_id="test-001"
        )

        # Verify quarantine files exist
        quarantine_dir = tmp_path / "quarantine"
        assert quarantine_dir.exists(), "Quarantine directory should exist"
        assert (quarantine_dir / "CER_draft_QUARANTINED.md").exists()
        assert len(list(quarantine_dir.glob("failed_gate_report_*.json"))) > 0
        assert (quarantine_dir / "rejection_ledger.json").exists()

        # Verify rejection ledger content
        ledger = json.loads((quarantine_dir / "rejection_ledger.json").read_text())
        assert ledger["total_rejections"] >= 1
        assert any("gate_1_domain_consistency" in str(e.get("failed_gates", [])) for e in ledger["entries"])

    def test_clean_report_not_quarantined(self, tmp_path):
        """Clean report → no quarantine, all gates PASS."""
        cer_text = (
            "# Summary\n\n"
            "This CER evaluates the Cardiac Tissue Stabilizer for CABG procedures. "
            "Current evidence is insufficient to conclude on all claims. "
            "Further clinical evidence is required.\n\n"
            "# 2.1 Device Description\n\n"
            "The cardiac tissue stabilizer uses mechanical stabilization during "
            "off-pump coronary artery bypass surgery.\n\n"
            "# 3 Clinical Background\n\n"
            "Coronary artery disease is treated via CABG or PCI. "
            "Off-pump CABG (OPCAB) avoids cardiopulmonary bypass complications.\n\n"
            "# 5 Conclusions\n\n"
            "No conclusion can be drawn at this stage. Claims are held pending "
            "additional clinical data.\n"
        )
        device_profile = {
            "device_name": "Cardiac Tissue Stabilizer",
            "device_domain": "cardiac_tissue_stabilizer",
        }
        claim_support_matrix = {
            "C-01": {"support_level": "INSUFFICIENT"},
        }

        gate_results = run_all_writer_gates(cer_text, device_profile, claim_support_matrix)

        assert gate_results["quarantine"] is False, (
            f"Clean report should not be quarantined. "
            f"Gate results: {gate_results.get('gates', {})}"
        )
        assert gate_results["overall_status"] == "PASS"


# ── Gate 2: IFU Fact Consumption ────────────────────────────────────────────


class TestGate2IFUConsumption:
    """Gate 2 — IFU placeholder detection."""

    def test_ifu_exists_but_placeholder_found_hard_fail(self):
        """IFU source exists but body has 'Not extracted from IFU' → HARD FAIL."""
        cer_text = (
            "# 2.1 Device Description\n\n"
            "Composition: Not extracted from IFU source text; refer to subject device IFU for details.\n"
            "Working principle: Not extracted from IFU source text.\n"
            "Sterility: The device is provided sterile.\n"
        )
        device_profile = {
            "device_name": "Test Device",
            "profile_source_ids": ["SRC-IFU-001", "SRC-IFU-002"],
        }

        result = evaluate_ifu_consumption_gate(cer_text, device_profile)

        assert result["status"] == "HARD_FAIL", (
            f"IFU placeholders with available IFU source should HARD_FAIL. "
            f"Got {result['status']}: {result.get('message', '')}"
        )
        assert result["has_ifu_source"] is True
        assert result["placeholder_count"] > 0

    def test_no_ifu_source_placeholders_allowed(self):
        """No IFU source → IFU placeholders are acceptable (no HARD FAIL)."""
        cer_text = (
            "# 2.1 Device Description\n\n"
            "Composition: Not extracted from IFU source text.\n"
        )
        device_profile = {
            "device_name": "Test Device",
            "profile_source_ids": [],
        }

        result = evaluate_ifu_consumption_gate(cer_text, device_profile)

        assert result["status"] == "PASS", (
            f"No IFU source → placeholders should be accepted. "
            f"Got {result['status']}"
        )

    def test_no_placeholders_clean_pass(self):
        """No IFU placeholders → clean PASS."""
        cer_text = (
            "# 2.1 Device Description\n\n"
            "Composition: The device consists of titanium alloy components.\n"
            "Working principle: Radiofrequency energy is delivered via the electrode.\n"
        )
        device_profile = {
            "device_name": "Test Device",
            "profile_source_ids": ["SRC-IFU-001"],
        }

        result = evaluate_ifu_consumption_gate(cer_text, device_profile)

        assert result["status"] == "PASS"


# ── Gate 4: Submission Body Cleanliness ─────────────────────────────────────


class TestGate4BodyCleanliness:
    """Gate 4 — internal language leakage detection."""

    def test_internal_language_in_body_hard_fail(self):
        """CER body contains Claude/DeerFlow/MCP → HARD FAIL."""
        cer_text = (
            "# Summary\n\n"
            "Claude/DeerFlow must generate the customer request. "
            "The MCP evidence searches provide benchmark data. "
            "Generated by cer_authoring_v1, this draft uses AP/human CER writing paradigm.\n"
            "# 5 Conclusions\n\n"
            "The device is not_allowed for this claim type. "
            "The ALLOWED_USE_BLOCKED status prevents authoring. "
            "Score: 100 benchmark decision: PASS.\n"
        )
        # No Annex in this text, so Gate 4 scans everything

        result = evaluate_body_cleanliness_gate(cer_text)

        assert result["status"] == "HARD_FAIL", (
            f"Internal system language should HARD FAIL Gate 4. "
            f"Got {result['status']}: {result.get('message', '')}"
        )
        # Should catch multiple banned strings
        assert result["finding_count"] >= 5, (
            f"Expected at least 5 banned string findings, got {result['finding_count']}"
        )
        assert result["quarantine"] is True

    def test_clean_body_with_annex_mcp_in_heading_pass(self):
        """Body text is clean; 'MCP' appears only in Annex heading → PASS."""
        cer_text = (
            "# Summary\n\n"
            "The device is safe and effective for its intended use.\n\n"
            "# 5 Conclusions\n\n"
            "Current evidence supports clinical use.\n\n"
            "# Annex J MCP Execution and Human Template Benchmark\n\n"
            "This annex documents MCP tool usage and benchmark results.\n"
        )

        result = evaluate_body_cleanliness_gate(cer_text)

        assert result["status"] == "PASS", (
            f"'MCP' in Annex heading should not trigger Gate 4. "
            f"Got {result['status']}: {result.get('message', '')}. "
            f"Findings: {result.get('findings', [])}"
        )

    def test_clean_body_no_internal_language_pass(self):
        """Clean body text with no banned strings → PASS."""
        cer_text = (
            "# Summary\n\n"
            "This CER evaluates the cardiac tissue stabilizer for CABG procedures. "
            "The clinical evidence is reviewed under MDR Article 61 and MEDDEV 2.7/1 Rev. 4.\n\n"
            "# 5 Conclusions\n\n"
            "The benefit-risk profile is acceptable based on available data.\n"
        )

        result = evaluate_body_cleanliness_gate(cer_text)

        assert result["status"] == "PASS", (
            f"Clean body text should PASS Gate 4. "
            f"Got {result['status']}: {result.get('message', '')}. "
            f"Findings: {result.get('findings', [])}"
        )


# ── W3: QA Gate Hardening (Gate 5) ──────────────────────────────────────────


class TestGate5RemediatedQA:
    """Gate 5 — Remediated QA gate replacing Annex J."""

    def test_contaminated_cardiac_stabilizer_qa_fail(self):
        """Contaminated cardiac stabilizer report → QA FAIL."""
        cer_text = _load_draft(PILOT_02_ROOT / "CER_draft.md")
        device_profile = _load_json(PILOT_02_ROOT / "device_profile.json")
        claim_support_matrix = _load_json(PILOT_02_ROOT / "claim_support_matrix.json")

        result = evaluate_remediated_qa_gate(cer_text, device_profile, claim_support_matrix)

        assert result["status"] == "FAIL", (
            f"Contaminated report must QA FAIL. Got {result['status']} (score {result['score']}). "
            f"Failing: {result.get('failing_dimensions', [])}"
        )
        assert result["score"] < 100, "Score must be < 100 for contaminated report"
        assert len(result["failing_dimensions"]) > 0, "Must have failing dimensions"
        assert len(result["findings"]) > 0, "Must have per-item findings"
        assert result["quarantine"] is True

    def test_contaminated_plasma_electrode_qa_fail(self):
        """Contaminated plasma electrode report → QA FAIL."""
        cer_text = _load_draft(PILOT_01_ROOT / "CER_draft.md")
        device_profile = _load_json(PILOT_01_ROOT / "device_profile.json")
        claim_support_matrix = _load_json(PILOT_01_ROOT / "claim_support_matrix.json")

        result = evaluate_remediated_qa_gate(cer_text, device_profile, claim_support_matrix)

        assert result["status"] == "FAIL", (
            f"Contaminated plasma electrode report must QA FAIL. "
            f"Got {result['status']} (score {result['score']}). "
            f"Failing: {result.get('failing_dimensions', [])}"
        )
        assert result["score"] < 100

    def test_internal_language_leakage_qa_fail(self):
        """Internal language leakage → QA FAIL."""
        cer_text = (
            "# Summary\n\n"
            "Claude/DeerFlow must generate customer request. "
            "The device is effective for cardiac surgery.\n\n"
            "# 5 Conclusions\n\n"
            "Generated by cer_authoring_v1. Score: 100 benchmark decision.\n"
        )
        device_profile = {
            "device_name": "Test Device",
            "device_domain": "cardiac_tissue_stabilizer",
        }

        result = evaluate_remediated_qa_gate(cer_text, device_profile)

        assert result["status"] == "FAIL", (
            f"Internal language leakage must QA FAIL. Got {result['status']} (score {result['score']})"
        )
        assert "body_cleanliness" in result["failing_dimensions"]

    def test_evidence_insufficient_but_supportive_conclusion_qa_fail(self):
        """INSUFFICIENT evidence + supportive conclusion → QA FAIL."""
        cer_text = (
            "# Summary\n\n"
            "The clinical data support the safety and performance of the device. "
            "Evidence demonstrates acceptable outcomes.\n\n"
            "# 5 Conclusions\n\n"
            "The device is consistent with state of the art.\n"
        )
        claim_support_matrix = {
            "C-01": {"support_level": "INSUFFICIENT"},
        }

        result = evaluate_remediated_qa_gate(cer_text, None, claim_support_matrix)

        assert result["status"] == "FAIL", (
            f"Evidence-conclusion mismatch must QA FAIL. Got {result['status']} (score {result['score']})"
        )
        assert "evidence_conclusion_consistency" in result["failing_dimensions"]

    def test_clean_minimal_report_qa_pass(self):
        """Clean minimal report → QA PASS."""
        cer_text = (
            "# Summary\n\n"
            "This CER evaluates the Cardiac Tissue Stabilizer for CABG. "
            "Current evidence is insufficient to conclude on all claims.\n\n"
            "# 2.1 Device Description\n\n"
            "The device consists of mechanical stabilizer components.\n\n"
            "# 3 Clinical Background\n\n"
            "Coronary artery bypass grafting is a standard treatment for CAD.\n\n"
            "# 5 Conclusions\n\n"
            "No conclusion can be drawn at this stage. Claims held pending data.\n"
        )
        device_profile = {
            "device_name": "Cardiac Tissue Stabilizer",
            "device_domain": "cardiac_tissue_stabilizer",
        }
        claim_support_matrix = {
            "C-01": {"support_level": "INSUFFICIENT"},
        }

        result = evaluate_remediated_qa_gate(cer_text, device_profile, claim_support_matrix)

        assert result["status"] == "PASS", (
            f"Clean report must QA PASS. Got {result['status']} (score {result['score']}). "
            f"Dimensions: {result.get('dimensions', {})}"
        )
        assert result["score"] >= 70, f"Clean report should score >= 70, got {result['score']}"
        # If ambiguous term warnings lowered score, verify it's not FAIL
        assert result["score"] > 0

    def test_qa_no_longer_outputs_unsupported_pass(self):
        """QA gate no longer gives PASS/100/findings empty on contaminated reports."""
        # Using a clearly contaminated text
        cer_text = (
            "# Summary\n\n"
            "The ureteroscope is used during cardiac surgery. "
            "Stone burden is assessed via urological endoscopy.\n\n"
            "# 5 Conclusions\n\n"
            "The clinical data support the intended use. Evidence is favourable.\n"
        )
        device_profile = {
            "device_name": "Cardiac Tissue Stabilizer",
            "device_domain": "cardiac_tissue_stabilizer",
        }
        claim_support_matrix = {
            "C-01": {"support_level": "INSUFFICIENT"},
        }

        result = evaluate_remediated_qa_gate(cer_text, device_profile, claim_support_matrix)

        # Must NOT be PASS with 100
        assert not (result["status"] == "PASS" and result["score"] == 100), (
            "QA must not give PASS/100 on clearly contaminated report"
        )
        assert result["score"] < 100
        assert len(result["findings"]) > 0, "findings must not be empty"
