"""Regression tests for CER retrieval/domain fixes that affect E2E runs."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from deerflow.runtime.cer_authoring import mcp_tools, pipeline
from deerflow.runtime.cer_authoring.pipeline import (
    _classify_device_identity,
    _clinical_domain_from_text,
    _database_source_row,
    _device_domain_to_kb_family,
    _device_name_from_filename,
    _infer_device_name_from_sources,
    _phase7_retrieval_domain_profile,
    _protocol_deviations_from_registry,
    _search_run_from_result,
    build_claims,
    run_sota_search,
)
from deerflow.runtime.cer_authoring.writer_remediation.domain_templates import (
    get_domain_template_sections,
)


def test_user_manual_stem_is_not_used_as_device_name() -> None:
    assert _device_name_from_filename("C_XM_User_Manual.pdf") == ""
    assert _device_name_from_filename("Software_User_Manual.pdf") == ""
    assert _device_name_from_filename("IFU of Bubble Study System20260331.docx") == "Bubble Study System"


def test_identity_matching_does_not_read_stent_inside_consistently() -> None:
    state = {
        "source_inventory": [
            {
                "source_id": "SRC-001",
                "filename": "RMF.pdf",
                "document_type": "RMF",
                "source_role": "subject_device_risk_management",
                "text": "The manufacturer consistently maintains risk management records.",
            }
        ]
    }

    identity = _classify_device_identity(
        "Bubble Study System",
        "Automated agitated saline bubble study for right-to-left shunt assessment.",
        "The manufacturer consistently maintains risk management records.",
        state,
    )

    assert identity["clinical_domain"] == "contrast_imaging_bubble_study_system"
    assert identity["clinical_domain"] != "stent_device"
    assert all(row.get("clinical_domain") != "stent_device" for row in identity.get("alternative_candidates", []))


def test_contrast_bubble_domain_claims_are_specific_and_complete() -> None:
    result = build_claims(
        {
            "device_profile": {
                "clinical_domain": "contrast_imaging_bubble_study_system",
                "device_domain": "contrast_imaging_bubble_study_system",
                "intended_purpose": "Bubble Study System for c-TTE/c-TCD right-to-left shunt assessment.",
            },
            "source_inventory": [{"source_id": "SRC-IFU", "document_type": "IFU", "source_role": "subject_device_ifu"}],
        }
    )

    claims = result["claim_ledger"]
    claim_text = " ".join(row["claim_text"] for row in claims).lower()
    assert len(claims) >= 10
    assert "agitated saline" in claim_text
    assert "right-to-left shunt" in claim_text
    assert any(row["claim_type"] == "clinical_benefit" for row in claims)


def test_nuclear_medicine_domain_prefers_domain_default_over_generic_software_name() -> None:
    state = {
        "source_lock_report": {"locked_domain": "nuclear_medicine_image_processing_software"},
        "source_inventory": [
            {
                "filename": "Software_User_Manual.pdf",
                "document_type": "IFU",
                "source_role": "subject_device_ifu",
                "relevance_score": 10,
            }
        ],
    }

    assert _infer_device_name_from_sources(state) == "Medical Image Processing Software"


def test_nuclear_medicine_retrieval_profile_uses_specific_terms() -> None:
    profile = {
        "clinical_domain": "nuclear_medicine_image_processing_software",
        "device_name": "Software Medical Device",
        "device_type": "software medical device",
    }
    state = {"target_keywords": ["SPECT", "nuclear medicine"]}

    retrieval = _phase7_retrieval_domain_profile(profile, state)

    assert retrieval["retrieval_domain"] == "nuclear_medicine_image_processing_software"
    assert "SPECT" in retrieval["inclusion_terms"]
    assert "nuclear medicine" in retrieval["inclusion_terms"]
    assert "catheter ablation" in retrieval["exclusion_terms"]


def test_nuclear_medicine_domain_has_writer_template_dispatch() -> None:
    sections = get_domain_template_sections("nuclear_medicine_image_processing_software")
    assert sections
    assert any("software" in str(section).lower() or "image" in str(section).lower() for section in sections)


def test_contrast_bubble_domain_has_writer_template_dispatch() -> None:
    sections = get_domain_template_sections("contrast_imaging_bubble_study_system")
    assert sections
    assert any("bubble" in str(section).lower() and "right-to-left shunt" in str(section).lower() for section in sections)


def test_contrast_bubble_sota_benchmarks_are_domain_specific(monkeypatch) -> None:
    def fake_execute(row: dict, state: dict, profile: dict) -> dict:
        return {
            "status": "ok",
            "database": row.get("database", "PubMed"),
            "query": row.get("query_string", "bubble study"),
            "records": [],
            "count": 0,
            "returned_count": 0,
        }

    monkeypatch.setattr(pipeline, "_execute_external_database_search", fake_execute)
    result = run_sota_search(
        {
            "device_profile": {
                "clinical_domain": "contrast_imaging_bubble_study_system",
                "device_domain": "contrast_imaging_bubble_study_system",
                "device_name": "Bubble Study System",
            },
            "claim_ledger": [{"claim_id": "C-PERF-02"}],
        }
    )

    benchmarks = result["sota_benchmark_matrix"]
    assert len(benchmarks) >= 8
    assert any("RLS/PFO" in row["endpoint"] for row in benchmarks)
    assert any(row["corresponding_claim_id"] == "C-SAFE-02" for row in benchmarks)


def test_nuclear_medicine_workstation_text_is_not_ai_diagnostic_fallback() -> None:
    text = (
        "Nuclear medicine SPECT/CT image reconstruction workstation for DICOM image "
        "processing, quantitative analysis, PACS transfer, and report generation."
    )

    assert _clinical_domain_from_text(text) == "nuclear_medicine_image_processing_software"
    assert _device_domain_to_kb_family("nuclear_medicine_image_processing_software") == "DEV-SW"


def test_retrieval_gap_is_promoted_to_search_registry_and_protocol_deviation() -> None:
    result = {
        "status": "ok",
        "database": "PubMed",
        "query": "SPECT image processing",
        "count": 42,
        "returned_count": 0,
        "retrieval_gap_note": "PubMed returned count=42 but no PMIDs after retries.",
    }

    registry_row = _search_run_from_result("SEARCH-SOTA-01", result, "SOTA")
    source_row = _database_source_row(registry_row)
    deviations = _protocol_deviations_from_registry([registry_row])

    assert registry_row["retrieval_gap_note"] == result["retrieval_gap_note"]
    assert registry_row["error_message"] == result["retrieval_gap_note"]
    assert source_row["limitation"] == result["retrieval_gap_note"]
    assert deviations[0]["deviation_type"] == "retrieval_result_gap"


def test_pmc_adapter_records_retrieval_gap_when_count_without_idlist(monkeypatch) -> None:
    def fake_fetch_json(url: str) -> dict:
        return {"esearchresult": {"count": "12", "idlist": []}}

    monkeypatch.setattr(mcp_tools, "_adapter_fetch_json", fake_fetch_json)

    result = mcp_tools._adapter_pmc_fulltext_search("SPECT image processing", retmax=5)

    assert result["status"] == "ok"
    assert result["count"] == 12
    assert result["returned_count"] == 0
    assert "retrieval_gap_note" in result


def test_auto_confirm_same_gate_guard_counts_tail() -> None:
    script = Path(__file__).resolve().parents[7] / "backend" / "scripts" / "run_cer_authoring.py"
    spec = importlib.util.spec_from_file_location("run_cer_authoring", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._same_tail_count(["device_profile", "device_profile"], "device_profile") == 2
    assert module._same_tail_count(["device_profile", "claim_decomposition"], "device_profile") == 0
