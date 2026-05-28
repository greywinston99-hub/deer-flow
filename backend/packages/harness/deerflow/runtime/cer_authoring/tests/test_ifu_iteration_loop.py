"""WS2: IFU Iteration Loop Tests."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from deerflow.runtime.cer_authoring.ifu_iteration import build_ifu_iteration_ledger


class TestIFUIterationLoop:
    def test_empty_state_produces_ledger(self):
        result = build_ifu_iteration_ledger({})
        assert result["schema"] == "ifu_iteration_decision_ledger_v1"
        assert "ifu_iteration_decision_ledger" in result
        assert "ifu_claim_scope_delta_matrix" in result

    def test_overclaim_blocks_writer(self):
        feedback = [{"type": "overclaim", "description": "IFU claims unsupported efficacy", "severity": "critical", "status": "open"}]
        result = build_ifu_iteration_ledger({}, ifu_feedback=feedback)
        ledger = result["ifu_iteration_decision_ledger"]
        assert ledger["has_overclaim"] is True
        assert len(ledger["open_blockers"]) > 0

    def test_missing_clinical_benefit_does_not_block_writer(self):
        feedback = [{"type": "missing_clinical_benefit", "description": "IFU lacks clinical benefit statement", "status": "open"}]
        result = build_ifu_iteration_ledger({}, ifu_feedback=feedback)
        ledger = result["ifu_iteration_decision_ledger"]
        assert ledger["has_missing_clinical_benefit"] is True
        assert len(ledger["open_blockers"]) == 0

    def test_ifu_claim_scope_delta_generated(self):
        claims = [
            {"claim_id": "C1", "claim_text": "Safe for use", "claim_type": "ifu_warning_residual_risk", "final_body_allowed": True},
            {"claim_id": "C2", "claim_text": "Effective treatment", "claim_type": "clinical_benefit", "final_body_allowed": False},
        ]
        result = build_ifu_iteration_ledger({"claim_ledger": claims})
        delta = result["ifu_claim_scope_delta_matrix"]
        assert delta["total_claims_with_ifu_reference"] >= 0

    def test_all_closed_when_no_open_items(self):
        feedback = [{"type": "scope_aligned", "description": "Aligned", "status": "closed"}]
        result = build_ifu_iteration_ledger({}, ifu_feedback=feedback)
        assert result["ifu_iteration_decision_ledger"]["all_closed"] is True

    def test_version_conflict_blocks(self):
        feedback = [{"type": "version_conflict", "description": "IFU version mismatch", "severity": "major", "status": "open"}]
        result = build_ifu_iteration_ledger({}, ifu_feedback=feedback)
        assert result["ifu_iteration_decision_ledger"]["blocker_count"] >= 1
