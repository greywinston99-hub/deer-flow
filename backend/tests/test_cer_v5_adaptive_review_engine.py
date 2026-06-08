from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gateway.app import create_app


AUTH_HEADERS = {
    "X-CER-User-ID": "dev-senior",
    "X-CER-User-Name": "Dev Senior Reviewer",
    "X-CER-User-Role": "SENIOR_REVIEWER",
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _sample_family_groups() -> list[dict]:
    return [
        {
            "group_id": "SF-IFU",
            "source_type": "ifu",
            "recommended_canonical_file_id": "ifu-1",
            "recommended_canonical_reason": "Controlled IFU PDF with matching release metadata",
            "confidence": 0.94,
            "group_status": "RECOMMENDED_READY_FOR_CONFIRMATION",
            "candidates": [
                {
                    "file_id": "ifu-1",
                    "file_name": "IFU_HeartPump_v2.1.pdf",
                    "relative_path": "docs/IFU_HeartPump_v2.1.pdf",
                    "auto_classified_type": "ifu",
                    "ranking_score": 0.94,
                    "readability_status": "PASS",
                    "file_hash_sha256": "abc123",
                    "negative_signals": [],
                    "size_bytes": 125000,
                }
            ],
            "alternatives": [],
            "companion_files": [],
            "duplicate_files": [],
            "open_file_required": [],
            "missing_reason": None,
        },
        {
            "group_id": "SF-CER",
            "source_type": "cer",
            "recommended_canonical_file_id": "cer-1",
            "recommended_canonical_reason": "Clinical evaluation report selected from canonical group",
            "confidence": 0.82,
            "group_status": "MULTIPLE_CANDIDATES_NEED_REVIEW",
            "candidates": [
                {
                    "file_id": "cer-1",
                    "file_name": "CER_2024.pdf",
                    "relative_path": "docs/CER_2024.pdf",
                    "auto_classified_type": "cer",
                    "ranking_score": 0.82,
                    "readability_status": "PASS",
                    "size_bytes": 310000,
                }
            ],
            "alternatives": [
                {
                    "file_id": "cer-legacy",
                    "file_name": "CER_2023.pdf",
                    "relative_path": "docs/archive/CER_2023.pdf",
                    "auto_classified_type": "cer",
                    "ranking_score": 0.61,
                    "readability_status": "PASS",
                    "size_bytes": 250000,
                }
            ],
            "companion_files": [],
            "duplicate_files": [],
            "open_file_required": [],
            "missing_reason": None,
        },
        {
            "group_id": "SF-RMF",
            "source_type": "rmf",
            "recommended_canonical_file_id": "rmf-1",
            "recommended_canonical_reason": "Spreadsheet detected but still requires open-file review",
            "confidence": 0.74,
            "group_status": "READABILITY_INSUFFICIENT",
            "candidates": [
                {
                    "file_id": "rmf-1",
                    "file_name": "RMF_2024.xlsx",
                    "relative_path": "docs/RMF_2024.xlsx",
                    "auto_classified_type": "rmf",
                    "ranking_score": 0.74,
                    "readability_status": "NEEDS_OPEN_FILE_CHECK",
                    "size_bytes": 150000000,
                    "negative_signals": ["large spreadsheet"],
                }
            ],
            "alternatives": [],
            "companion_files": [],
            "duplicate_files": [],
            "open_file_required": [
                {
                    "file_id": "rmf-1",
                    "file_name": "RMF_2024.xlsx",
                    "relative_path": "docs/RMF_2024.xlsx",
                    "auto_classified_type": "rmf",
                    "ranking_score": 0.74,
                    "readability_status": "NEEDS_OPEN_FILE_CHECK",
                    "size_bytes": 150000000,
                }
            ],
            "missing_reason": None,
        },
        {
            "group_id": "SF-EQUIV",
            "source_type": "equivalence",
            "recommended_canonical_file_id": "eq-1",
            "recommended_canonical_reason": "Equivalence matrix found",
            "confidence": 0.57,
            "group_status": "LOW_CONFIDENCE_NEED_OPEN_FILE_CHECK",
            "candidates": [
                {
                    "file_id": "eq-1",
                    "file_name": "Equivalence_Matrix.xlsx",
                    "relative_path": "docs/Equivalence_Matrix.xlsx",
                    "auto_classified_type": "equivalence",
                    "ranking_score": 0.57,
                    "readability_status": "PASS",
                    "size_bytes": 190000,
                }
            ],
            "alternatives": [],
            "companion_files": [],
            "duplicate_files": [],
            "open_file_required": [],
            "missing_reason": None,
        },
    ]


def test_builds_slot_workbench_with_v5_metadata(client: TestClient) -> None:
    response = client.post(
        "/api/cer-review/v5/CER_RMF_174/slots/build",
        headers=AUTH_HEADERS,
        json={"source_family_groups": _sample_family_groups()},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data["slots"]) == 12
    ifu_slot = next(slot for slot in data["slots"] if slot["slot_type"] == "IFU")
    rmf_slot = next(slot for slot in data["slots"] if slot["slot_type"] == "RMF_RISK")
    pmcf_slot = next(slot for slot in data["slots"] if slot["slot_type"] == "PMCF")

    assert ifu_slot["confidence_band"] == "HIGH"
    assert ifu_slot["integrity_status"] == "HASH_PRESENT"
    assert ifu_slot["direct_evidence_link"].endswith("IFU_HeartPump_v2.1.pdf")
    assert rmf_slot["confidence_band"] != "HIGH"
    assert "LARGE_FILE" in rmf_slot["risk_flags"]
    assert pmcf_slot["slot_status"] == "MISSING"
    assert any(item["slot_type"] == "IFU" for item in data["heatmap"])


def test_gap_analysis_returns_actionable_paths(client: TestClient) -> None:
    build = client.post(
        "/api/cer-review/v5/CER_RMF_174/slots/build",
        headers=AUTH_HEADERS,
        json={"source_family_groups": _sample_family_groups()},
    ).json()

    response = client.post(
        "/api/cer-review/v5/CER_RMF_174/gaps/analyze",
        headers=AUTH_HEADERS,
        json={"slot_workbench_id": build["slot_workbench_id"], "flavor_profile": "STRICT"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    gap_types = {gap["gap_type"] for gap in data["g_points"]}

    assert data["workflow_can_continue"] in {"NO", "LIMITED"}
    assert "missing_source" in gap_types
    assert "rmf_gap" in gap_types
    assert any(gap["next_action"] for gap in data["g_points"])


def test_copilot_and_backtest_remain_sandbox_only(client: TestClient) -> None:
    build = client.post(
        "/api/cer-review/v5/CER_RMF_174/slots/build",
        headers=AUTH_HEADERS,
        json={"source_family_groups": _sample_family_groups()},
    ).json()
    gap = client.post(
        "/api/cer-review/v5/CER_RMF_174/gaps/analyze",
        headers=AUTH_HEADERS,
        json={"slot_workbench_id": build["slot_workbench_id"], "flavor_profile": "BALANCED"},
    ).json()

    copilot = client.post(
        "/api/cer-review/v5/CER_RMF_174/copilot/draft",
        headers=AUTH_HEADERS,
        json={
            "current_view": "slot_workbench",
            "slot_workbench_id": build["slot_workbench_id"],
            "gap_analysis_id": gap["gap_analysis_id"],
            "reviewer_question": "Can I run limited review?",
        },
    )
    assert copilot.status_code == 200, copilot.text
    copilot_data = copilot.json()
    assert copilot_data["boundary_notes"]
    assert any(s["requires_human_confirmation"] for s in copilot_data["suggestions"])

    batch = client.post(
        "/api/cer-review/v5/CER_RMF_174/copilot/batch-draft",
        headers=AUTH_HEADERS,
        json={"operation": "stage_high_confidence", "slot_workbench_id": build["slot_workbench_id"]},
    )
    assert batch.status_code == 200, batch.text
    batch_data = batch.json()
    assert batch_data["requires_confirmation"] is True

    backtest = client.post(
        "/api/cer-review/v5/CER_RMF_174/shadow-backtest/run",
        headers=AUTH_HEADERS,
        json={
            "slot_workbench_id": build["slot_workbench_id"],
            "parameter_candidates": {"confidence_score_delta": -0.05, "open_file_penalty": 0.1},
        },
    )
    assert backtest.status_code == 200, backtest.text
    report = backtest.json()["report"]
    assert report["rollback_plan"]
    assert report["sandbox_only"] is True
    assert report["approval_required"] is True
