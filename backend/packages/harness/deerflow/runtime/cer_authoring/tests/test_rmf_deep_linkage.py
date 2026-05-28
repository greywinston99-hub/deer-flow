"""WS9: RMF Deep Linkage Tests."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from deerflow.runtime.cer_authoring.rmf_crosswalk import build_rmf_deep_linkage


class TestRMFDeepLinkage:
    def test_empty_state_produces_linkage(self):
        linkage = build_rmf_deep_linkage({})
        assert linkage["schema"] == "rmf_deep_linkage_v1"
        assert "rmf_hazard_trace" in linkage
        assert "ifu_warning_rmf_crosswalk" in linkage

    def test_missing_rmf_source_fails_gate(self):
        linkage = build_rmf_deep_linkage({})
        assert linkage["gate_status"] == "FAIL_MISSING_RMF_SOURCE"
        assert linkage["blocks_unqualified_br_conclusion"] is True

    def test_rmf_source_present_enables_linkage(self):
        state = {
            "source_inventory": [{"document_type": "risk_management_file", "filename": "RMF_v2.pdf"}],
        }
        linkage = build_rmf_deep_linkage(state)
        assert linkage["rmf_hazard_trace"]["has_rmf_source"] is True

    def test_ifu_warning_linked_to_hazard(self):
        state = {
            "source_inventory": [{"document_type": "risk_management_file", "filename": "RMF_v2.pdf"}],
        }
        risk_rows = [
            {"risk_id": "R1", "hazard_id": "HAZ-001", "harm": "air embolism during contrast injection",
             "risk_control_measure": "Automated air detection and removal system",
             "residual_risk_acceptability": "acceptable"},
        ]
        ifu_warnings = [
            {"claim_id": "W1", "claim_text": "Warning: Risk of air embolism if air detection system is bypassed",
             "claim_type": "ifu_warning_residual_risk"},
        ]
        linkage = build_rmf_deep_linkage(state, risk_rows, ifu_warnings)
        crosswalk = linkage["ifu_warning_rmf_crosswalk"]
        assert crosswalk["total_warnings"] >= 1

    def test_unlinked_warnings_detected(self):
        risk_rows = [
            {"risk_id": "R1", "hazard_id": "HAZ-001", "harm": "electrical shock"},
        ]
        ifu_warnings = [
            {"claim_id": "W1", "claim_text": "Warning: Do not use in MRI environment",
             "claim_type": "ifu_warning_residual_risk"},
        ]
        linkage = build_rmf_deep_linkage({}, risk_rows, ifu_warnings)
        assert linkage["gate_status"] in {"FAIL_UNLINKED_WARNINGS", "FAIL_MISSING_RMF_SOURCE"}

    def test_deep_hazard_fields_present(self):
        risk_rows = [
            {"risk_id": "R1", "sequence_of_events": "Step 1: injection, Step 2: bubble formation",
             "hazardous_situation": "Air enters bloodstream", "harm": "Air embolism",
             "initial_risk": "high", "risk_control_measure": "Air detection sensor",
             "residual_risk": "low", "residual_risk_acceptability": "acceptable"},
        ]
        linkage = build_rmf_deep_linkage({}, risk_rows)
        trace = linkage["rmf_hazard_trace"]["rows"][0]
        assert "sequence_of_events" in trace
        assert "hazardous_situation" in trace
        assert "harm" in trace
        assert "risk_control_measure" in trace
        assert "residual_risk_acceptability" in trace

    def test_linkage_complete_flag(self):
        state = {"source_inventory": [{"document_type": "rmf", "filename": "rmf.pdf"}]}
        risk_rows = [{"risk_id": "R1", "harm": "infection", "residual_risk_acceptability": "acceptable"}]
        ifu_warnings = [{"claim_id": "W1", "claim_text": "infection risk", "claim_type": "ifu_warning"}]
        linkage = build_rmf_deep_linkage(state, risk_rows, ifu_warnings)
        assert "linkage_complete" in linkage

    def test_blocks_unqualified_br_when_gate_fails(self):
        linkage = build_rmf_deep_linkage({})
        assert linkage["gate_status"] != "PASS"
        assert linkage["blocks_unqualified_br_conclusion"] is True
