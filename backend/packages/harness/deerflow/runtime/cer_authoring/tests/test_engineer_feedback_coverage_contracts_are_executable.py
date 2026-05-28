"""Test that engineer feedback coverage contracts are executable, not just declared."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class TestEngineerFeedbackCoverageContracts:
    def test_coverage_report_v2_produced(self):
        """Coverage report must use v2 schema with contract verification."""
        from deerflow.runtime.cer_authoring.engineer_feedback_coverage import build_engineer_feedback_coverage_report
        report = build_engineer_feedback_coverage_report()
        assert report["schema"] == "engineer_feedback_coverage_report_v2"
        assert "verified_absorption_rate" in report["summary"]

    def test_contracts_verified_field_present(self):
        """Each entry must have contracts_verified dict."""
        from deerflow.runtime.cer_authoring.engineer_feedback_coverage import build_engineer_feedback_coverage_report
        report = build_engineer_feedback_coverage_report()
        for entry in report["entries"]:
            assert "contracts_verified" in entry, f"Missing contracts_verified for {entry['feedback_id']}"
            cv = entry["contracts_verified"]
            for key in ("code", "artifact", "gate", "test", "total_verified"):
                assert key in cv, f"Missing {key} in contracts_verified for {entry['feedback_id']}"

    def test_code_contract_verification(self):
        """Code contracts should be verified as importable."""
        from deerflow.runtime.cer_authoring.engineer_feedback_coverage import _verify_code_contract
        assert _verify_code_contract("pipeline._build_claim_evidence_matrix")
        assert _verify_code_contract("gates.evaluate_pre_writer_readiness_gate")
        assert not _verify_code_contract("")
        assert not _verify_code_contract("nonexistent.module.function")

    def test_artifact_contract_verification(self):
        """Artifact contracts should match OUTPUT_FILES."""
        from deerflow.runtime.cer_authoring.engineer_feedback_coverage import _verify_artifact_contract
        from deerflow.runtime.cer_authoring.artifacts import OUTPUT_FILES
        art_set = set(OUTPUT_FILES)
        assert _verify_artifact_contract("engineer_feedback_coverage_report.json", art_set)
        assert not _verify_artifact_contract("nonexistent_artifact.xyz", art_set)
        assert not _verify_artifact_contract("", art_set)

    def test_gate_contract_verification(self):
        """Gate contracts should detect WS gate patterns in gates.py."""
        from deerflow.runtime.cer_authoring.engineer_feedback_coverage import _verify_gate_contract
        gate_source = (Path(__file__).resolve().parent.parent / "gates.py").read_text()
        assert _verify_gate_contract("gates._gate_ws7_equivalence_route", gate_source)
        assert _verify_gate_contract("gates._gate_ws10_submission_cleanliness", gate_source)
        # Empty contract should return False
        assert not _verify_gate_contract("", "")

    def test_test_contract_verification(self):
        """Test contracts should verify test files exist."""
        from deerflow.runtime.cer_authoring.engineer_feedback_coverage import _verify_test_contract
        assert _verify_test_contract("test_engineer_feedback_coverage.py")
        assert _verify_test_contract("test_equivalence_route_lock.py::test_no_similar_device_not_claimed")
        assert not _verify_test_contract("nonexistent_test_file.py")
        assert not _verify_test_contract("")

    def test_absorption_rate_reflects_contract_verification(self):
        """Absorption rate must be computed from verified contracts, not declared status."""
        from deerflow.runtime.cer_authoring.engineer_feedback_coverage import build_engineer_feedback_coverage_report
        report = build_engineer_feedback_coverage_report()
        # verified_absorption_rate should be >= 0
        assert report["summary"]["verified_absorption_rate"] >= 0.0
        # At least some rules should have gate verification (since WS gates are wired)
        gate_verified = sum(1 for e in report["entries"] if e["contracts_verified"]["gate"])
        assert gate_verified > 0, "No rules have gate contract verification"

    def test_no_p0_gaps(self):
        """After WS integration, there should be zero P0 gaps."""
        from deerflow.runtime.cer_authoring.engineer_feedback_coverage import build_engineer_feedback_coverage_report
        report = build_engineer_feedback_coverage_report()
        assert report["summary"]["p0_gap_count"] == 0, f"P0 gaps remain: {report['summary']['p0_gaps']}"
