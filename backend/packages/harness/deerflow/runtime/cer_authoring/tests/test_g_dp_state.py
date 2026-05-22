"""G_DP_STATE behavioral tests: 7 DP conditions + edge case."""
from deerflow.runtime.cer_authoring.gates import _gate_defect_state_consistency, GateResult


def test_dp_state_empty_passes():
    """Empty state should PASS."""
    result = _gate_defect_state_consistency({})
    assert result.status == "PASS"
    assert result.gate_id == "G_DP_STATE"


def test_dp005_claim_without_sota():
    """DP-005: claims without SOTA benchmark should FAIL."""
    state = {
        "claim_evidence_matrix": [
            {"claim_id": "C1", "sota_ids": []},
            {"claim_id": "C2", "sota_ids": []},
        ]
    }
    result = _gate_defect_state_consistency(state)
    assert result.status == "FAIL"
    assert "DP-005" in result.message
    assert "C1" in result.message


def test_dp005_claim_with_sota_passes():
    """Claims with SOTA benchmarks should not trigger DP-005."""
    state = {
        "claim_evidence_matrix": [
            {"claim_id": "C1", "sota_ids": ["S1", "S2"]},
        ]
    }
    result = _gate_defect_state_consistency(state)
    # DP-005 shouldn't be the only violation, but we check it's PASS or DP-005 not present
    if result.status == "FAIL":
        assert "DP-005" not in result.message


def test_dp006_g42_insufficient():
    """DP-006: claims with 0 evidence should FAIL."""
    state = {
        "claim_evidence_matrix": [{"claim_id": "C1"}],
        "evidence_registry": [],
    }
    result = _gate_defect_state_consistency(state)
    assert result.status == "FAIL"
    assert "DP-006" in result.message


def test_dp008_no_rmf_for_warning():
    """DP-008: vigilance without RMF should FAIL."""
    state = {
        "vigilance_recall_registry": [{"id": "V1"}, {"id": "V2"}],
        "rmf_registry": [],
    }
    result = _gate_defect_state_consistency(state)
    assert result.status == "FAIL"
    assert "DP-008" in result.message


def test_dp012_pool_below_threshold():
    """DP-012: screening pool below threshold should FAIL."""
    state = {
        "search_run_registry": [{"id": "S1"}, {"id": "S2"}],
        "screening_disposition": [{"id": "SD1"}],
    }
    result = _gate_defect_state_consistency(state)
    assert result.status == "FAIL"
    assert "DP-012" in result.message


def test_dp014_missing_3d_comparison():
    """DP-014: equivalence claimed without 3D data should FAIL."""
    state = {
        "equivalence_strategy": "legacy_mdd",
        "equivalence_3d_matrix": [],
    }
    result = _gate_defect_state_consistency(state)
    assert result.status == "FAIL"
    assert "DP-014" in result.message


def test_dp015_gspr_without_evidence():
    """DP-015: GSPR items without evidence mapping should FAIL."""
    state = {
        "gspr_checklist": [
            {"evidence_ids": []},
            {"evidence_ids": []},
            {"clinical_evidence_refs": ["E1"]},
        ],
    }
    result = _gate_defect_state_consistency(state)
    assert result.status == "FAIL"
    assert "DP-015" in result.message
    assert "2/3" in result.message
