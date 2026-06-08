import json

from deerflow.runtime.cer_review.review_assist_lead_agent import (
    SMState,
    _extract_stage_json_from_text,
)


def _valid_gap_payload() -> dict:
    return {
        "schema_name": "cer_review_gap_findings",
        "schema_version": "v2",
        "reviewer_decision": "PENDING",
        "candidate_findings": [
            {
                "finding_id": "GAP-001",
                "type": "missing_document",
                "severity_advisory": "HIGH",
                "evidence": [
                    {
                        "source_file": "source_inventory.json",
                        "location": "manifest",
                        "excerpt": "CER document absent from inventory",
                    }
                ],
            }
        ],
    }


def test_gap_parser_accepts_clean_json():
    payload = _valid_gap_payload()

    data, diagnostics = _extract_stage_json_from_text(json.dumps(payload), SMState.GAP_ANALYSIS_DONE)

    assert data == payload
    assert diagnostics["schema_validation_result"]["valid"] is True
    assert diagnostics["candidate_count"] == 1
    assert diagnostics["extraction_strategy"] == "embedded_json_object"


def test_gap_parser_accepts_fenced_json():
    payload = _valid_gap_payload()

    data, diagnostics = _extract_stage_json_from_text(
        "```json\n" + json.dumps(payload) + "\n```",
        SMState.GAP_ANALYSIS_DONE,
    )

    assert data == payload
    assert diagnostics["schema_validation_result"]["valid"] is True
    assert diagnostics["extraction_strategy"] == "markdown_json_fence"


def test_gap_parser_accepts_schema_valid_json_with_surrounding_text():
    payload = _valid_gap_payload()
    text = "<think>reasoning omitted</think>\nHere is the payload:\n```json\n" + json.dumps(payload) + "\n```\nDone."

    data, diagnostics = _extract_stage_json_from_text(text, SMState.GAP_ANALYSIS_DONE)

    assert data == payload
    assert diagnostics["schema_validation_result"]["valid"] is True
    assert "polluted_output_recovered" in diagnostics["warning_flags"]


def test_gap_parser_accepts_empty_result_schema():
    payload = {
        "schema_name": "cer_review_gap_findings",
        "schema_version": "v2",
        "project_id": "PROJECT_021",
        "review_session_id": "test-session",
        "generated_at": "2026-05-01T00:00:00Z",
        "reviewer_decision": "PENDING",
        "source_inventory_ref": "source_inventory.json",
        "candidate_findings": [],
        "summary": {
            "total_gaps": 0,
            "blocking_gaps": 0,
            "warning_gaps": 0,
            "informational_gaps": 0,
        },
        "pipeline_limitations": [],
    }

    data, diagnostics = _extract_stage_json_from_text(json.dumps(payload), SMState.GAP_ANALYSIS_DONE)

    assert data == payload
    assert diagnostics["schema_validation_result"]["valid"] is True
    assert diagnostics["candidate_count"] == 0


def test_gap_parser_rejects_non_schema_json_with_precise_classification():
    data, diagnostics = _extract_stage_json_from_text(
        '{"summary": "not the gap schema"}',
        SMState.GAP_ANALYSIS_DONE,
    )

    assert data is None
    validation = diagnostics["schema_validation_result"]
    assert validation["valid"] is False
    assert validation["classification"] == "GAP_SPECIALIST_SCHEMA_CONTRACT_FAILURE"
    assert "candidate_findings must be present and must be a list" in validation["errors"]


def test_gap_parser_never_treats_upstream_artifact_missing_as_zero_findings():
    data, diagnostics = _extract_stage_json_from_text(
        json.dumps(
            {
                "candidate_findings": [],
                "reviewer_decision": "PENDING",
                "upstream_artifact_missing": True,
            }
        ),
        SMState.GAP_ANALYSIS_DONE,
    )

    assert data is None
    validation = diagnostics["schema_validation_result"]
    assert validation["valid"] is False
    assert validation["classification"] == "GAP_SPECIALIST_SCHEMA_CONTRACT_FAILURE"
    assert "upstream_artifact_missing_not_zero_findings" in diagnostics["candidate_attempts"][0]["warning_flags"]


def test_gap_parser_classifies_failed_smoke_raw_output_as_schema_contract_failure():
    failed_smoke_raw = """<think>
I need to write candidate_findings.json immediately.
</think>

Looking at the source_inventory, the evidence package contains only one document.
I will write the candidate_findings.json immediately to capture these findings.
"""

    data, diagnostics = _extract_stage_json_from_text(failed_smoke_raw, SMState.GAP_ANALYSIS_DONE)

    assert data is None
    validation = diagnostics["schema_validation_result"]
    assert validation["valid"] is False
    assert validation["classification"] == "GAP_SPECIALIST_SCHEMA_CONTRACT_FAILURE"
