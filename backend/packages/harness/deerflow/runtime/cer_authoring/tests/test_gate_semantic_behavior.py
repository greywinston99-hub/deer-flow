"""Gate semantic behavior tests — prove gates actually enforce reasoning rules."""
import pytest
from deerflow.runtime.cer_authoring.gates import (
    _gate_ifu_working_document,
    _gate_sota_reasoning,
    evaluate_pre_writer_readiness_gate,
)


# ── G_IFU_WORKING_DOCUMENT ──

def test_ifu_overclaim_triggers_fail():
    """IFU claims more than evidence supports → FAIL."""
    result = _gate_ifu_working_document({
        "device_profile": {"clinical_benefit": ""},
        "claim_ledger": [
            {"claim_id": "C1", "claim_type": "clinical_benefit", "support_status": "SUPPORTED"},
        ],
        "ifu_cer_alignment_ledger": {
            "alignments": [
                {"ifu_statement": "complication rate <1%", "alignment_status": "overclaimed_in_ifu"},
            ]
        },
    })
    assert result.status == "FAIL"
    assert "overclaimed" in result.message.lower() or "IFU-G02" in result.message


def test_ifu_missing_benefit_triggers_fail():
    """IFU lacks clinical benefit but CER has supported claims → FAIL."""
    result = _gate_ifu_working_document({
        "device_profile": {"clinical_benefit": "Requires confirmation from IFU"},
        "claim_ledger": [
            {"claim_id": "C1", "claim_type": "clinical_benefit", "support_status": "SUPPORTED"},
        ],
    })
    assert result.status == "FAIL"
    assert "IFU-G01" in result.message or "IFU lacks" in result.message.lower()


def test_ifu_all_aligned_passes():
    """All IFU claims aligned with evidence → PASS."""
    result = _gate_ifu_working_document({
        "device_profile": {"clinical_benefit": "Reduces procedure time"},
        "claim_ledger": [
            {"claim_id": "C1", "claim_type": "clinical_benefit", "support_status": "SUPPORTED"},
        ],
        "ifu_cer_alignment_ledger": {
            "alignments": [{"alignment_status": "aligned"}]
        },
    })
    assert result.status == "PASS"


# ── G_SOTA_REASONING ──

def test_sota_benchmark_number_only_fails():
    """Benchmark has value but no synthesis method → FAIL."""
    result = _gate_sota_reasoning({
        "sota_benchmark_matrix": [
            {"endpoint": "止血有效率", "benchmark_value": "94.5%"},
        ]
    })
    assert result.status == "FAIL"
    assert "SOTA-G01" in result.message or "no synthesis_method" in result.message.lower()


def test_sota_benchmark_no_source_fails():
    """Benchmark has value but no sota_source → FAIL."""
    result = _gate_sota_reasoning({
        "sota_benchmark_matrix": [
            {"endpoint": "止血有效率", "benchmark_value": "94.5%", "synthesis_method": "weighted_mean"},
        ]
    })
    assert result.status == "FAIL"
    assert "SOTA-G02" in result.message or "no evidence source" in result.message.lower()


def test_sota_benchmark_complete_passes():
    """Benchmark has value + method + source → PASS."""
    result = _gate_sota_reasoning({
        "sota_benchmark_matrix": [
            {"endpoint": "止血有效率", "benchmark_value": "94.5%",
             "synthesis_method": "weighted_mean by sample_size",
             "sota_source": "12 studies, 1240 patients"},
        ]
    })
    assert result.status == "PASS"


# ── G46 IFU Granularity ──

def test_g46_ifu_overclaimed_blocks():
    """G46: overclaimed_in_ifu → BLOCKED → does not enter Writer."""
    report = evaluate_pre_writer_readiness_gate({
        "ifu_cer_alignment_ledger": {
            "alignments": [
                {"alignment_status": "overclaimed_in_ifu", "ifu_statement": "complication rate <1%"},
            ]
        },
    })
    # Find IFU_ALIGNMENT condition
    ifu_conds = [c for c in report.get("conditions", []) if c["condition_name"] == "IFU_ALIGNMENT"]
    assert len(ifu_conds) >= 1
    assert ifu_conds[0]["status"] == "BLOCKED"
    assert "overclaimed" in ifu_conds[0]["message"].lower()


def test_g46_ifu_missing_does_not_block():
    """G46: missing_in_ifu → recommendation, does NOT block CER."""
    report = evaluate_pre_writer_readiness_gate({
        "ifu_cer_alignment_ledger": {
            "alignments": [
                {"alignment_status": "missing_in_ifu"},
            ]
        },
    })
    ifu_conds = [c for c in report.get("conditions", []) if c["condition_name"] == "IFU_ALIGNMENT"]
    if ifu_conds:
        # missing_in_ifu should be PASS (recommendation only)
        assert any(c["status"] == "PASS" for c in ifu_conds), \
            f"missing_in_ifu should not block: {ifu_conds}"
