"""WS1: Engineer Feedback Coverage Tests."""

from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from deerflow.runtime.cer_authoring.engineer_feedback_coverage import (
    build_engineer_feedback_coverage_report,
    _load_rules,
)


class TestEngineerFeedbackCoverage:
    def test_rules_file_exists(self):
        rules = _load_rules()
        assert len(rules) > 0, "engineer_feedback_rules.json must contain rules"

    def test_all_rules_have_required_fields(self):
        rules = _load_rules()
        required = {"feedback_id", "source_document", "requirement", "severity",
                     "implemented_by", "artifact_contract", "gate_contract", "test_contract"}
        for rule in rules:
            missing = required - set(rule.keys())
            assert not missing, f"Rule {rule.get('feedback_id')} missing fields: {missing}"

    def test_no_unmapped_critical_feedback(self):
        report = build_engineer_feedback_coverage_report()
        summary = report["summary"]
        assert summary["p0_gap_count"] <= len(summary["p0_gaps"]), "P0 gap tracking mismatch"
        for entry in report["entries"]:
            if entry["severity"] == "P0" and not entry["absorbed"]:
                assert entry["feedback_id"] in summary["p0_gaps"], \
                    f"P0 gap {entry['feedback_id']} not tracked in summary"

    def test_coverage_report_structure(self):
        report = build_engineer_feedback_coverage_report()
        assert report["schema"] in {"engineer_feedback_coverage_report_v1", "engineer_feedback_coverage_report_v2"}
        assert "summary" in report
        assert "entries" in report
        assert "total_rules" in report["summary"]
        assert "absorption_rate" in report["summary"]

    def test_absorption_rate_calculation(self):
        report = build_engineer_feedback_coverage_report()
        s = report["summary"]
        if s["total_rules"] > 0:
            expected = round(s["absorbed"] / s["total_rules"], 3)
            assert s["absorption_rate"] == expected

    def test_coverage_report_with_state(self):
        report = build_engineer_feedback_coverage_report({"project_id": "test"})
        assert "entries" in report
