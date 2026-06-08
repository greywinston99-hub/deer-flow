"""BIGDP2026.6: Gap disposition logic semantic tests.

Verifies insufficient evidence triggers appropriate gap dispositions.
Tests rules: GAP-01 through GAP-05.
"""
import pytest


class TestGapDispositionLogic:
    """GAP rules: Evidence gaps must be dispositioned correctly."""

    def _build_state(self, claims, evidence_matrix, **extra):
        state = {
            "claim_ledger": claims,
            "claim_evidence_matrix": evidence_matrix,
            "evidence_registry": [],
            "endpoint_registry": [],
            "sota_benchmark_table": [],
            "benefit_risk_ledger": [],
            "device_profile": {"device_name": "Test Device", "device_class": "IIb"},
            "equivalence_claimed": False,
        }
        state.update(extra)
        return state

    def test_no_evidence_triggers_gap(self):
        """GAP-01: Insufficient evidence MUST trigger gap disposition."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        claims = [{"claim_id": "C-01", "claim_text": "Amazing results", "claim_type": "clinical_performance"}]
        state = self._build_state(claims, [])
        result = _node_build_reasoning_ledger(state)
        claim = result["cer_reasoning_ledger"]["claims"][0]
        assert claim["gap_disposition"] != "no_gap", (
            f"No evidence should trigger gap, got '{claim['gap_disposition']}'"
        )

    def test_evidence_gap_is_not_no_gap(self):
        """When evidence is insufficient, gap_disposition is NOT 'no_gap'."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        claims = [{"claim_id": "C-01", "claim_text": "Safe device", "claim_type": "clinical_safety"}]
        evidence_matrix = [{"claim_id": "C-01", "evidence_ids": []}]
        state = self._build_state(claims, evidence_matrix)
        result = _node_build_reasoning_ledger(state)
        claim = result["cer_reasoning_ledger"]["claims"][0]
        assert claim["gap_disposition"] != "no_gap", (
            f"Without evidence, gap should not be 'no_gap'. Got: {claim['gap_disposition']}"
        )

    def test_evidence_present_no_gap(self):
        """When evidence is sufficient, gap_disposition is 'no_gap'."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        claims = [{"claim_id": "C-01", "claim_text": "Achieves hemostasis", "claim_type": "clinical_performance"}]
        evidence_matrix = [{"claim_id": "C-01", "evidence_ids": ["E-001", "E-002"]}]
        state = self._build_state(claims, evidence_matrix)
        result = _node_build_reasoning_ledger(state)
        claim = result["cer_reasoning_ledger"]["claims"][0]
        assert claim["gap_disposition"] == "no_gap", (
            f"With evidence, expected 'no_gap', got '{claim['gap_disposition']}'"
        )

    def test_valid_gap_disposition_values(self):
        """All gap dispositions must be from the valid set."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger
        valid = {"no_gap", "PMCF", "labeling", "risk_control", "claim_narrowing", "cannot_support"}

        # Test with evidence
        claims = [{"claim_id": "C-01", "claim_text": "Test claim", "claim_type": "clinical_performance"}]
        evidence_matrix = [{"claim_id": "C-01", "evidence_ids": []}]
        state = self._build_state(claims, evidence_matrix)
        result = _node_build_reasoning_ledger(state)
        for claim in result["cer_reasoning_ledger"]["claims"]:
            assert claim["gap_disposition"] in valid, (
                f"Invalid gap disposition: '{claim['gap_disposition']}'. Valid: {valid}"
            )
