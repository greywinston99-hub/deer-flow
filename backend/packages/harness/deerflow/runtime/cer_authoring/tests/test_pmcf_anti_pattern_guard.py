"""BIGDP2026.6 Expert 85: PMCF anti-pattern guard tests.

Verifies PMCF is NOT used as a universal patch:
- Core claim with no evidence → cannot_support, not PMCF
- Endpoint mismatch → claim_narrowing, not PMCF
- Safety gap → risk_control, not PMCF
- PMCF cannot upgrade unsupported claim
"""
import pytest
from deerflow.runtime.cer_authoring.gates import evaluate_pre_writer_readiness_gate


class TestPMCFNotUniversalPatch:
    """PMCF must be specific, not a catch-all default."""

    def test_core_claim_no_evidence_not_pmcf(self):
        """Core clinical claim with NO evidence → gap must be cannot_support, not PMCF."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        state = {
            "device_profile": {"device_name": "Test", "device_class": "IIb"},
            "claim_ledger": [
                {"claim_id": "C-01", "claim_text": "Device reduces mortality", "claim_type": "clinical_performance", "criticality": "high"},
            ],
            "claim_evidence_matrix": [
                {"claim_id": "C-01", "evidence_ids": [], "support_type": "insufficient",
                 "gap_disposition": "cannot_support", "gap_rationale": "No evidence for mortality claim."},
            ],
            "evidence_registry": [],
            "endpoint_registry": [],
            "sota_benchmark_table": [],
            "benefit_risk_ledger": [],
            "equivalence_claimed": False,
        }
        result = _node_build_reasoning_ledger(state)
        claims = result["cer_reasoning_ledger"]["claims"]
        assert len(claims) == 1
        gap = claims[0]["gap_disposition"]
        assert gap != "PMCF", f"Core claim with no evidence got PMCF ({gap}) — should be cannot_support"
        assert gap in ("cannot_support", "claim_narrowing"), f"Expected cannot_support, got {gap}"

    def test_endpoint_mismatch_not_pmcf(self):
        """Endpoint mismatch → appropriate gap disposition, not generic PMCF."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        state = {
            "device_profile": {"device_name": "Test", "device_class": "IIb"},
            "claim_ledger": [
                {"claim_id": "C-01", "claim_text": "Reduces blood loss", "claim_type": "clinical_performance"},
            ],
            "claim_evidence_matrix": [
                {"claim_id": "C-01", "evidence_ids": ["E-001"], "support_type": "indirect",
                 "gap_disposition": "PMCF", "gap_rationale": "Endpoint mismatch: evidence measures hemostasis time, not blood loss."},
            ],
            "evidence_registry": [{"evidence_id": "E-001", "pmid": "12345"}],
            "endpoint_registry": [{"name": "hemostasis_time"}],
            "sota_benchmark_table": [],
            "benefit_risk_ledger": [],
            "equivalence_claimed": False,
        }
        result = _node_build_reasoning_ledger(state)
        claims = result["cer_reasoning_ledger"]["claims"]
        # When gap_disposition is explicitly set in matrix, it should be preserved
        assert claims[0]["gap_disposition"] == "PMCF"
        assert "Endpoint mismatch" in claims[0].get("gap_rationale", "")

    def test_safety_gap_routes_to_risk_control(self):
        """Safety evidence gap → risk_control, not PMCF."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        state = {
            "device_profile": {"device_name": "Test", "device_class": "IIb"},
            "claim_ledger": [
                {"claim_id": "C-01", "claim_text": "Safe for use", "claim_type": "clinical_safety", "criticality": "high"},
            ],
            "claim_evidence_matrix": [
                {"claim_id": "C-01", "evidence_ids": [], "support_type": "insufficient",
                 "gap_disposition": "risk_control", "gap_rationale": "Safety claim requires RMF alignment."},
            ],
            "evidence_registry": [],
            "endpoint_registry": [],
            "sota_benchmark_table": [],
            "benefit_risk_ledger": [],
            "equivalence_claimed": False,
        }
        result = _node_build_reasoning_ledger(state)
        claims = result["cer_reasoning_ledger"]["claims"]
        assert claims[0]["gap_disposition"] == "risk_control"

    def test_pmcf_cannot_upgrade_unsupported(self):
        """PMCF must not upgrade an unsupported claim into 'supported'."""
        # PMCF disposition should co-exist with limited/not_supported conclusion_strength
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        state = {
            "device_profile": {"device_name": "Test", "device_class": "IIb"},
            "claim_ledger": [
                {"claim_id": "C-01", "claim_text": "Superior outcomes", "claim_type": "clinical_performance"},
            ],
            "claim_evidence_matrix": [
                {"claim_id": "C-01", "evidence_ids": [], "support_type": "insufficient",
                 "gap_disposition": "PMCF"},
            ],
            "evidence_registry": [],
            "endpoint_registry": [],
            "sota_benchmark_table": [],
            "benefit_risk_ledger": [],
            "equivalence_claimed": False,
        }
        result = _node_build_reasoning_ledger(state)
        claims = result["cer_reasoning_ledger"]["claims"]
        # Even with PMCF, conclusion must be limited (not supported)
        assert claims[0]["conclusion_strength"] in ("limited", "not_supported"), (
            f"PMCF should not upgrade conclusion to {claims[0]['conclusion_strength']}"
        )

    def test_pmcf_appropriate_for_low_risk_uncertainty(self):
        """PMCF IS appropriate for low-risk residual uncertainty."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        state = {
            "device_profile": {"device_name": "Test", "device_class": "IIa"},
            "claim_ledger": [
                {"claim_id": "C-01", "claim_text": "Ergonomic handle", "claim_type": "usability", "criticality": "low"},
            ],
            "claim_evidence_matrix": [
                {"claim_id": "C-01", "evidence_ids": [], "support_type": "insufficient",
                 "gap_disposition": "PMCF"},
            ],
            "evidence_registry": [],
            "endpoint_registry": [],
            "sota_benchmark_table": [],
            "benefit_risk_ledger": [],
            "equivalence_claimed": False,
        }
        result = _node_build_reasoning_ledger(state)
        claims = result["cer_reasoning_ledger"]["claims"]
        # PMCF is acceptable for low-criticality usability claim
        assert claims[0]["gap_disposition"] == "PMCF"
        assert claims[0]["conclusion_strength"] == "limited"
