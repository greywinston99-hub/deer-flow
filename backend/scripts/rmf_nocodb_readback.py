"""
RMF NocoDB Readback Module

Provides actual NocoDB readback for RMF dry-run.
Uses the same NocoDB binding as CER knowledge system.

This module is used by rmf_harness_dry_run.py to perform
actual readback of approved/published knowledge assets from NocoDB.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── NocoDB config (mirrors cer_nocodb_binding.py) ─────────────────────────────

NOCODB_BASE_URL = os.environ.get("NOCODB_BASE_URL", "http://localhost:8081").rstrip("/")
NOCODB_V1_API = f"{NOCODB_BASE_URL}/api/v1"
NOCODB_V2_API = f"{NOCODB_BASE_URL}/api/v2"
NOCODB_EMAIL = os.environ.get("NOCODB_EMAIL", "")
NOCODB_PASSWORD = os.environ.get("NOCODB_PASSWORD", "")
NOCODB_BASE_ID = os.environ.get("NOCODB_BASE_ID", "")
NOCODB_TIMEOUT = float(os.environ.get("NOCODB_TIMEOUT", "10"))


def _nocodb_configured() -> bool:
    return bool(NOCODB_EMAIL and NOCODB_PASSWORD and NOCODB_BASE_ID)


def check_nocodb_health(timeout: int = 5) -> bool:
    """Check if NocoDB is reachable."""
    try:
        resp = httpx.get(f"{NOCODB_V1_API}/health", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def _nocodb_session(timeout: float | None = None) -> httpx.Client:
    """Create an authenticated NocoDB session using cookie-based auth flow."""
    if not _nocodb_configured():
        raise RuntimeError("NocoDB is missing NOCODB_EMAIL, NOCODB_PASSWORD, or NOCODB_BASE_ID")

    client = httpx.Client(timeout=timeout or NOCODB_TIMEOUT)
    signin = client.post(
        f"{NOCODB_V1_API}/auth/user/signin",
        json={"email": NOCODB_EMAIL, "password": NOCODB_PASSWORD},
    )
    if signin.status_code != 200:
        raise RuntimeError(f"NocoDB signin failed: {signin.status_code} {signin.text}")
    return client


def _list_tables(client: httpx.Client) -> list[dict[str, Any]]:
    resp = client.get(f"{NOCODB_V1_API}/db/meta/projects/{NOCODB_BASE_ID}/tables")
    if resp.status_code != 200:
        raise RuntimeError(f"NocoDB table list failed: {resp.status_code} {resp.text}")
    return resp.json().get("list", [])


def _get_table_map(client: httpx.Client) -> dict[str, dict[str, Any]]:
    return {table["table_name"]: table for table in _list_tables(client)}


def _query_records(
    client: httpx.Client,
    table_id: str,
    *,
    where: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    if where:
        params["where"] = where
    resp = client.get(f"{NOCODB_V2_API}/tables/{table_id}/records", params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"NocoDB record list failed: {resp.status_code} {resp.text}")
    return resp.json().get("list", [])


# ── RMF-specific knowledge readback ─────────────────────────────────────────

# RMF-relevant asset types (may not match actual NocoDB content exactly)
# Query all approved/published and let downstream filter
RMF_ASSET_TYPES = [
    "review_checklist",
    "failure_pattern",
    "boundary_condition",
    "institution_profile",
    "review_heuristic",
    # Also include types that may exist in NocoDB
    "TerminologyUnit",
    "RuleUnit",
    "EvidenceRequirement",
    "FailurePattern",
]


def readback_approved_knowledge_assets() -> dict[str, Any]:
    """
    Read back approved/published knowledge assets from NocoDB.

    Returns:
        Dict with:
        - actual_connection: bool
        - source: "nocodb"
        - asset_count: int
        - assets: list of asset records
        - degraded_mode: bool
        - error: str or None
        - readback_timestamp: ISO8601

    Excludes:
        - rejected
        - parked
        - needs_human_review
    """
    result = {
        "actual_connection": False,
        "source": "nocodb",
        "asset_count": 0,
        "assets": [],
        "degraded_mode": True,
        "error": None,
        "readback_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Check if NocoDB is configured
    if not _nocodb_configured():
        result["error"] = "NocoDB not configured (missing env vars)"
        return result

    # Check if NocoDB is reachable
    if not check_nocodb_health():
        result["error"] = "NocoDB health check failed"
        return result

    try:
        client = _nocodb_session()
        try:
            table_map = _get_table_map(client)

            knowledge_assets_table = table_map.get("knowledge_assets")
            if not knowledge_assets_table:
                result["error"] = "knowledge_assets table not found"
                return result

            table_id = knowledge_assets_table["id"]

            # Query for approved OR published status
            # Exclude: rejected, parked, needs_human_review
            rows = _query_records(
                client,
                table_id,
                where="(status,eq,published)~or(status,eq,approved)",
                limit=100,
            )

            # Include all approved/published assets (RMF agents filter as needed)
            # Note: TerminologyUnit, EvidenceRequirement, FailurePattern exist in NocoDB
            # but may not have matching asset_type values in knowledge_assets
            result["actual_connection"] = True
            result["degraded_mode"] = False
            result["asset_count"] = len(rows)
            result["assets"] = rows

            return result

        finally:
            client.close()

    except Exception as exc:
        logger.warning("NocoDB readback failed: %s", exc)
        result["error"] = str(exc)
        return result


def write_knowledge_assets_to_file(
    output_path: Path,
    project_id: str,
    rmf_run_id: str,
) -> dict[str, Any]:
    """
    Read knowledge assets from NocoDB and write to artifact file.

    Returns the same dict as readback_approved_knowledge_assets(), but also
    writes the result to output_path.
    """
    result = readback_approved_knowledge_assets()

    # Add metadata
    result["_meta"] = {
        "project_id": project_id,
        "rmf_run_id": rmf_run_id,
        "readback_timestamp": datetime.now(timezone.utc).isoformat(),
        "nocodb_url": NOCODB_BASE_URL,
        "asset_types_included": RMF_ASSET_TYPES,
        "status_filter": ["approved", "published"],
        "statuses_excluded": ["rejected", "parked", "needs_human_review"],
    }

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    return result


if __name__ == "__main__":
    # Test readback
    print("Testing NocoDB readback...")
    result = readback_knowledge_assets()
    print(f"actual_connection: {result['actual_connection']}")
    print(f"asset_count: {result['asset_count']}")
    print(f"degraded_mode: {result['degraded_mode']}")
    if result["error"]:
        print(f"error: {result['error']}")
    else:
        print(f"assets: {len(result['assets'])}")
        for asset in result["assets"][:3]:
            print(f"  - {asset.get('asset_id')}: {asset.get('asset_type')} ({asset.get('status')})")
