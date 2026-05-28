from deerflow.runtime.cer_authoring.gates import evaluate_cep_exists_gate, evaluate_pre_writer_readiness_gate
from deerflow.runtime.cer_authoring.pipeline import write_cer_chapters


def test_missing_cep_blocks_pre_writer_readiness() -> None:
    report = evaluate_pre_writer_readiness_gate({"pre_writer_readiness_condition_overrides": {}})
    assert report["status"] in {"REWORK_REQUIRED", "BLOCKED"}
    assert any(row["condition_name"] == "CEP" for row in report["failing_sub_conditions"])


def test_empty_cep_method_fields_fail_gate() -> None:
    result = evaluate_cep_exists_gate({"clinical_evaluation_plan": {"device_name": "Device"}})
    assert result.status == "REWORK_REQUIRED"
    assert "incomplete" in result.message.lower()


def test_source_preflight_blocks_writer() -> None:
    generated = write_cer_chapters(
        {
            "source_preflight_gate_report": {
                "status": "BLOCKED",
                "blocking_issues": [{"issue_id": "IFU-P0-PLACEHOLDER"}],
            }
        }
    )
    assert generated["writer_invocation_allowed"] is False
    assert generated["writer_invocation_guard"]["required_gate"] == "SOURCE_PREFLIGHT"


def test_benefit_risk_not_concludable_blocks_writer() -> None:
    generated = write_cer_chapters(
        {
            "clinical_evaluation_plan": {
                "device_name": "Device",
                "device_class": "IIa",
                "scope": "Scope",
                "literature_search_protocol": {
                    "databases": ["PubMed"],
                    "inclusion_criteria": ["aligned"],
                    "exclusion_criteria": ["not aligned"],
                },
                "appraisal_method": "MEDDEV",
                "sota_methodology": "systematic search",
                "claim_support_method": "claim matrix",
                "benefit_risk_method": "RMF/PMS",
                "pms_pmcf_update_plan": {"objective": "follow-up"},
            },
            "benefit_risk_closure_matrix": {"closure_status": "NOT_CONCLUDABLE"},
        }
    )
    assert generated["writer_invocation_allowed"] is False
    assert generated["writer_invocation_guard"]["required_gate"] == "BR_CLOSURE_GATE"
