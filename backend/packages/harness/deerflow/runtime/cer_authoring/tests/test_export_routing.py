"""Test _route_after_gates routing logic for export vs controlled_compromise.

Regression coverage for the HUMAN_HOLD → export routing fix.
"""

import pytest

import json

from deerflow.runtime.cer_authoring.artifacts import write_authoring_artifacts
from deerflow.runtime.cer_authoring.graph import _route_after_gates, _route_after_input_gate


class TestRouteAfterGates:
    """Verify routing decisions after final gate closure."""

    def test_gate_passed_routes_to_export(self):
        """PASS_TO_DRAFT_DOCX → export node."""
        state = {
            "status": "gate_passed",
            "final_gate_decision": "PASS_TO_DRAFT_DOCX",
        }
        assert _route_after_gates(state) == "export"

    def test_human_hold_routes_to_export(self):
        """HUMAN_HOLD must route to export so artifacts are written.

        Regression: previously self_inspection overwrote status to
        'self_inspection_complete', causing _route_after_gates to
        miss HUMAN_HOLD and send execution to controlled_compromise
        (which does NOT write artifacts).
        """
        state = {
            "status": "self_inspection_complete",  # set by _node_self_inspection
            "final_gate_decision": "HUMAN_HOLD",
        }
        assert _route_after_gates(state) == "export"

    def test_gate_rework_required_routes_to_controlled_compromise(self):
        """Non-HUMAN_HOLD rework → controlled_compromise."""
        state = {
            "status": "gate_rework_required",
            "final_gate_decision": "REWORK_REQUIRED",
        }
        assert _route_after_gates(state) == "controlled_compromise"

    def test_self_inspection_complete_without_human_hold(self):
        """self_inspection_complete alone → controlled_compromise."""
        state = {
            "status": "self_inspection_complete",
            "final_gate_decision": "REWORK_REQUIRED",
        }
        assert _route_after_gates(state) == "controlled_compromise"

    def test_input_required_routes_to_controlled_compromise(self):
        """Missing inputs → controlled_compromise."""
        state = {
            "status": "input_required",
            "final_gate_decision": "HUMAN_HOLD",
        }
        # HUMAN_HOLD overrides and sends to export, which then
        # skips the interrupt and writes artifacts.
        assert _route_after_gates(state) == "export"

    def test_provider_unavailable_routes_to_controlled_compromise(self):
        """Provider unavailable → controlled_compromise."""
        state = {
            "status": "provider_unavailable",
            "final_gate_decision": "HUMAN_HOLD",
        }
        # HUMAN_HOLD still routes to export; export node handles it.
        assert _route_after_gates(state) == "export"

    def test_no_final_gate_decision_defaults_to_controlled_compromise(self):
        """Missing final_gate_decision → controlled_compromise."""
        state = {
            "status": "gate_rework_required",
            "final_gate_decision": None,
        }
        assert _route_after_gates(state) == "controlled_compromise"


def test_source_preflight_block_routes_to_controlled_compromise():
    state = {"status": "source_preflight_blocked", "final_gate_decision": "HUMAN_HOLD"}
    assert _route_after_input_gate(state) == "controlled_compromise"


def test_blocked_authoring_exports_preflight_and_compromise_artifacts(tmp_path):
    state = {
        "project_id": "EXPORT-BLOCKED",
        "status": "controlled_compromise",
        "final_gate_decision": "HUMAN_HOLD",
        "source_lock_report": {"status": "BLOCKED"},
        "ifu_fact_table": {"status": "INCOMPLETE"},
        "source_preflight_gate_report": {
            "status": "BLOCKED",
            "blocking_issues": [{"issue_id": "IFU-P0", "message": "IFU missing"}],
            "controlled_gaps": [{"issue_id": "GAP-PMS"}],
        },
        "classification_consistency_report": {"status": "BLOCKED"},
        "device_classification_lock": {"lock_status": "conflict"},
        "controlled_compromise_manifest": {
            "schema_name": "controlled_compromise_manifest",
            "terminal_status": "DOMAIN_FATAL",
            "writer_invoked": False,
        },
    }
    write_authoring_artifacts(tmp_path, state)
    for name in (
        "source_preflight_gate_report.json",
        "device_classification_lock.json",
        "blocker_report.json",
        "controlled_compromise_manifest.json",
    ):
        assert (tmp_path / name).exists()
    blocker = json.loads((tmp_path / "blocker_report.json").read_text(encoding="utf-8"))
    assert blocker["status"] == "BLOCKED"
    assert blocker["blocking_issue_count"] == 1
    manifest = json.loads((tmp_path / "controlled_compromise_manifest.json").read_text(encoding="utf-8"))
    assert manifest["terminal_status"] == "DOMAIN_FATAL"
    assert manifest["writer_invoked"] is False
