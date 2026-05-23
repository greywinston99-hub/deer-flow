"""CER NocoDB machine asset binding layer.

Provides NocoDB-backed machine knowledge asset storage with a SQLite fallback.

The local NocoDB instance currently exposes:
- metadata APIs on ``/api/v1/db/meta/...``
- row CRUD on ``/api/v2/tables/{table_id}/records``
- session auth via ``POST /api/v1/auth/user/signin`` plus cookies
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import httpx

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────

CER_ARTIFACTS_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer")
KNOWLEDGE_STORE_ROOT = CER_ARTIFACTS_ROOT / "knowledge_store"
SQLITE_DB_PATH = KNOWLEDGE_STORE_ROOT / "cer_knowledge.db"
PUBLICATION_OUTPUT_ROOT = CER_ARTIFACTS_ROOT / "knowledge_publication"

# ── NocoDB config ─────────────────────────────────────────────────────────────

NOCODB_BASE_URL = os.environ.get("NOCODB_BASE_URL", "http://localhost:8081").rstrip("/")
NOCODB_V1_API = f"{NOCODB_BASE_URL}/api/v1"
NOCODB_V2_API = f"{NOCODB_BASE_URL}/api/v2"
NOCODB_EMAIL = os.environ.get("NOCODB_EMAIL", "")
NOCODB_PASSWORD = os.environ.get("NOCODB_PASSWORD", "")
NOCODB_BASE_ID = os.environ.get("NOCODB_BASE_ID", "")
NOCODB_TIMEOUT = float(os.environ.get("NOCODB_TIMEOUT", "10"))


def _nocodb_configured() -> bool:
    return bool(NOCODB_EMAIL and NOCODB_PASSWORD and NOCODB_BASE_ID)


@contextmanager
def _nocodb_session(timeout: float | None = None) -> Iterator[httpx.Client]:
    """Create an authenticated NocoDB session using the cookie-based auth flow."""
    if not _nocodb_configured():
        raise RuntimeError("NocoDB is missing NOCODB_EMAIL, NOCODB_PASSWORD, or NOCODB_BASE_ID")

    client = httpx.Client(timeout=timeout or NOCODB_TIMEOUT)
    try:
        signin = client.post(
            f"{NOCODB_V1_API}/auth/user/signin",
            json={"email": NOCODB_EMAIL, "password": NOCODB_PASSWORD},
        )
        if signin.status_code != 200:
            raise RuntimeError(f"NocoDB signin failed: {signin.status_code} {signin.text}")
        yield client
    finally:
        client.close()


# ── Binding Status ─────────────────────────────────────────────────────────────

class DBBindingStatus(str):
    NOCODB_ACTIVE = "NOCODB_ACTIVE"
    SQLITE_FALLBACK_ACTIVE = "SQLITE_FALLBACK_ACTIVE"
    DB_UNAVAILABLE = "DB_UNAVAILABLE"


# ── Health Check ────────────────────────────────────────────────────────────────

def check_nocodb_health(timeout: int = 5) -> bool:
    """Check if NocoDB is reachable."""
    try:
        resp = httpx.get(f"{NOCODB_V1_API}/health", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def _nocodb_ready(timeout: int = 5) -> bool:
    """Check whether NocoDB is reachable, configured, and usable."""
    if not check_nocodb_health(timeout=timeout):
        return False
    if not _nocodb_configured():
        return False

    try:
        with _nocodb_session(timeout=timeout) as client:
            resp = client.get(f"{NOCODB_V1_API}/db/meta/projects/{NOCODB_BASE_ID}/tables")
            return resp.status_code == 200
    except Exception:
        return False


def get_binding_status() -> str:
    """Determine which DB binding is currently active."""
    if _nocodb_ready():
        return DBBindingStatus.NOCODB_ACTIVE

    try:
        if SQLITE_DB_PATH.exists():
            conn = sqlite3.connect(str(SQLITE_DB_PATH))
            cur = conn.execute("SELECT COUNT(*) FROM knowledge_assets LIMIT 1")
            count = cur.fetchone()[0]
            conn.close()
            if count > 0:
                return DBBindingStatus.SQLITE_FALLBACK_ACTIVE
    except Exception:
        pass

    return DBBindingStatus.DB_UNAVAILABLE


# ── SQLite helpers (fallback) ──────────────────────────────────────────────────

def _get_sqlite_conn():
    PUBLICATION_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_STORE_ROOT.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_sqlite_schema(conn)
    return conn


def _init_sqlite_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS knowledge_assets (
            asset_id TEXT PRIMARY KEY,
            asset_type TEXT NOT NULL,
            title TEXT,
            summary TEXT,
            regulatory_context TEXT,
            source_project_id TEXT NOT NULL,
            source_run_id TEXT,
            source_artifact_path TEXT,
            source_excerpt TEXT,
            applicability_boundary TEXT,
            generalizability_level TEXT,
            confidence REAL,
            status TEXT NOT NULL,
            approved_by TEXT,
            approved_at TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS knowledge_review_decisions (
            id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            notes TEXT,
            decided_by TEXT,
            decided_at TEXT
        );
        CREATE TABLE IF NOT EXISTS knowledge_usage_logs (
            id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            used_by_project_id TEXT,
            used_in_workflow TEXT,
            relevance_reason TEXT,
            used_at TEXT
        );
        CREATE TABLE IF NOT EXISTS workflow_improvements (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            improvement_type TEXT NOT NULL,
            description TEXT,
            source_needs_correction_id TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS knowledge_sources (
            id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            document_type TEXT,
            document_path TEXT,
            page_reference TEXT,
            excerpt TEXT
        );
    """)
    conn.commit()


# ── NocoDB helpers ─────────────────────────────────────────────────────────────

NOCODB_TABLE_SCHEMAS = {
    "knowledge_assets": [
        {"column_name": "asset_id", "uidt": "SingleLineText"},
        {"column_name": "asset_type", "uidt": "SingleLineText"},
        {"column_name": "title", "uidt": "SingleLineText"},
        {"column_name": "summary", "uidt": "LongText"},
        {"column_name": "regulatory_context", "uidt": "SingleLineText"},
        {"column_name": "source_project_id", "uidt": "SingleLineText"},
        {"column_name": "source_run_id", "uidt": "SingleLineText"},
        {"column_name": "source_artifact_path", "uidt": "LongText"},
        {"column_name": "source_excerpt", "uidt": "LongText"},
        {"column_name": "applicability_boundary", "uidt": "LongText"},
        {"column_name": "generalizability_level", "uidt": "SingleLineText"},
        {"column_name": "confidence", "uidt": "Decimal"},
        {"column_name": "status", "uidt": "SingleLineText"},
        {"column_name": "approved_by", "uidt": "SingleLineText"},
        {"column_name": "approved_at", "uidt": "DateTime"},
        {"column_name": "created_at", "uidt": "DateTime"},
        {"column_name": "updated_at", "uidt": "DateTime"},
    ],
    "knowledge_review_decisions": [
        {"column_name": "id", "uidt": "SingleLineText"},
        {"column_name": "asset_id", "uidt": "SingleLineText"},
        {"column_name": "project_id", "uidt": "SingleLineText"},
        {"column_name": "decision", "uidt": "SingleLineText"},
        {"column_name": "notes", "uidt": "LongText"},
        {"column_name": "decided_by", "uidt": "SingleLineText"},
        {"column_name": "decided_at", "uidt": "DateTime"},
    ],
    "knowledge_usage_logs": [
        {"column_name": "id", "uidt": "SingleLineText"},
        {"column_name": "asset_id", "uidt": "SingleLineText"},
        {"column_name": "used_by_project_id", "uidt": "SingleLineText"},
        {"column_name": "used_in_workflow", "uidt": "SingleLineText"},
        {"column_name": "relevance_reason", "uidt": "LongText"},
        {"column_name": "used_at", "uidt": "DateTime"},
    ],
    "workflow_improvements": [
        {"column_name": "id", "uidt": "SingleLineText"},
        {"column_name": "project_id", "uidt": "SingleLineText"},
        {"column_name": "improvement_type", "uidt": "SingleLineText"},
        {"column_name": "description", "uidt": "LongText"},
        {"column_name": "source_needs_correction_id", "uidt": "SingleLineText"},
        {"column_name": "created_at", "uidt": "DateTime"},
    ],
    "knowledge_sources": [
        {"column_name": "id", "uidt": "SingleLineText"},
        {"column_name": "asset_id", "uidt": "SingleLineText"},
        {"column_name": "document_type", "uidt": "SingleLineText"},
        {"column_name": "document_path", "uidt": "LongText"},
        {"column_name": "page_reference", "uidt": "SingleLineText"},
        {"column_name": "excerpt", "uidt": "LongText"},
    ],
}


def _list_nocodb_tables(client: httpx.Client) -> list[dict[str, Any]]:
    resp = client.get(f"{NOCODB_V1_API}/db/meta/projects/{NOCODB_BASE_ID}/tables")
    if resp.status_code != 200:
        raise RuntimeError(f"NocoDB table list failed: {resp.status_code} {resp.text}")
    return resp.json().get("list", [])


def _get_nocodb_table_map(client: httpx.Client) -> dict[str, dict[str, Any]]:
    return {table["table_name"]: table for table in _list_nocodb_tables(client)}


def _create_nocodb_table(
    client: httpx.Client,
    table_name: str,
    columns: list[dict[str, str]],
) -> bool:
    resp = client.post(
        f"{NOCODB_V1_API}/db/meta/projects/{NOCODB_BASE_ID}/tables",
        json={"table_name": table_name, "title": table_name, "columns": columns},
    )
    if resp.status_code in (200, 201):
        return True
    logger.warning("Failed to create NocoDB table %s: %s %s", table_name, resp.status_code, resp.text)
    return False


def setup_nocodb_schema() -> dict[str, bool]:
    """Ensure all required tables exist in NocoDB.

    Returns dict of table_name -> created (True) or already_exists (False).
    """
    if not _nocodb_ready():
        return {}

    results: dict[str, bool] = {}
    with _nocodb_session() as client:
        existing_tables = _get_nocodb_table_map(client)
        for table_name, columns in NOCODB_TABLE_SCHEMAS.items():
            if table_name in existing_tables:
                results[table_name] = False
                continue
            results[table_name] = _create_nocodb_table(client, table_name, columns)
            time.sleep(0.2)
    return results


def _list_records(
    client: httpx.Client,
    table_id: str,
    *,
    where: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    if where:
        params["where"] = where
    resp = client.get(f"{NOCODB_V2_API}/tables/{table_id}/records", params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"NocoDB record list failed: {resp.status_code} {resp.text}")
    return resp.json().get("list", [])


def _nocodb_upsert(
    client: httpx.Client,
    table_map: dict[str, dict[str, Any]],
    table_name: str,
    record: dict[str, Any],
    key_field: str,
) -> bool:
    """Upsert a record into a NocoDB table."""
    table = table_map.get(table_name)
    if not table:
        logger.warning("NocoDB table %s is missing from metadata", table_name)
        return False

    key_value = record.get(key_field)
    if key_value is None:
        logger.warning("NocoDB upsert skipped for %s: missing key field %s", table_name, key_field)
        return False

    try:
        rows = _list_records(
            client,
            table["id"],
            where=f"({key_field},eq,{key_value})",
            limit=1,
        )
        if rows:
            payload = {"Id": rows[0].get("Id"), **record}
            resp = client.patch(f"{NOCODB_V2_API}/tables/{table['id']}/records", json=payload)
            return resp.status_code in (200, 201)

        resp = client.post(f"{NOCODB_V2_API}/tables/{table['id']}/records", json=record)
        return resp.status_code in (200, 201)
    except Exception as exc:
        logger.error("NocoDB upsert failed for %s/%s: %s", table_name, key_value, exc)
        return False


def _nocodb_query_one(
    client: httpx.Client,
    table_map: dict[str, dict[str, Any]],
    table_name: str,
    *,
    where: str,
) -> dict[str, Any] | None:
    table = table_map.get(table_name)
    if not table:
        return None
    rows = _list_records(client, table["id"], where=where, limit=1)
    return rows[0] if rows else None


def _nocodb_query_many(
    client: httpx.Client,
    table_map: dict[str, dict[str, Any]],
    table_name: str,
    *,
    where: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    table = table_map.get(table_name)
    if not table:
        return []
    return _list_records(client, table["id"], where=where, limit=limit)


# ── SQLite write helpers ───────────────────────────────────────────────────────

def _sqlite_upsert_asset(asset: dict[str, Any]) -> bool:
    """Upsert asset to SQLite."""
    try:
        conn = _get_sqlite_conn()
        conn.execute("""
            INSERT OR REPLACE INTO knowledge_assets
            (asset_id, asset_type, title, summary, regulatory_context,
             source_project_id, source_run_id, source_artifact_path,
             source_excerpt, applicability_boundary, generalizability_level,
             confidence, status, approved_by, approved_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            asset.get("asset_id"), asset.get("asset_type"), asset.get("title"),
            asset.get("summary"), asset.get("regulatory_context"),
            asset.get("source_project_id"), asset.get("source_run_id"),
            asset.get("source_artifact_path"), asset.get("source_excerpt"),
            asset.get("applicability_boundary"), asset.get("generalizability_level"),
            asset.get("confidence"), asset.get("status"), asset.get("approved_by"),
            asset.get("approved_at"), asset.get("created_at"), asset.get("updated_at"),
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as exc:
        logger.error("SQLite upsert failed: %s", exc)
        return False


def _sqlite_upsert_decision(decision: dict[str, Any]) -> bool:
    """Upsert review decision to SQLite."""
    try:
        conn = _get_sqlite_conn()
        conn.execute("""
            INSERT OR REPLACE INTO knowledge_review_decisions
            (id, asset_id, project_id, decision, notes, decided_by, decided_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            decision.get("id"), decision.get("asset_id"), decision.get("project_id"),
            decision.get("decision"), decision.get("notes"), decision.get("decided_by"),
            decision.get("decided_at"),
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as exc:
        logger.error("SQLite decision upsert failed: %s", exc)
        return False


# ── Record builder ─────────────────────────────────────────────────────────────

def _build_asset_record(asset_data: dict[str, Any]) -> dict[str, Any]:
    """Convert machine asset JSON to DB record format."""
    payload = asset_data.get("payload", {})
    metadata = asset_data.get("metadata", {})

    source_excerpt = None
    if isinstance(payload, dict):
        source_excerpt = (
            payload.get("definition")
            or payload.get("description")
            or (f"{payload.get('term', '')}: {payload.get('definition', '')}" if "term" in payload else None)
            or payload.get("rule_text", "")[:200]
        )

    return {
        "asset_id": asset_data.get("asset_id"),
        "asset_type": asset_data.get("asset_type"),
        "title": payload.get("title") if isinstance(payload, dict) else None,
        "summary": payload.get("description") if isinstance(payload, dict) else None,
        "regulatory_context": payload.get("regulatory_context", "MDR_EU") if isinstance(payload, dict) else "MDR_EU",
        "source_project_id": asset_data.get("project_id"),
        "source_run_id": metadata.get("integration_run_id") or asset_data.get("integration_run_id"),
        "source_artifact_path": asset_data.get("source_artifact"),
        "source_excerpt": source_excerpt,
        "applicability_boundary": payload.get("applicability_boundary") if isinstance(payload, dict) else None,
        "generalizability_level": payload.get("generalizability_level") if isinstance(payload, dict) else "project_specific",
        "confidence": asset_data.get("confidence"),
        "status": asset_data.get("state"),
        "approved_by": metadata.get("reviewed_by"),
        "approved_at": metadata.get("reviewed_at"),
        "created_at": metadata.get("extracted_at"),
        "updated_at": metadata.get("published_at"),
    }


# ── Core sync functions ───────────────────────────────────────────────────────

def sync_to_nocodb(project_id: str) -> dict[str, Any]:
    """Sync approved knowledge assets to NocoDB.

    Returns:
        Dict with published_count, binding_status, errors
    """
    # ── Hard Boundary: no_nocodb_writes ──────────────────────────────────────
    if os.environ.get("CER_REVIEW_NO_NOCODB_WRITES") == "1":
        logger.warning(
            "NocoDB write blocked by hard boundary (CER_REVIEW_NO_NOCODB_WRITES=1). "
            "Project %s assets will remain in local SQLite only.",
            project_id,
        )
        return {
            "published_count": 0,
            "binding_status": "BLOCKED_BY_HARD_BOUNDARY",
            "fallback": "sqlite",
            "errors": [],
        }
    # ── End hard boundary ────────────────────────────────────────────────────
    status = get_binding_status()
    machine_root = KNOWLEDGE_STORE_ROOT / "machine_assets"
    nocodb_records: list[dict[str, Any]] = []
    sqlite_records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for asset_type_folder in machine_root.iterdir():
        if not asset_type_folder.is_dir():
            continue

        project_folder = asset_type_folder / project_id
        if not project_folder.exists():
            continue

        for json_file in project_folder.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as fh:
                    asset_data = json.load(fh)

                metadata = asset_data.get("metadata", {})
                review_decision = (metadata.get("review_decision") or "").upper()
                if review_decision not in ("APPROVE", "APPROVED"):
                    continue

                record = _build_asset_record(asset_data)

                if status == DBBindingStatus.NOCODB_ACTIVE:
                    nocodb_records.append(record)
                else:
                    sqlite_records.append(record)
            except Exception as exc:
                errors.append({"file": str(json_file), "error": str(exc)})

    published_count = 0

    if status == DBBindingStatus.NOCODB_ACTIVE:
        schema_results = setup_nocodb_schema()
        if not schema_results and not _nocodb_ready():
            status = DBBindingStatus.SQLITE_FALLBACK_ACTIVE
        else:
            try:
                with _nocodb_session() as client:
                    table_map = _get_nocodb_table_map(client)

                    for record in nocodb_records:
                        if _nocodb_upsert(client, table_map, "knowledge_assets", record, "asset_id"):
                            published_count += 1
                        else:
                            _sqlite_upsert_asset(record)
                            published_count += 1

                    for asset_type_folder in machine_root.iterdir():
                        if not asset_type_folder.is_dir():
                            continue
                        project_folder = asset_type_folder / project_id
                        if not project_folder.exists():
                            continue
                        for json_file in project_folder.glob("*.json"):
                            try:
                                with open(json_file, encoding="utf-8") as fh:
                                    asset_data = json.load(fh)
                                metadata = asset_data.get("metadata", {})
                                review_decision = (metadata.get("review_decision") or "").upper()
                                if review_decision not in ("APPROVE", "APPROVED"):
                                    continue
                                decision = {
                                    "id": f"KRD-{uuid.uuid4().hex[:12]}",
                                    "asset_id": asset_data.get("asset_id"),
                                    "project_id": project_id,
                                    "decision": metadata.get("review_decision", "APPROVED"),
                                    "notes": metadata.get("review_notes"),
                                    "decided_by": metadata.get("reviewed_by"),
                                    "decided_at": metadata.get("reviewed_at"),
                                }
                                if not _nocodb_upsert(client, table_map, "knowledge_review_decisions", decision, "id"):
                                    _sqlite_upsert_decision(decision)
                            except Exception:
                                pass
            except Exception as exc:
                logger.warning("NocoDB sync failed; falling back to SQLite: %s", exc)
                status = DBBindingStatus.SQLITE_FALLBACK_ACTIVE

    if status == DBBindingStatus.SQLITE_FALLBACK_ACTIVE:
        for record in sqlite_records or nocodb_records:
            if _sqlite_upsert_asset(record):
                published_count += 1

    return {
        "published_count": published_count,
        "binding_status": status,
        "nocodb_active": status == DBBindingStatus.NOCODB_ACTIVE,
        "errors": errors,
    }


def sync_all_projects_to_nocodb() -> dict[str, Any]:
    """Sync all projects' approved assets to NocoDB."""
    machine_root = KNOWLEDGE_STORE_ROOT / "machine_assets"
    results = {}
    total_published = 0

    for asset_type_folder in machine_root.iterdir():
        if not asset_type_folder.is_dir():
            continue

        for project_folder in asset_type_folder.iterdir():
            if not project_folder.is_dir():
                continue
            project_id = project_folder.name
            if project_id in results:
                continue
            result = sync_to_nocodb(project_id)
            results[project_id] = result
            total_published += result["published_count"]

    return {"total_published": total_published, "projects": results}


# ── Readback ───────────────────────────────────────────────────────────────────

def query_nocodb_asset(asset_id: str) -> dict[str, Any] | None:
    """Query one approved asset from NocoDB."""
    if get_binding_status() != DBBindingStatus.NOCODB_ACTIVE:
        return None
    try:
        with _nocodb_session() as client:
            table_map = _get_nocodb_table_map(client)
            return _nocodb_query_one(
                client,
                table_map,
                "knowledge_assets",
                where=f"(asset_id,eq,{asset_id})",
            )
    except Exception as exc:
        logger.warning("NocoDB query failed: %s", exc)
        return None


def query_nocodb_assets_by_type(asset_type: str) -> list[dict[str, Any]]:
    """Query all approved assets of a type from NocoDB."""
    if get_binding_status() != DBBindingStatus.NOCODB_ACTIVE:
        return []
    try:
        with _nocodb_session() as client:
            table_map = _get_nocodb_table_map(client)
            return _nocodb_query_many(
                client,
                table_map,
                "knowledge_assets",
                where=f"(asset_type,eq,{asset_type})~and(status,eq,published)",
                limit=100,
            )
    except Exception as exc:
        logger.warning("NocoDB query by type failed: %s", exc)
        return []


def query_sqlite_asset(asset_id: str) -> dict[str, Any] | None:
    """Query one approved asset from SQLite."""
    try:
        conn = _get_sqlite_conn()
        row = conn.execute(
            "SELECT * FROM knowledge_assets WHERE asset_id = ? AND status IN ('approved', 'published')",
            (asset_id,),
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
    except Exception:
        pass
    return None


def query_approved_asset(asset_id: str) -> dict[str, Any] | None:
    """Query one approved asset. Prefers NocoDB, falls back to SQLite."""
    if get_binding_status() == DBBindingStatus.NOCODB_ACTIVE:
        result = query_nocodb_asset(asset_id)
        if result:
            return result
    return query_sqlite_asset(asset_id)


def query_approved_reusable_assets(
    device_category: str | None = None,
    notified_body: str | None = None,
    asset_type: str | None = None,
    regulatory_boundary: str | None = None,
    generalizability: str | None = None,
    reusable: bool | None = None,
    reuse_allowed: bool | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query approved/active reusable assets with anti-pollution filters.

    ANTI-POLLUTION RULES:
    - Only returns status IN ('approved', 'active')
    - Excludes: candidate, human_review_required, rejected, parked, machine_draft
    - NB-specific filtering: If device is NB-specific, only use for that NB
    - Device category filtering: If device category specific, only use for that category
    - Returns empty list if no approved/active exist (NO fallback to candidate)

    Args:
        device_category: Filter by device category (e.g., 'blood_purification')
        notified_body: Filter by notified body (e.g., 'TÜV')
        asset_type: Filter by asset type (e.g., 'finding_knowledge_card')
        regulatory_boundary: Filter by regulatory boundary (e.g., 'EU MDR 2017/745')
        generalizability: Filter by generalizability level
        reusable: If True, only return assets where reusable=True
        reuse_allowed: If True, only return assets where reuse_allowed=True
        limit: Maximum number of records to return

    Returns:
        List of approved/active assets matching filters, or empty list if none found.
    """
    status = get_binding_status()

    if status == DBBindingStatus.NOCODB_ACTIVE:
        return _nocodb_query_reusable_assets(
            device_category=device_category,
            notified_body=notified_body,
            asset_type=asset_type,
            regulatory_boundary=regulatory_boundary,
            generalizability=generalizability,
            reusable=reusable,
            reuse_allowed=reuse_allowed,
            limit=limit,
        )
    elif status == DBBindingStatus.SQLITE_FALLBACK_ACTIVE:
        return _sqlite_query_reusable_assets(
            device_category=device_category,
            notified_body=notified_body,
            asset_type=asset_type,
            regulatory_boundary=regulatory_boundary,
            generalizability=generalizability,
            reusable=reusable,
            reuse_allowed=reuse_allowed,
            limit=limit,
        )
    else:
        logger.warning(
            "query_approved_reusable_assets: DB unavailable (binding_status=%s). "
            "Returning empty list.",
            status,
        )
        return []


def _nocodb_query_reusable_assets(
    device_category: str | None = None,
    notified_body: str | None = None,
    asset_type: str | None = None,
    regulatory_boundary: str | None = None,
    generalizability: str | None = None,
    reusable: bool | None = None,
    reuse_allowed: bool | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query reusable assets from NocoDB with anti-pollution filters.

    NOTE: device_category and notified_body are encoded in applicability_boundary
    (LongText field). For precise filtering, use applicability_boundary contains
    or decode the boundary text. The direct column filters below use fields
    that exist in the NocoDB schema.
    """
    try:
        with _nocodb_session() as client:
            table_map = _get_nocodb_table_map(client)
            if "knowledge_assets" not in table_map:
                logger.warning("NocoDB table 'knowledge_assets' not found")
                return []

            # Build WHERE clause — only approved/active, anti-pollution
            # NocoDB filter syntax: (field,eq,value) ~or(condition)
            conditions = ["(status,eq,approved)~or(status,eq,active)"]

            # asset_type uses the actual column
            if asset_type:
                conditions.append(f"(asset_type,eq,{asset_type})")
            # regulatory_context maps to regulatory_boundary parameter
            if regulatory_boundary:
                conditions.append(f"(regulatory_context,eq,{regulatory_boundary})")
            # generalizability_level uses the actual column
            if generalizability:
                conditions.append(f"(generalizability_level,eq,{generalizability})")
            # reusable/reuse_allowed use applicability_boundary encoded values
            if reusable is True:
                conditions.append("(applicability_boundary,cs,reusable:true)")
            if reuse_allowed is True:
                conditions.append("(applicability_boundary,cs,reuse_allowed:true)")
            # device_category/notified_body are encoded in applicability_boundary
            if device_category:
                conditions.append(f"(applicability_boundary,cs,{device_category})")
            if notified_body:
                conditions.append(f"(applicability_boundary,cs,notified_body:{notified_body})")

            where = "~and(".join(conditions) + ")" * (len(conditions) - 1) if conditions else ""

            return _nocodb_query_many(
                client,
                table_map,
                "knowledge_assets",
                where=where,
                limit=limit,
            )
    except Exception as exc:
        logger.warning("NocoDB query_reusable_assets failed: %s", exc)
        return []


def _sqlite_query_reusable_assets(
    device_category: str | None = None,
    notified_body: str | None = None,
    asset_type: str | None = None,
    regulatory_boundary: str | None = None,
    generalizability: str | None = None,
    reusable: bool | None = None,
    reuse_allowed: bool | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query reusable assets from SQLite with anti-pollution filters.

    NOTE: device_category and notified_body are encoded in applicability_boundary
    (LongText field). The SQLite schema does not have separate columns for these.
    For now, device_category and notified_body filters are logged as unsupported
    and ignored, since the schema doesn't store these separately.
    """
    try:
        conn = _get_sqlite_conn()

        # Base query — only approved/active, anti-pollution
        query = "SELECT * FROM knowledge_assets WHERE status IN ('approved', 'active')"
        params: list[Any] = []

        if device_category:
            # applicability_boundary encodes device_category info
            query += " AND (applicability_boundary LIKE ?)"
            params.append(f"%{device_category}%")
        if notified_body:
            # applicability_boundary encodes notified_body info
            query += " AND (applicability_boundary LIKE ?)"
            params.append(f"%notified_body:{notified_body}%")
        if asset_type:
            query += " AND (asset_type = ?)"
            params.append(asset_type)
        if regulatory_boundary:
            # regulatory_context column maps to regulatory_boundary parameter
            query += " AND (regulatory_context = ?)"
            params.append(regulatory_boundary)
        if generalizability:
            query += " AND (generalizability_level = ?)"
            params.append(generalizability)
        if reusable is True:
            query += " AND (applicability_boundary LIKE '%reusable:true%')"
        if reuse_allowed is True:
            query += " AND (applicability_boundary LIKE '%reuse_allowed:true%')"

        query += " ORDER BY confidence DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.warning("SQLite query_reusable_assets failed: %s", exc)
        return []


def readback_smoke_test() -> dict[str, Any]:
    """Smoke test: read any approved asset from active DB."""
    status = get_binding_status()

    if status == DBBindingStatus.NOCODB_ACTIVE:
        try:
            with _nocodb_session() as client:
                table_map = _get_nocodb_table_map(client)
                rows = _nocodb_query_many(
                    client,
                    table_map,
                    "knowledge_assets",
                    where="(status,eq,published)",
                    limit=1,
                )
                if rows:
                    row = rows[0]
                    return {
                        "passed": True,
                        "asset_id": row.get("asset_id"),
                        "asset_type": row.get("asset_type"),
                        "source_project_id": row.get("source_project_id"),
                        "status": row.get("status"),
                        "binding_status": status,
                        "message": "Readback smoke test PASSED (NocoDB)",
                    }
        except Exception as exc:
            logger.warning("NocoDB readback smoke test failed: %s", exc)

    try:
        conn = _get_sqlite_conn()
        row = conn.execute(
            "SELECT * FROM knowledge_assets WHERE status IN ('approved', 'published') LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            record = dict(row)
            return {
                "passed": True,
                "asset_id": record.get("asset_id"),
                "asset_type": record.get("asset_type"),
                "source_project_id": record.get("source_project_id"),
                "status": record.get("status"),
                "binding_status": DBBindingStatus.SQLITE_FALLBACK_ACTIVE,
                "message": "Readback smoke test PASSED (SQLite fallback)",
            }
    except Exception as exc:
        return {"passed": False, "message": f"SQLite readback failed: {exc}"}

    return {"passed": False, "binding_status": status, "message": "No published assets found"}
