"""test_live_api.py — Live HTTP verification of CER DAG halt state via FastAPI.

Steps:
1. Create a transient mock project_profile.yaml + CER.txt designed to trigger
   a severity-based halt (missing benefit-risk elements).
2. POST /api/cer/start
3. GET  /api/cer/status/{thread_id}
4. Assert response contains human_adjudication_pending, halted_node, resume_from_node.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import httpx

API_BASE = "http://localhost:8001"
AUTH_HEADERS = {
    "X-CER-User-ID": "live-test-user",
    "X-CER-User-Role": "SENIOR_REVIEWER",
}
TIMEOUT = httpx.Timeout(300.0, connect=30.0)


def _write_project_profile(tmpdir: Path, project_id: str) -> Path:
    profile = {
        "project_id": project_id,
        "project_name": f"Live API Test {project_id}",
        "institution_profile": {"organization": "Test Org", "assessment_body": "Test Body"},
        "review_scope": {"mode": "smoke_precheck", "review_language": "en", "jurisdiction": "EU MDR"},
        "primary_review_object": "CER",
        "device_context": {
            "device_name": "Test Device",
            "device_family": "Test Family",
            "device_class": "Class IIa",
            "intended_use": "Test device for pediatric lesion treatment.",
            "market_stage": "technical_documentation_review",
            "implantable_status": False,
            "intended_purpose_confirmed": True,
        },
        "project_protocol": {
            "project_id": project_id,
            "product_name": "Test Device",
            "device_class": "Class IIa",
            "gate_a_status": "draft",
            "assessment_type": "smoke_precheck",
        },
        "input_package": {
            "root_path": str(tmpdir / "input"),
            "documents": [
                {
                    "doc_type": "CER",
                    "label": "Clinical Evaluation Report",
                    "path": "CER.txt",
                    "required_for_p0": True,
                    "source_ref": {"document_id": "cer_main", "path": "CER.txt"},
                }
            ],
        },
        "artifact_policy": {
            "artifact_root": "/mnt/user-data/outputs/cer_review_v0/${run_id}/artifacts",
            "persist_intermediate_artifacts": True,
        },
    }
    path = tmpdir / "project_profile.yaml"
    import yaml
    path.write_text(yaml.dump(profile), encoding="utf-8")
    return path


def _write_cer_text(path: Path) -> None:
    content = """
Clinical Evaluation Report

1. INTENDED PURPOSE
The device is intended for pediatric lesion treatment.

2. EQUIVALENCE
Equivalence is demonstrated with Predicate Device XYZ.
Technical: design, specification, energy.
Biological: material, biocompatibility, contact, duration, sterilization.
Clinical: patient population, indication, user, use environment, clinical outcome.

3. BENEFIT-RISK
ALARP (As Low As Reasonably Practicable) has been applied.
No explicit acceptable or unacceptable statements.
"""
    path.write_text(content, encoding="utf-8")


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="cer_live_api_test_"))
    try:
        input_dir = tmpdir / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        _write_cer_text(input_dir / "CER.txt")

        project_id = f"LIVE-{uuid.uuid4().hex[:6]}"
        profile_path = _write_project_profile(tmpdir, project_id)

        payload = {
            "project_profile": str(profile_path),
            "input_root": str(input_dir),
            "mode": "smoke-run",
        }

        print("=== Step A: POST /api/cer/start ===")
        with httpx.Client(base_url=API_BASE, timeout=TIMEOUT, headers=AUTH_HEADERS) as client:
            resp_start = client.post("/api/cer/start", json=payload)
            print(f"Status: {resp_start.status_code}")
            print(resp_start.text)
            print()

            if resp_start.status_code != 200:
                print("START failed — aborting.")
                return 1

            start_data = resp_start.json()
            thread_id = start_data["thread_id"]
            run_id = start_data["run_id"]
            halt_state = start_data.get("halt_state")

            print(f"thread_id: {thread_id}")
            print(f"run_id:    {run_id}")
            print(f"halt_state from /start: {json.dumps(halt_state, indent=2, ensure_ascii=False)}")
            print()

            print("=== Step B: GET /api/cer/status/{thread_id} ===")
            resp_status = client.get(f"/api/cer/status/{thread_id}")
            print(f"Status: {resp_status.status_code}")
            status_data = resp_status.json()
            print(json.dumps(status_data, indent=2, ensure_ascii=False))
            print()

        # Acceptance assertions
        checks = {
            "status_code_200": resp_status.status_code == 200,
            "human_adjudication_pending_true": status_data.get("human_adjudication_pending") is True,
            "halted_node_present": bool(status_data.get("halted_node")),
            "resume_from_node_present": bool(status_data.get("resume_from_node")),
        }

        print("=== Acceptance Checks ===")
        for name, passed in checks.items():
            print(f"  {'PASS' if passed else 'FAIL'}  {name}")

        overall = all(checks.values())
        print()
        print(f"Overall: {'PASS' if overall else 'FAIL'}")
        return 0 if overall else 1

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
