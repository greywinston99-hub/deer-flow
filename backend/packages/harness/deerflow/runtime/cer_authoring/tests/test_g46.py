"""Unit tests for G46 pre-writer readiness gate (9-condition aggregation)."""
import pytest
from deerflow.runtime.cer_authoring.gates import evaluate_pre_writer_readiness_gate


class TestG46Conditions:
    def test_all_conditions_pass(self):
        result = evaluate_pre_writer_readiness_gate({})
        assert result["status"] == "PASS"

    def test_identity_fails_routes_to_device_profile(self):
        state = {
            "pre_writer_readiness_condition_overrides": {
                "identity": {"status": "REWORK_REQUIRED", "upstream_route": "device_profile"}
            }
        }
        result = evaluate_pre_writer_readiness_gate(state)
        assert result["status"] == "REWORK_REQUIRED"
        assert result.get("next_node") == "device_profile"

    def test_multiple_failures_pick_highest_priority(self):
        state = {
            "pre_writer_readiness_condition_overrides": {
                "BR": {"status": "REWORK_REQUIRED"},
                "identity": {"status": "REWORK_REQUIRED"},
            }
        }
        result = evaluate_pre_writer_readiness_gate(state)
        assert result["status"] == "REWORK_REQUIRED"
        assert result.get("next_node") == "device_profile"

    def test_blocked_routes_to_controlled_compromise(self):
        state = {
            "pre_writer_readiness_condition_overrides": {
                "identity": {"status": "BLOCKED"}
            }
        }
        result = evaluate_pre_writer_readiness_gate(state)
        assert result["status"] == "BLOCKED"
        assert result.get("next_node") == "controlled_compromise"

    def test_empty_state_has_expected_structure(self):
        result = evaluate_pre_writer_readiness_gate({})
        assert "status" in result
        assert "gate_id" in result
