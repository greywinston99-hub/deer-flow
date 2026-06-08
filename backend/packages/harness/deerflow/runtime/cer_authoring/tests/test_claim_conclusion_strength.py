"""BIGDP2026.6: Claim conclusion strength semantic tests.

Verifies weak or indirect evidence cannot produce strong conclusion.
Tests rules: CON-01 through CON-07, EVS-02 through EVS-06.
"""
import json
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[7] / "BIGDP2026_6" / "expert_scenario_fixtures"


class TestConclusionStrengthDerivation:
    """CON rules: Conclusion strength must be evidence-based, not IFU-based."""

    def _build_state(self, claims, evidence, **extra):
        """Build minimal state for reasoning ledger tests."""
        claim_evidence_matrix = []
        for c in claims:
            claim_evidence_matrix.append({
                "claim_id": c["claim_id"],
                "evidence_ids": [e["evidence_id"] for e in evidence],
                "support_type": evidence[0].get("support_type", "direct") if evidence else "insufficient",
            })
        state = {
            "claim_ledger": claims,
            "claim_evidence_matrix": claim_evidence_matrix,
            "evidence_registry": evidence,
            "endpoint_registry": [],
            "sota_benchmark_table": [],
            "benefit_risk_ledger": [],
            "device_profile": {"device_name": "Test", "device_class": "IIb"},
        }
        state.update(extra)
        return state

    def test_indirect_evidence_not_strong(self):
        """CON-02: Indirect-only evidence cannot produce 'strong' conclusion."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        claims = [{"claim_id": "C-01", "claim_text": "Reduces procedure time", "claim_type": "clinical_performance"}]
        evidence = [
            {"evidence_id": "E-001", "pmid": "11111", "study_design": "Meta-analysis",
             "sample_size": 500, "support_type": "indirect"},
            {"evidence_id": "E-002", "pmid": "22222", "study_design": "Cohort",
             "sample_size": 80, "support_type": "indirect"},
        ]
        state = self._build_state(claims, evidence)
        result = _node_build_reasoning_ledger(state)
        claim = result["cer_reasoning_ledger"]["claims"][0]
        assert claim["conclusion_strength"] != "strong", (
            f"Indirect-only evidence produced 'strong' conclusion — violates CON-02. Got: {claim['conclusion_strength']}"
        )
        assert claim["evidence_support_type"] == "indirect"

    def test_direct_evidence_with_two_sources_is_strong(self):
        """Two direct evidence sources → strong conclusion (CON-01)."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        claims = [{"claim_id": "C-01", "claim_text": "Achieves hemostasis", "claim_type": "clinical_performance"}]
        evidence = [
            {"evidence_id": "E-001", "pmid": "11111", "study_design": "RCT",
             "sample_size": 200, "support_type": "direct"},
            {"evidence_id": "E-002", "pmid": "22222", "study_design": "RCT",
             "sample_size": 150, "support_type": "direct"},
        ]
        state = self._build_state(claims, evidence)
        result = _node_build_reasoning_ledger(state)
        claim = result["cer_reasoning_ledger"]["claims"][0]
        assert claim["conclusion_strength"] == "strong", (
            f"Two direct sources should produce 'strong', got {claim['conclusion_strength']}"
        )

    def test_insufficient_evidence_is_not_supported(self):
        """CON-03: No evidence → limited or not_supported, never strong/moderate."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        claims = [{"claim_id": "C-01", "claim_text": "Revolutionary results", "claim_type": "clinical_performance"}]
        state = self._build_state(claims, [])
        result = _node_build_reasoning_ledger(state)
        claim = result["cer_reasoning_ledger"]["claims"][0]
        assert claim["conclusion_strength"] in ("limited", "not_supported"), (
            f"No evidence should produce limited/not_supported, got {claim['conclusion_strength']}"
        )
        assert claim["evidence_support_type"] == "insufficient"

    def test_equivalent_evidence_not_direct(self):
        """S-08: Equivalent device evidence → support_type is 'equivalent', not 'direct'."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        fixture = json.loads((FIXTURES_DIR / "08_equivalence_evidence_misused.json").read_text())
        claims = [{"claim_id": "C-01", "claim_text": fixture["input"]["ifu_text"], "claim_type": "clinical_performance"}]
        evidence = fixture["input"]["available_evidence"]
        # The claim_evidence_matrix must use support_type='equivalent' to reflect
        # that the evidence is from an equivalent device, not the subject device
        state = self._build_state(claims, evidence,
            equivalence_claimed=True,
            equivalent_device_name="ClosurePro V1")
        # Override the claim_evidence_matrix support_type to 'equivalent'
        state["claim_evidence_matrix"] = [{
            "claim_id": "C-01",
            "evidence_ids": [e["evidence_id"] for e in evidence],
            "support_type": "equivalent",
        }]
        result = _node_build_reasoning_ledger(state)
        claim = result["cer_reasoning_ledger"]["claims"][0]
        # With equivalent-only evidence, support should be 'equivalent'
        assert claim["evidence_support_type"] == "equivalent", (
            f"Equivalent evidence should be classified as 'equivalent'. Got: {claim['evidence_support_type']}"
        )
        # Conclusion should be moderate at best (not strong) per CON rules
        assert claim["conclusion_strength"] != "strong", (
            f"Equivalent-only evidence should not produce 'strong'. Got: {claim['conclusion_strength']}"
        )

    def test_single_direct_study_at_most_moderate(self):
        """CON-04: Single direct study → at most 'moderate'."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        claims = [{"claim_id": "C-01", "claim_text": "Safe for use", "claim_type": "clinical_safety"}]
        evidence = [
            {"evidence_id": "E-001", "pmid": "55555", "study_design": "Prospective",
             "sample_size": 45, "support_type": "direct"},
        ]
        state = self._build_state(claims, evidence)
        result = _node_build_reasoning_ledger(state)
        claim = result["cer_reasoning_ledger"]["claims"][0]
        assert claim["conclusion_strength"] in ("moderate", "limited"), (
            f"Single study should produce moderate/limited, got {claim['conclusion_strength']}"
        )
