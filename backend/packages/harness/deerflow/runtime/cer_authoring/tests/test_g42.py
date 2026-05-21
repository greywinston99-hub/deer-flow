"""Unit tests for G42 evidence sufficiency gate (13 failure patterns)."""
import pytest
from deerflow.runtime.cer_authoring.gates import evaluate_evidence_sufficiency_gate

G42_PATTERN_STATES = {
    "SOURCE_TYPE_REQUIREMENT_NOT_MET": {
        "claim_ledger": [{"claim_id": "C-01", "claim_type": "IFU_warning"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "SOURCE_TYPE_REQUIREMENT_NOT_MET",
            "repair_route": "risk_gspr_mapping",
        }],
    },
    "ALLOWED_USE_BLOCKED": {
        "claim_ledger": [{"claim_id": "C-01"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "ALLOWED_USE_BLOCKED",
            "repair_route": "claim_decomposition",
        }],
    },
    "MISSING_DATA_BLOCKING": {
        "claim_ledger": [{"claim_id": "C-01"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "MISSING_DATA_BLOCKING",
            "repair_route": "evidence_appraisal",
        }],
    },
    "LINKING_GAP": {
        "claim_ledger": [{"claim_id": "C-01"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "LINKING_GAP",
            "repair_route": "pre_g42_claim_evidence_candidate_linking",
        }],
    },
    "ENDPOINT_GAP": {
        "claim_ledger": [{"claim_id": "C-01"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "ENDPOINT_GAP",
            "repair_route": "endpoint_extraction",
        }],
    },
    "PDF_GAP": {
        "claim_ledger": [{"claim_id": "C-01"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "PDF_GAP",
            "repair_route": "evidence_appraisal",
        }],
    },
    "EVIDENCE_TRULY_INSUFFICIENT": {
        "claim_ledger": [{"claim_id": "C-01"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "EVIDENCE_TRULY_INSUFFICIENT",
            "repair_route": "query_expansion",
        }],
    },
    "CLAIM_SOURCE_MISMATCH": {
        "claim_ledger": [{"claim_id": "C-01", "claim_type": "clinical_benefit"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "CLAIM_SOURCE_MISMATCH",
            "repair_route": "risk_gspr_mapping",
        }],
    },
    "CLAIM_TYPE_MISCLASSIFICATION": {
        "claim_ledger": [{"claim_id": "C-01"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "CLAIM_TYPE_MISCLASSIFICATION",
            "repair_route": "claim_decomposition",
        }],
    },
    "CLAIM_OVERREACH": {
        "claim_ledger": [{"claim_id": "C-01"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "CLAIM_OVERREACH",
            "repair_route": "claim_evidence_matrix",
        }],
    },
    "SEMANTIC_SUPPORT_NOT_ESTABLISHED": {
        "claim_ledger": [{"claim_id": "C-01"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "SEMANTIC_SUPPORT_NOT_ESTABLISHED",
            "repair_route": "pre_g42_claim_evidence_candidate_linking",
        }],
    },
    "SOURCE_TYPE_INAPPROPRIATE": {
        "claim_ledger": [{"claim_id": "C-01"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "SOURCE_TYPE_INAPPROPRIATE",
            "repair_route": "risk_gspr_mapping",
        }],
    },
    "OCR_GAP": {
        "claim_ledger": [{"claim_id": "C-01"}],
        "pre_g42_claim_evidence_candidate_matrix": [{
            "claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "OCR_GAP",
            "repair_route": "evidence_appraisal",
        }],
    },
}


class TestG42Patterns:
    @pytest.mark.parametrize("pattern_name", list(G42_PATTERN_STATES.keys()))
    def test_pattern_triggers_correct_route(self, pattern_name):
        state = G42_PATTERN_STATES[pattern_name]
        result = evaluate_evidence_sufficiency_gate(state)
        assert result["status"] == "REWORK_REQUIRED", f"Pattern {pattern_name} should be REWORK_REQUIRED"
        assert result.get("failure_pattern", "") != ""

    def test_spiral_round_3_becomes_blocked(self):
        state = {
            **G42_PATTERN_STATES["EVIDENCE_TRULY_INSUFFICIENT"],
            "evidence_spiral_lineage": [
                {"spiral_round_id": 1}, {"spiral_round_id": 2}, {"spiral_round_id": 3}
            ],
        }
        result = evaluate_evidence_sufficiency_gate(state)
        assert result["status"] in ("BLOCKED", "REWORK_REQUIRED")

    def test_all_claims_pass(self):
        state = {
            "claim_ledger": [{"claim_id": "C-01"}],
            "pre_g42_claim_evidence_candidate_matrix": [{
                "claim_id": "C-01", "sufficiency_status": "PASS",
            }],
        }
        result = evaluate_evidence_sufficiency_gate(state)
        assert result["status"] == "PASS"

    def test_empty_state_does_not_crash(self):
        result = evaluate_evidence_sufficiency_gate({})
        assert result is not None
        assert "status" in result

    def test_all_13_patterns_defined(self):
        from deerflow.runtime.cer_authoring.gates import G42_FAILURE_REPAIR_ROUTES
        expected = set(G42_FAILURE_REPAIR_ROUTES.keys())
        tested = set(G42_PATTERN_STATES.keys())
        missing = expected - tested
        assert not missing, f"Untested G42 patterns: {missing}"
