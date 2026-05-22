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


class TestG46AllNineConditions:
    """B: G46 9-condition full combination — each condition tested individually."""

    CONDITIONS = [
        "identity", "evidence_sufficiency", "retrieval_domain",
        "screening_pool", "fulltext_basis", "SOTA",
        "claim_evidence", "BR", "alignment",
    ]
    REWORK_ROUTES = {
        "identity": "device_profile",
        "retrieval_domain": "sota_search",
        "screening_pool": "sota_search",
        "fulltext_basis": "evidence_appraisal",
        "evidence_sufficiency": "sota_search",
        "SOTA": "endpoint_extraction",
        "claim_evidence": "writer_synthesis",
        "BR": "writer_synthesis",
        "alignment": "risk_gspr_mapping",
    }

    @pytest.mark.parametrize("condition", CONDITIONS)
    def test_single_condition_rework(self, condition):
        """Each condition alone → REWORK_REQUIRED with correct route."""
        state = {
            "pre_writer_readiness_condition_overrides": {
                condition: {"status": "REWORK_REQUIRED"}
            }
        }
        result = evaluate_pre_writer_readiness_gate(state)
        assert result["status"] == "REWORK_REQUIRED"
        route = result.get("next_node", "")
        expected = self.REWORK_ROUTES.get(condition, "")
        assert route == expected, f"{condition}: expected route '{expected}', got '{route}'"

    @pytest.mark.parametrize("condition", CONDITIONS)
    def test_single_condition_blocked(self, condition):
        """Each condition alone BLOCKED → BLOCKED with controlled_compromise route."""
        state = {
            "pre_writer_readiness_condition_overrides": {
                condition: {"status": "BLOCKED"}
            }
        }
        result = evaluate_pre_writer_readiness_gate(state)
        assert result["status"] == "BLOCKED"
        assert result.get("next_node") == "controlled_compromise"

    def test_priority_order_applied(self):
        """When multiple conditions fail, highest priority (identity) wins."""
        state = {
            "pre_writer_readiness_condition_overrides": {
                "alignment": {"status": "REWORK_REQUIRED"},
                "BR": {"status": "REWORK_REQUIRED"},
                "identity": {"status": "REWORK_REQUIRED"},
            }
        }
        result = evaluate_pre_writer_readiness_gate(state)
        assert result["status"] == "REWORK_REQUIRED"
        assert result.get("next_node") == "device_profile"  # identity is highest

    def test_mixed_rework_and_blocked(self):
        """REWORK + BLOCKED → BLOCKED takes precedence."""
        state = {
            "pre_writer_readiness_condition_overrides": {
                "BR": {"status": "REWORK_REQUIRED"},
                "alignment": {"status": "BLOCKED"},
            }
        }
        result = evaluate_pre_writer_readiness_gate(state)
        assert result["status"] == "BLOCKED"

    def test_all_nine_pass(self):
        """All 9 conditions PASS → PASS."""
        state = {
            "pre_writer_readiness_condition_overrides": {
                c: {"status": "PASS"} for c in self.CONDITIONS
            }
        }
        result = evaluate_pre_writer_readiness_gate(state)
        assert result["status"] == "PASS"
