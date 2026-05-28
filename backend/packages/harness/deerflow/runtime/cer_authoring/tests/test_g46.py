"""Unit tests for G46 pre-writer readiness gate (9-condition aggregation + WS gates)."""
import pytest
from deerflow.runtime.cer_authoring.gates import evaluate_pre_writer_readiness_gate

# Minimal valid state that satisfies all WS sub-gates so G46 tests can
# focus on the 9 placeholder conditions without triggering real gate logic.
def _ws_pass_state():
    return {
        "prisma_flow_data": {
            "flow": {"raw_hits": 42, "dedup_input": 40, "duplicate_count": 2,
                     "after_dedup": 38, "title_abstract_screened": 38,
                     "title_abstract_excluded": 20, "fulltext_assessed": 18,
                     "fulltext_excluded": 8, "final_included": 10},
        },
        "source_inventory": [
            {"document_type": "RMF", "source_role": "rmf_risk_management",
             "filename": "risk_management_report.pdf"},
        ],
        "claim_ledger": [],
        "clinical_evaluation_plan": {
            "device_name": "Test Device",
            "device_class": "IIb",
            "scope": "Test scope",
            "literature_search_protocol": {
                "databases": ["PubMed"],
                "inclusion_criteria": ["RCT"],
                "exclusion_criteria": ["case reports"],
            },
            "appraisal_method": "MDCG 2020-6",
            "sota_methodology": "LSP",
            "claim_support_method": "evidence-to-claim matrix",
            "benefit_risk_method": "MDCG 2020-6 §4.7",
            "pms_pmcf_update_plan": "Annual PMCF",
        },
    }


# Conditions whose BLOCKED is intentionally downgraded to REWORK_REQUIRED
# in evaluate_pre_writer_readiness_gate (placeholder-only conditions that
# lack dedicated evaluation logic — gates.py L254-256).
_PLACEHOLDER_DOWNGRADE_CONDITIONS = {"claim_evidence", "retrieval_completeness"}


class TestG46Conditions:
    def test_all_conditions_pass(self):
        result = evaluate_pre_writer_readiness_gate(_ws_pass_state())
        assert result["status"] == "PASS"

    def test_identity_fails_routes_to_device_profile(self):
        state = {
            **_ws_pass_state(),
            "pre_writer_readiness_condition_overrides": {
                "identity": {"status": "REWORK_REQUIRED", "upstream_route": "device_profile"}
            }
        }
        result = evaluate_pre_writer_readiness_gate(state)
        assert result["status"] == "REWORK_REQUIRED"
        assert result.get("next_node") == "device_profile"

    def test_multiple_failures_pick_highest_priority(self):
        state = {
            **_ws_pass_state(),
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
            **_ws_pass_state(),
            "pre_writer_readiness_condition_overrides": {
                "identity": {"status": "BLOCKED"}
            }
        }
        result = evaluate_pre_writer_readiness_gate(state)
        assert result["status"] == "BLOCKED"
        assert result.get("next_node") == "controlled_compromise"

    def test_empty_state_yields_structure_not_pass(self):
        """Empty state may return non-PASS because real WS gates require real data."""
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
            **_ws_pass_state(),
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
        """Each condition alone BLOCKED → BLOCKED (or REWORK_REQUIRED for placeholders)."""
        state = {
            **_ws_pass_state(),
            "pre_writer_readiness_condition_overrides": {
                condition: {"status": "BLOCKED"}
            }
        }
        result = evaluate_pre_writer_readiness_gate(state)
        if condition in _PLACEHOLDER_DOWNGRADE_CONDITIONS:
            assert result["status"] == "REWORK_REQUIRED", \
                f"{condition}: placeholder condition downgrades BLOCKED to REWORK_REQUIRED"
        else:
            assert result["status"] == "BLOCKED"
            assert result.get("next_node") == "controlled_compromise"

    def test_priority_order_applied(self):
        """When multiple conditions fail, highest priority (identity) wins."""
        state = {
            **_ws_pass_state(),
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
            **_ws_pass_state(),
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
            **_ws_pass_state(),
            "pre_writer_readiness_condition_overrides": {
                c: {"status": "PASS"} for c in self.CONDITIONS
            }
        }
        result = evaluate_pre_writer_readiness_gate(state)
        assert result["status"] == "PASS"
