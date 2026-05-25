#!/usr/bin/env python3
"""
Phase 3M-G Reproduction Script:
Verify that AVAILABLE_SOURCE_LIMITED workflow with frontend-style payload
(containing version_status: "human_confirmed" / "unconfirmed")
does NOT return HTTP 500, and returns a controlled 200 response.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.gateway.app import create_app

app = create_app()
client = TestClient(app)

PAYLOAD = {
    "project_id": "TEST-PHASE3M-G",
    "project_name": "Phase 3M G 500 Fix Test",
    "workflow_mode": "AVAILABLE_SOURCE_LIMITED",
    "source_package_ref": "/tmp/test-source",
    "known_limitations_ref": None,
    "review_scope": ["IFU", "CER", "RMF"],
    "official_cear_allowed": False,
    "final_regulatory_decision_allowed": False,
    "production_claim_allowed": False,
    "ifu_available": True,
    "cer_available": True,
    "rmf_available": False,
    "risk_related_available": False,
    "equivalence_available": False,
    "pmcf_available": False,
    "pms_available": False,
    "gspr_available": False,
    "sscp_available": False,
    "source_documents": [
        {
            "document_id": "SP-0001",
            "document_type": "ifu",
            "file_name": "IFU.pdf",
            "source_path": "/tmp/test-source/IFU.pdf",
            "version_status": "human_confirmed",
            "availability": "available",
            "is_true_source": True,
            "notes": "UI_LOCAL_CONFIRMATION_ONLY",
        },
        {
            "document_id": "SP-0002",
            "document_type": None,
            "file_name": "Unknown.pdf",
            "source_path": "/tmp/test-source/Unknown.pdf",
            "version_status": "unconfirmed",
            "availability": "requires_confirmation",
            "is_true_source": False,
            "notes": "UI_LOCAL_CONFIRMATION_ONLY | MARK_UNKNOWN",
        },
    ],
}


def test_human_confirmed_no_500():
    r = client.post("/api/cer-review/workflows/available-source/run", json=PAYLOAD)
    print(f"Status: {r.status_code}")
    print(f"Body keys: {list(r.json().keys()) if r.status_code == 200 else r.text}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert data["status"] in ("SUCCESS", "HOLD", "LIMITED", "COMPLETED"), f"Unexpected status: {data['status']}"
    assert data["workflow_mode"] in (
        "AVAILABLE_SOURCE_LIMITED",
        "INVENTORY_ONLY_HOLD",
        "CER_ONLY_LIMITED_WITH_IFU_GAP",
    )
    assert data["downgrade_decision"] is not None
    # Boundary preserved
    assert data["boundaries_applied"]["official_cear_allowed"] is False
    assert data["boundaries_applied"]["final_regulatory_decision_allowed"] is False
    assert data["boundaries_applied"]["production_claim_allowed"] is False
    print("PASS: No HTTP 500, controlled response returned.")


if __name__ == "__main__":
    test_human_confirmed_no_500()
