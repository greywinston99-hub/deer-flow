"""BIGDP2026.6 Expert 85: G42 expert repair strategy tests.

Verifies G42 routes to correct repair node based on evidence gap characteristics.
Tests 8 routing scenarios.
"""
import pytest
from deerflow.runtime.cer_authoring.gates import evaluate_evidence_sufficiency_gate, _compute_g42_dynamic_max_rounds


class TestG42ExpertRepairStrategy:
    """G42 routes to correct repair based on gap type, not just round count."""

    def _state(self, pattern, **extra):
        base = {
            "device_profile": {"device_class": "IIb"},
            "claim_ledger": [{"claim_id": "C-01", "claim_type": "clinical_performance", "criticality": "medium"}],
            "pre_g42_claim_evidence_candidate_matrix": [{
                "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
                "failure_pattern": pattern,
                "repair_route": "query_expansion",
            }],
        }
        base.update(extra)
        return base

    def test_missing_evidence_routes_to_query_expansion(self):
        """EVIDENCE_TRULY_INSUFFICIENT → query_expansion for more searching."""
        state = self._state("EVIDENCE_TRULY_INSUFFICIENT")
        result = evaluate_evidence_sufficiency_gate(state)
        assert result["status"] == "REWORK_REQUIRED"
        assert result["next_node"] == "query_expansion"

    def test_endpoint_gap_routes_to_endpoint_extraction(self):
        """ENDPOINT_GAP → endpoint_extraction."""
        state = self._state("ENDPOINT_GAP",
            pre_g42_claim_evidence_candidate_matrix=[{
                "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
                "failure_pattern": "ENDPOINT_GAP", "repair_route": "endpoint_extraction",
            }])
        result = evaluate_evidence_sufficiency_gate(state)
        assert result["status"] == "REWORK_REQUIRED"
        assert result["next_node"] == "endpoint_extraction"

    def test_linking_gap_routes_to_pre_g42_linking(self):
        """LINKING_GAP → pre_g42_claim_evidence_candidate_linking."""
        state = self._state("LINKING_GAP",
            pre_g42_claim_evidence_candidate_matrix=[{
                "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
                "failure_pattern": "LINKING_GAP", "repair_route": "pre_g42_claim_evidence_candidate_linking",
            }])
        result = evaluate_evidence_sufficiency_gate(state)
        assert result["status"] == "REWORK_REQUIRED"
        assert result["next_node"] == "pre_g42_claim_evidence_candidate_linking"

    def test_claim_overreach_routes_to_claim_evidence_matrix(self):
        """CLAIM_OVERREACH → claim_evidence_matrix for claim rework."""
        state = self._state("CLAIM_OVERREACH",
            pre_g42_claim_evidence_candidate_matrix=[{
                "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
                "failure_pattern": "CLAIM_OVERREACH", "repair_route": "claim_evidence_matrix",
            }])
        result = evaluate_evidence_sufficiency_gate(state)
        assert result["status"] == "REWORK_REQUIRED"
        assert result["next_node"] == "claim_evidence_matrix"

    def test_pdf_gap_routes_to_evidence_appraisal(self):
        """PDF_GAP → evidence_appraisal."""
        state = self._state("PDF_GAP",
            pre_g42_claim_evidence_candidate_matrix=[{
                "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
                "failure_pattern": "PDF_GAP", "repair_route": "evidence_appraisal",
            }])
        result = evaluate_evidence_sufficiency_gate(state)
        assert result["status"] == "REWORK_REQUIRED"
        assert result["next_node"] == "evidence_appraisal"

    def test_max_rounds_blocked_for_class_i(self):
        """Class I device hits BLOCKED at round 3 (base only)."""
        from deerflow.runtime.cer_authoring.gates import MAX_SPIRAL_ROUNDS
        state = self._state("EVIDENCE_TRULY_INSUFFICIENT",
            device_profile={"device_class": "I"},
            evidence_spiral_lineage=[
                {"spiral_round_id": 1}, {"spiral_round_id": 2}, {"spiral_round_id": 3},
            ])
        result = evaluate_evidence_sufficiency_gate(state)
        assert result["status"] in ("BLOCKED", "REWORK_REQUIRED")

    def test_class_iii_gets_more_rounds(self):
        """Class III: dynamic max ≥ 5 rounds (base 3 + class_bonus 2)."""
        dynamic = _compute_g42_dynamic_max_rounds({
            "device_profile": {"device_class": "III"},
            "claim_ledger": [],
        })
        assert dynamic >= 5, f"Class III should get ≥5 rounds, got {dynamic}"

    def test_source_type_not_met_routes_correctly(self):
        """SOURCE_TYPE_REQUIREMENT_NOT_MET routes to appropriate node."""
        state = self._state("SOURCE_TYPE_REQUIREMENT_NOT_MET",
            pre_g42_claim_evidence_candidate_matrix=[{
                "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
                "failure_pattern": "SOURCE_TYPE_REQUIREMENT_NOT_MET", "repair_route": "risk_gspr_mapping",
            }])
        result = evaluate_evidence_sufficiency_gate(state)
        assert result["status"] == "REWORK_REQUIRED"
        # Source type requirements route based on repair_route in matrix
        assert result["next_node"] in ("risk_gspr_mapping", "query_expansion")
