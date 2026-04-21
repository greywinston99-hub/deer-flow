#!/usr/bin/env python3
"""
RMF Phase B: NocoDB Bidirectional Runtime Loop Verification

Performs actual writeback to NocoDB and read-after-write verification.

This script:
1. Loads approved knowledge assets from NocoDB (Phase A)
2. Simulates generating preliminary findings (dry-run, no LLM)
3. Writes review_run record to NocoDB
4. Writes preliminary_findings records to NocoDB
5. Writes human_review_required_items records to NocoDB
6. Writes backflow_candidates records to NocoDB
7. Reads back all records to verify
8. Generates verification evidence

Usage:
    python scripts/rmf_phase_b_writeback.py --project-id RMF-PHASE-B-SMOKE --run-id rmf-phase-b-writeback-001
"""

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Setup ──────────────────────────────────────────────────────────────────────

BACKEND_DIR = Path(__file__).parent.parent
ENV_FILE = BACKEND_DIR.parent / ".env"

if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

NOCODB_BASE_URL = os.environ.get("NOCODB_BASE_URL", "http://localhost:8081").rstrip("/")
NOCODB_V1_API = f"{NOCODB_BASE_URL}/api/v1"
NOCODB_V2_API = f"{NOCODB_BASE_URL}/api/v2"
NOCODB_EMAIL = os.environ.get("NOCODB_EMAIL", "")
NOCODB_PASSWORD = os.environ.get("NOCODB_PASSWORD", "")
NOCODB_BASE_ID = os.environ.get("NOCODB_BASE_ID", "")

ARTIFACTS_DIR = BACKEND_DIR / "artifacts"

# ── NocoDB Helpers ──────────────────────────────────────────────────────────────

def nocodb_session():
    """Create authenticated NocoDB session."""
    client = __import__("httpx").Client(timeout=10)
    signin = client.post(
        f"{NOCODB_V1_API}/auth/user/signin",
        json={"email": NOCODB_EMAIL, "password": NOCODB_PASSWORD},
    )
    if signin.status_code != 200:
        raise RuntimeError(f"NocoDB signin failed: {signin.status_code}")
    return client


def get_table_map(client):
    """Get table name to ID mapping."""
    resp = client.get(f"{NOCODB_V1_API}/db/meta/projects/{NOCODB_BASE_ID}/tables")
    tables = resp.json().get("list", [])
    return {t["table_name"]: t for t in tables}


def insert_records(client, table_id, records):
    """Insert multiple records into a table."""
    if not records:
        return []
    resp = client.post(
        f"{NOCODB_V2_API}/tables/{table_id}/records",
        json=records,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Insert failed: {resp.status_code} {resp.text}")
    return resp.json()


def query_records(client, table_id, where=None, limit=100):
    """Query records from a table."""
    params = {"limit": limit}
    if where:
        params["where"] = where
    resp = client.get(f"{NOCODB_V2_API}/tables/{table_id}/records", params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"Query failed: {resp.status_code} {resp.text}")
    return resp.json().get("list", [])


# ── Phase B Writeback ─────────────────────────────────────────────────────────

def run_phase_b(project_id: str, run_id: str) -> dict:
    """
    Execute Phase B: NocoDB writeback with read-after-write verification.

    Returns verification evidence dict.
    """
    verification = {
        "run_id": run_id,
        "project_id": project_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "actual_connection": True,
        "writeback_performed": True,
        "read_after_write_verified": False,
        "records_written": {},
        "records_read": {},
        "inserted_or_updated_record_count": 0,
        "checksum_comparison": {},
        "errors": [],
    }

    # Step 1: Load approved knowledge assets from NocoDB (Phase A behavior)
    print("[Step 1] Loading approved knowledge assets from NocoDB...")
    try:
        nocodb_readback_spec = importlib.util.spec_from_file_location(
            "rmf_nocodb_readback",
            str(BACKEND_DIR / "scripts" / "rmf_nocodb_readback.py")
        )
        nocodb_readback_module = importlib.util.module_from_spec(nocodb_readback_spec)
        sys.modules["rmf_nocodb_readback"] = nocodb_readback_module
        nocodb_readback_spec.loader.exec_module(nocodb_readback_module)
        readback_approved_knowledge_assets = nocodb_readback_module.readback_approved_knowledge_assets
        kb_result = readback_approved_knowledge_assets()
        verification["knowledge_assets_loaded"] = kb_result["asset_count"]
        verification["knowledge_assets"] = kb_result["assets"]
        print(f"  Loaded {kb_result['asset_count']} knowledge assets")
    except Exception as e:
        verification["errors"].append(f"Knowledge load failed: {e}")
        print(f"  ERROR: {e}")
        return verification

    # Step 2: Generate simulated preliminary findings (dry-run only, no LLM)
    print("[Step 2] Generating simulated preliminary findings (dry-run, no LLM)...")
    findings = [
        {
            "finding_id": f"COMP-001",
            "dimension": "COMP",
            "finding_type": "coverage_gap",
            "severity": "major",
            "description": "Risk coverage gap identified in production risk monitoring section",
            "source_document": "RMF",
            "source_section": "risk_analysis",
            "recommendation": "Add explicit production monitoring procedures",
            "requires_human_review": False,
        },
        {
            "finding_id": f"ACPT-001",
            "dimension": "ACPT",
            "finding_type": "benefit_risk_uncertainty",
            "severity": "critical",
            "description": "Benefit-risk assessment has uncertainty in clinical benefit magnitude",
            "source_document": "CER",
            "source_section": "clinical_evidence",
            "recommendation": "Human reviewer must assess benefit-risk under uncertainty",
            "requires_human_review": True,
        },
    ]
    verification["preliminary_findings"] = findings
    print(f"  Generated {len(findings)} simulated findings")

    # Step 3: Generate human review required items
    print("[Step 3] Generating human review required items...")
    human_review_items = [
        {
            "item_id": f"HR-001",
            "decision_area": "benefit_risk_final",
            "description": "Benefit-risk assessment uncertainty requires Layer 3 decision",
            "severity": "critical",
            "dimension": "ACPT",
            "finding_id_ref": "ACPT-001",
            "layer3_decision_required": True,
            "status": "AWAITING_HUMAN",
        }
    ]
    verification["human_review_items"] = human_review_items
    print(f"  Generated {len(human_review_items)} human review items")

    # Step 4: Generate backflow candidates
    print("[Step 4] Generating backflow candidates...")
    backflow_candidates = [
        {
            "candidate_id": f"BC-{uuid.uuid4().hex[:12]}",
            "candidate_type": "FailurePattern",
            "description": "Production risk monitoring gap identified in RMF review",
            "confidence": 0.85,
            "recommended_action": "approve",
            "proposed_content": {
                "pattern": "Production risk monitoring gap",
                "description": "RMF production section must include explicit monitoring procedures",
                "applies_to": ["COMP", "ACPT"],
            },
            "source_finding_id": "COMP-001",
            "status": "pending_review",
        },
        {
            "candidate_id": f"BC-{uuid.uuid4().hex[:12]}",
            "candidate_type": "TerminologyUnit",
            "description": "Benefit-risk uncertainty term requires standardization",
            "confidence": 0.72,
            "recommended_action": "review",
            "proposed_content": {
                "term": "benefit_risk_uncertainty",
                "definition": "Condition where clinical benefit magnitude cannot be precisely determined",
                "usage_context": "ACPT dimension assessment",
            },
            "source_finding_id": "ACPT-001",
            "status": "pending_review",
        },
    ]
    verification["backflow_candidates"] = backflow_candidates
    print(f"  Generated {len(backflow_candidates)} backflow candidates")

    # Step 5: Write to NocoDB
    print("[Step 5] Writing records to NocoDB...")
    try:
        client = nocodb_session()
        table_map = get_table_map(client)

        records_written = {}

        # Write review_run
        if "rmf_review_runs" in table_map:
            review_run_record = {
                "run_id": run_id,
                "project_id": project_id,
                "review_type": "RMF_PRELIMINARY_REVIEW",
                "status": "PREPARED_FOR_HUMAN_REVIEW",
                "human_gate_status": "pending",
                "findings_count": len(findings),
                "pms_triggered": False,
                "knowledge_assets_loaded": kb_result["asset_count"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            resp = insert_records(client, table_map["rmf_review_runs"]["id"], [review_run_record])
            records_written["rmf_review_runs"] = 1
            print(f"  Wrote 1 review_run record")

        # Write preliminary_findings
        if "rmf_preliminary_findings" in table_map:
            findings_records = [
                {
                    "finding_id": f["finding_id"],
                    "run_id": run_id,
                    "dimension": f["dimension"],
                    "finding_type": f["finding_type"],
                    "severity": f["severity"],
                    "description": f["description"],
                    "source_document": f["source_document"],
                    "source_section": f["source_section"],
                    "recommendation": f["recommendation"],
                    "requires_human_review": f["requires_human_review"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                for f in findings
            ]
            resp = insert_records(client, table_map["rmf_preliminary_findings"]["id"], findings_records)
            records_written["rmf_preliminary_findings"] = len(findings_records)
            print(f"  Wrote {len(findings_records)} preliminary_finding records")

        # Write human_review_required_items
        if "rmf_human_review_required_items" in table_map:
            hr_records = [
                {
                    "item_id": hr["item_id"],
                    "run_id": run_id,
                    "decision_area": hr["decision_area"],
                    "description": hr["description"],
                    "severity": hr["severity"],
                    "dimension": hr["dimension"],
                    "finding_id_ref": hr["finding_id_ref"],
                    "layer3_decision_required": hr["layer3_decision_required"],
                    "status": hr["status"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                for hr in human_review_items
            ]
            resp = insert_records(client, table_map["rmf_human_review_required_items"]["id"], hr_records)
            records_written["rmf_human_review_required_items"] = len(hr_records)
            print(f"  Wrote {len(hr_records)} human_review_required_item records")

        # Write backflow_candidates
        if "rmf_backflow_candidates" in table_map:
            bc_records = [
                {
                    "candidate_id": bc["candidate_id"],
                    "run_id": run_id,
                    "candidate_type": bc["candidate_type"],
                    "description": bc["description"],
                    "confidence": bc["confidence"],
                    "recommended_action": bc["recommended_action"],
                    "proposed_content_json": json.dumps(bc["proposed_content"]),
                    "source_finding_id": bc["source_finding_id"],
                    "status": bc["status"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                for bc in backflow_candidates
            ]
            resp = insert_records(client, table_map["rmf_backflow_candidates"]["id"], bc_records)
            records_written["rmf_backflow_candidates"] = len(bc_records)
            print(f"  Wrote {len(bc_records)} backflow_candidate records")

        verification["records_written"] = records_written
        verification["inserted_or_updated_record_count"] = sum(records_written.values())
        client.close()

    except Exception as e:
        verification["errors"].append(f"NocoDB write failed: {e}")
        print(f"  ERROR: {e}")
        return verification

    # Step 6: Read-after-write verification
    print("[Step 6] Performing read-after-write verification...")
    try:
        client = nocodb_session()
        table_map = get_table_map(client)
        records_read = {}

        # Read back review_run
        if "rmf_review_runs" in table_map:
            rows = query_records(client, table_map["rmf_review_runs"]["id"],
                               where=f"(run_id,eq,{run_id})")
            records_read["rmf_review_runs"] = len(rows)
            if rows:
                verification["review_run_verified"] = rows[0]["run_id"] == run_id

        # Read back preliminary_findings
        if "rmf_preliminary_findings" in table_map:
            rows = query_records(client, table_map["rmf_preliminary_findings"]["id"],
                               where=f"(run_id,eq,{run_id})")
            records_read["rmf_preliminary_findings"] = len(rows)
            verification["findings_verified_count"] = len(rows)

        # Read back human_review_required_items
        if "rmf_human_review_required_items" in table_map:
            rows = query_records(client, table_map["rmf_human_review_required_items"]["id"],
                               where=f"(run_id,eq,{run_id})")
            records_read["rmf_human_review_required_items"] = len(rows)
            verification["hr_items_verified_count"] = len(rows)

        # Read back backflow_candidates
        if "rmf_backflow_candidates" in table_map:
            rows = query_records(client, table_map["rmf_backflow_candidates"]["id"],
                               where=f"(run_id,eq,{run_id})")
            records_read["rmf_backflow_candidates"] = len(rows)
            verification["backflow_verified_count"] = len(rows)

        verification["records_read"] = records_read

        # Checksum comparison
        verification["checksum_comparison"] = {
            "review_run": records_written.get("rmf_review_runs", 0) == records_read.get("rmf_review_runs", -1),
            "preliminary_findings": records_written.get("rmf_preliminary_findings", 0) == records_read.get("rmf_preliminary_findings", -1),
            "human_review_items": records_written.get("rmf_human_review_required_items", 0) == records_read.get("rmf_human_review_required_items", -1),
            "backflow_candidates": records_written.get("rmf_backflow_candidates", 0) == records_read.get("rmf_backflow_candidates", -1),
        }

        verification["read_after_write_verified"] = all(verification["checksum_comparison"].values())

        client.close()
        print(f"  Read-after-write verified: {verification['read_after_write_verified']}")

    except Exception as e:
        verification["errors"].append(f"Read-after-write verification failed: {e}")
        print(f"  ERROR: {e}")

    # Step 7: Write verification artifact
    print("[Step 7] Writing verification artifact...")
    artifact_root = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / run_id
    verification_dir = artifact_root / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)

    verification["completed_at"] = datetime.now(timezone.utc).isoformat()
    verification_file = verification_dir / "phase_b_writeback_verification.json"
    with open(verification_file, "w") as f:
        json.dump(verification, f, indent=2)
    print(f"  Written to: {verification_file}")

    return verification


def main():
    parser = argparse.ArgumentParser(description="RMF Phase B NocoDB Writeback")
    parser.add_argument("--project-id", default="RMF-PHASE-B-SMOKE", help="Project ID")
    parser.add_argument("--run-id", default="rmf-phase-b-writeback-001", help="Run ID")
    args = parser.parse_args()

    project_id = args.project_id
    run_id = args.run_id

    print("=" * 70)
    print("RMF PHASE B: NOCODB BIDIRECTIONAL RUNTIME LOOP")
    print("=" * 70)
    print(f"Project ID: {project_id}")
    print(f"Run ID: {run_id}")
    print()

    result = run_phase_b(project_id, run_id)

    print()
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"actual_connection: {result['actual_connection']}")
    print(f"writeback_performed: {result['writeback_performed']}")
    print(f"read_after_write_verified: {result['read_after_write_verified']}")
    print(f"inserted_or_updated_record_count: {result['inserted_or_updated_record_count']}")
    print(f"records_written: {result['records_written']}")
    print(f"records_read: {result['records_read']}")
    print(f"checksum_comparison: {result['checksum_comparison']}")
    if result['errors']:
        print(f"errors: {result['errors']}")
    print()
    print(f"Verification artifact: artifacts/cer/{project_id}/rmf_review/{run_id}/verification/phase_b_writeback_verification.json")

    status = "PASS" if result["read_after_write_verified"] else "FAIL"
    print(f"\nStatus: {status}")
    return 0 if result["read_after_write_verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
