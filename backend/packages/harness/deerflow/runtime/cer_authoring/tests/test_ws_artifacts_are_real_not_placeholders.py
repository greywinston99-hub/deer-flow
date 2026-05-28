"""Test that WS artifacts are real, not placeholders."""

from pathlib import Path
import json
import sys
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class TestWSArtifactsAreReal:
    def _minimal_state(self):
        return {
            "project_id": "test_ws",
            "source_inventory": [],
            "claim_ledger": [
                {"claim_id": "C1", "claim_text": "Device reduces mortality", "claim_type": "clinical_benefit"},
            ],
            "prisma_flow_data": {"raw_hits": 10},
            "evidence_registry": [
                {"evidence_id": "E1", "source_type": "subject_device_clinical_study", "study_design": "rct", "direct_evidence": True},
            ],
        }

    def test_engineer_feedback_coverage_is_not_placeholder(self):
        from deerflow.runtime.cer_authoring.engineer_feedback_coverage import build_engineer_feedback_coverage_report
        report = build_engineer_feedback_coverage_report()
        assert report["schema"].startswith("engineer_feedback_coverage")
        assert report["summary"]["total_rules"] > 0
        assert len(report["entries"]) > 0

    def test_ifu_iteration_ledger_is_not_placeholder(self):
        from deerflow.runtime.cer_authoring.ifu_iteration import build_ifu_iteration_ledger
        ledger = build_ifu_iteration_ledger({"claim_ledger": []})
        assert ledger["schema"] == "ifu_iteration_decision_ledger_v1"
        assert "ifu_iteration_decision_ledger" in ledger

    def test_claim_taxonomy_is_not_placeholder(self):
        from deerflow.runtime.cer_authoring.claim_taxonomy import build_claim_taxonomy_decision_table
        claims = [{"claim_id": "C1", "claim_text": "Reduces mortality", "claim_type": "clinical_benefit"}]
        taxonomy = build_claim_taxonomy_decision_table(claims)
        assert len(taxonomy["claim_taxonomy_decision_table"]) > 0
        assert taxonomy["claim_taxonomy_decision_table"][0]["classified_claim_class"] != ""

    def test_prisma_audit_is_not_placeholder(self):
        from deerflow.runtime.cer_authoring.prisma_reproducibility import build_prisma_reproducibility_audit
        audit = build_prisma_reproducibility_audit({"raw_hits": 10})
        assert audit["schema"] == "prisma_reproducibility_audit_v1"
        assert "flow_counts" in audit

    def test_evidence_level_matrix_is_not_placeholder(self):
        from deerflow.runtime.cer_authoring.evidence_level_matrix import build_evidence_level_summary_matrix
        evidence = [{"evidence_id": "E1", "source_type": "subject_device_clinical_study", "study_design": "rct"}]
        matrix = build_evidence_level_summary_matrix(evidence, [])
        assert matrix["schema"] == "evidence_level_summary_matrix_v1"
        assert matrix["summary"]["total_evidence_sources"] > 0

    def test_endpoint_homogeneity_matrix_is_not_placeholder(self):
        from deerflow.runtime.cer_authoring.endpoint_homogeneity import build_endpoint_homogeneity_matrix
        endpoints = [{"endpoint_family": "test", "unit": "%"}]
        matrix = build_endpoint_homogeneity_matrix(endpoints)
        assert matrix["schema"] == "endpoint_homogeneity_matrix_v1"

    def test_equivalence_route_lock_is_not_placeholder(self):
        from deerflow.runtime.cer_authoring.equivalence_route_lock import build_equivalence_route_lock
        lock = build_equivalence_route_lock({})
        assert lock["schema"] == "equivalence_route_lock_v1"
        assert lock["decision"] in {
            "equivalence_not_claimed", "full_equivalence_claimed",
            "similar_device_background_only", "customer_risk_accepted_data_gap",
        }

    def test_benefit_risk_closure_is_not_placeholder(self):
        from deerflow.runtime.cer_authoring.benefit_risk_section import build_benefit_risk_body_section
        br = build_benefit_risk_body_section({}, "")
        assert br["schema"] == "benefit_risk_closure_matrix_v1"
        assert "conclusion_allowed" in br

    def test_rmf_linkage_is_not_placeholder(self):
        from deerflow.runtime.cer_authoring.rmf_crosswalk import build_rmf_deep_linkage
        linkage = build_rmf_deep_linkage({})
        assert linkage["schema"] == "rmf_deep_linkage_v1"
        assert "rmf_hazard_trace" in linkage

    def test_regulatory_style_is_not_placeholder(self):
        from deerflow.runtime.cer_authoring.regulatory_style import build_regulatory_style_fingerprint
        fp = build_regulatory_style_fingerprint("The device is safe and effective.")
        assert fp["schema"] == "regulatory_style_fingerprint_v1"
        assert fp["metrics"]["total_words"] > 0

    def test_xlsx_artifacts_have_rows(self):
        """Verify XLSX artifacts from builders have real data rows."""
        from deerflow.runtime.cer_authoring.claim_taxonomy import build_claim_taxonomy_decision_table
        claims = [{"claim_id": "C1", "claim_text": "Reduces mortality", "claim_type": "clinical_benefit"}]
        taxonomy = build_claim_taxonomy_decision_table(claims)
        rows = taxonomy["claim_taxonomy_decision_table"]
        assert len(rows) > 0
        assert isinstance(rows[0], dict)
        assert "claim_id" in rows[0]

    def test_artifacts_in_output_files(self):
        """WS artifacts must be listed in OUTPUT_FILES."""
        from deerflow.runtime.cer_authoring.artifacts import OUTPUT_FILES

        required = [
            "engineer_feedback_coverage_report.json",
            "ifu_iteration_decision_ledger.json",
            "ifu_claim_scope_delta_matrix.xlsx",
            "claim_taxonomy_decision_table.xlsx",
            "claim_evidence_route_matrix.xlsx",
            "prisma_reproducibility_audit.json",
            "evidence_level_summary_matrix.xlsx",
            "endpoint_homogeneity_matrix.xlsx",
            "equivalence_route_lock.json",
            "regulatory_style_fingerprint_report.json",
        ]

        for art in required:
            assert art in OUTPUT_FILES, f"{art} not in OUTPUT_FILES"

    def test_final_gate_report_includes_ws_gate_results(self):
        """Final gate report must reflect WS gate results."""
        from deerflow.runtime.cer_authoring.artifacts import write_authoring_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            state = self._minimal_state()
            try:
                written = write_authoring_artifacts(tmpdir, state)
                # Check that FINAL_DRAFT_QA_REPORT.json exists
                draft_qa = Path(tmpdir) / "FINAL_DRAFT_QA_REPORT.json"
                assert draft_qa.exists(), f"FINAL_DRAFT_QA_REPORT.json not written. Written: {written[:10]}"
                data = json.loads(draft_qa.read_text())
                assert "ws_gates" in data, f"No ws_gates key in {list(data.keys())}"
                ws_gates = data["ws_gates"]
                assert "ws1_coverage" in ws_gates or "ws7_equivalence" in ws_gates
            except ImportError:
                pytest.skip("python-docx not available")
