"""CER Knowledge Publication — External Binding Sync Runner.

Publishes approved knowledge assets to external containers:
  - Obsidian Vault: /Users/winstonwei/CER-RAG/🔋CER项目/04_KNOWLEDGE_CARDS/
  - Machine DB: NocoDB (preferred) or SQLite (fallback)

Binding decision is delegated to cer_nocodb_binding.get_binding_status():
  - NOCODB_ACTIVE: write to NocoDB
  - SQLITE_FALLBACK_ACTIVE: write to SQLite
  - DB_UNAVAILABLE: log warning, skip DB write

This module is idempotent and generates publication manifests.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.gateway.routers.cer_nocodb_binding import (
    DBBindingStatus,
    get_binding_status,
    sync_to_nocodb as nocodb_sync_to_nocodb,
)

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────

CER_ARTIFACTS_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer")
KNOWLEDGE_STORE_ROOT = CER_ARTIFACTS_ROOT / "knowledge_store"
MACHINE_ASSETS_ROOT = KNOWLEDGE_STORE_ROOT / "machine_assets"
HUMAN_CARDS_ROOT = KNOWLEDGE_STORE_ROOT / "human"

OBSIDIAN_VAULT_ROOT = Path("/Users/winstonwei/CER-RAG/🔋CER项目/04_KNOWLEDGE_CARDS")
OBSIDIAN_KNOWLEDGE_CARDS = OBSIDIAN_VAULT_ROOT

SQLITE_DB_PATH = KNOWLEDGE_STORE_ROOT / "cer_knowledge.db"
PUBLICATION_OUTPUT_ROOT = CER_ARTIFACTS_ROOT / "knowledge_publication"

# ── Asset type → Obsidian folder mapping ─────────────────────────────────────

OBSIDIAN_FOLDER_MAP: dict[str, str] = {
    "TerminologyUnit": "rules",
    "EvidenceRequirement": "rules",
    "ChecklistUnit": "rules",
    "RuleUnit": "rules",
    "CaseLesson": "cases",
    "FailurePattern": "errors",
    "CrossDocumentMapping": "Cross_Document",
    "MethodUnit": "CER",
    "BoundaryCondition": "CER",
    "ReviewHeuristic": "CER",
    "WorkflowImprovement": "Workflow_Improvements",
}

# ── SQLite DB Setup ───────────────────────────────────────────────────────────

def _get_sqlite_conn() -> sqlite3.Connection:
    """Get SQLite connection (creates DB + tables if not exist)."""
    PUBLICATION_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_sqlite_schema(conn)
    return conn


def _init_sqlite_schema(conn: sqlite3.Connection) -> None:
    """Create tables if not exist."""
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


# ── Obsidian helpers ─────────────────────────────────────────────────────────

def _ensure_obsidian_folders() -> list[str]:
    """Ensure required Obsidian subfolders exist. Returns list of created paths."""
    created = []
    required_folders = [
        OBSIDIAN_KNOWLEDGE_CARDS / "CER",
        OBSIDIAN_KNOWLEDGE_CARDS / "RMF",
        OBSIDIAN_KNOWLEDGE_CARDS / "Cross_Document",
        OBSIDIAN_KNOWLEDGE_CARDS / "Workflow_Improvements",
        OBSIDIAN_KNOWLEDGE_CARDS / "cases",
        OBSIDIAN_KNOWLEDGE_CARDS / "errors",
        OBSIDIAN_KNOWLEDGE_CARDS / "rules",
    ]
    for folder in required_folders:
        folder.mkdir(parents=True, exist_ok=True)
        created.append(str(folder))
    return created


def _get_obsidian_folder(asset_type: str) -> Path:
    """Get Obsidian target folder for an asset type."""
    folder_name = OBSIDIAN_FOLDER_MAP.get(asset_type, "CER")
    return OBSIDIAN_KNOWLEDGE_CARDS / folder_name


# ── Machine asset → SQLite ───────────────────────────────────────────────────

def _machine_asset_to_db_record(asset_data: dict[str, Any]) -> dict[str, Any]:
    """Convert machine asset JSON to SQLite record."""
    payload = asset_data.get("payload", {})
    metadata = asset_data.get("metadata", {})

    # Build source_excerpt from payload
    source_excerpt = None
    if isinstance(payload, dict):
        if "definition" in payload:
            source_excerpt = payload.get("definition")
        elif "description" in payload:
            source_excerpt = payload.get("description")
        elif "term" in payload:
            source_excerpt = f"{payload.get('term')}: {payload.get('definition', '')}"

    return {
        "asset_id": asset_data.get("asset_id"),
        "asset_type": asset_data.get("asset_type"),
        "title": payload.get("title") if isinstance(payload, dict) else None,
        "summary": payload.get("description") if isinstance(payload, dict) else None,
        "regulatory_context": payload.get("regulatory_context") if isinstance(payload, dict) else None,
        "source_project_id": asset_data.get("project_id"),
        "source_run_id": asset_data.get("integration_run_id") or metadata.get("integration_run_id"),
        "source_artifact_path": asset_data.get("source_artifact"),
        "source_excerpt": source_excerpt,
        "applicability_boundary": payload.get("applicability_boundary") if isinstance(payload, dict) else None,
        "generalizability_level": payload.get("generalizability_level") if isinstance(payload, dict) else None,
        "confidence": asset_data.get("confidence"),
        "status": asset_data.get("state"),
        "approved_by": metadata.get("reviewed_by"),
        "approved_at": metadata.get("reviewed_at"),
        "created_at": metadata.get("extracted_at"),
        "updated_at": metadata.get("published_at"),
    }


# ── Markdown frontmatter builder ──────────────────────────────────────────────

def _build_obsidian_frontmatter(asset_data: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    """Build Obsidian-compatible frontmatter with all required fields."""
    payload = asset_data.get("payload", {})

    # Build source_excerpt from payload
    source_excerpt = None
    if isinstance(payload, dict):
        if "definition" in payload:
            source_excerpt = f"{payload.get('term', '')}: {payload.get('definition', '')}"
        elif "description" in payload:
            source_excerpt = payload.get("description")
        elif "rule_text" in payload:
            source_excerpt = payload.get("rule_text", "")[:200]

    fm = {
        "id": asset_data.get("asset_id"),
        "asset_id": asset_data.get("asset_id"),
        "asset_type": asset_data.get("asset_type"),
        "status": asset_data.get("state"),
        "source_project_id": asset_data.get("project_id"),
        "source_run_id": metadata.get("integration_run_id"),
        "source_artifact_path": asset_data.get("source_artifact"),
        "source_excerpt": source_excerpt,
        "regulatory_context": payload.get("regulatory_context", "MDR_EU") if isinstance(payload, dict) else "MDR_EU",
        "applicability_boundary": payload.get("applicability_boundary") if isinstance(payload, dict) else None,
        "generalizability_level": payload.get("generalizability_level") if isinstance(payload, dict) else "project_specific",
        "human_review_status": metadata.get("review_decision", "").lower(),
        "machine_asset_id": asset_data.get("asset_id"),
        "created_at": metadata.get("extracted_at"),
        "updated_at": metadata.get("published_at"),
    }
    # Remove None values for cleanliness
    return {k: v for k, v in fm.items() if v is not None}


def _build_obsidian_content(asset_data: dict[str, Any], frontmatter: dict[str, Any]) -> str:
    """Build Obsidian markdown content from machine asset."""
    payload = asset_data.get("payload", {})
    metadata = asset_data.get("metadata", {})

    lines = [
        f"# {asset_data.get('asset_type', 'Unknown')}: {asset_data.get('asset_id', 'N/A')}",
        "",
    ]

    # Add payload fields
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key not in ("regulatory_context", "applicability_boundary", "generalizability_level"):
                lines.append(f"**{key}:** {value}")
        lines.append("")

    # Review info
    lines.append("## Review")
    lines.append(f"- **Decision:** {metadata.get('review_decision', 'N/A')}")
    lines.append(f"- **Reviewer:** {metadata.get('reviewed_by', 'N/A')}")
    lines.append(f"- **Reviewed:** {metadata.get('reviewed_at', 'N/A')}")
    if metadata.get("review_notes"):
        lines.append(f"- **Notes:** {metadata['review_notes']}")
    lines.append("")

    # Source
    lines.append("## Source")
    lines.append(f"- Project: {asset_data.get('project_id', 'N/A')}")
    lines.append(f"- Artifact: {asset_data.get('source_artifact', 'N/A')}")
    lines.append("")

    lines.append("---")
    lines.append(f"_Extracted: {metadata.get('extracted_at', 'N/A')}_")
    if metadata.get("published_at"):
        lines.append(f"_Published: {metadata['published_at']}_")

    return "\n".join(lines)


# ── Core sync functions ─────────────────────────────────────────────────────

def sync_knowledge_to_obsidian(project_id: str) -> dict[str, Any]:
    """Sync approved knowledge assets to Obsidian Vault.

    Args:
        project_id: Project identifier

    Returns:
        Dict with counts and manifest of published files
    """
    _ensure_obsidian_folders()

    machine_root = MACHINE_ASSETS_ROOT
    obsidian_manifest: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    published_count = 0

    for asset_type_folder in machine_root.iterdir():
        if not asset_type_folder.is_dir():
            continue
        project_folder = asset_type_folder / project_id
        if not project_folder.exists():
            continue

        for json_file in project_folder.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    asset_data = json.load(f)

                # Only publish APPROVED assets
                state = asset_data.get("state", "")
                if state not in ("approved", "published"):
                    continue

                metadata = asset_data.get("metadata", {})
                review_decision = metadata.get("review_decision", "").upper()
                if review_decision not in ("APPROVE", "APPROVED"):
                    continue

                asset_id = asset_data.get("asset_id")
                asset_type = asset_data.get("asset_type")
                target_folder = _get_obsidian_folder(asset_type)
                target_file = target_folder / f"{asset_id}.md"

                # Idempotency: only write if newer
                should_write = True
                if target_file.exists():
                    existing = yaml.safe_load(open(target_file, encoding="utf-8"))
                    existing_updated = existing.get("updated_at", "")
                    new_updated = metadata.get("published_at", "")
                    if existing_updated >= new_updated:
                        should_write = False

                if should_write:
                    frontmatter = _build_obsidian_frontmatter(asset_data, metadata)
                    content = _build_obsidian_content(asset_data, frontmatter)

                    # Atomic write
                    tmp = target_file.with_suffix(".tmp")
                    with open(tmp, "w", encoding="utf-8") as f:
                        f.write("---\n")
                        yaml.dump(frontmatter, f, allow_unicode=True, sort_keys=False)
                        f.write("---\n\n")
                        f.write(content)
                    tmp.replace(target_file)

                    obsidian_manifest.append({
                        "asset_id": asset_id,
                        "asset_type": asset_type,
                        "target_path": str(target_file),
                        "status": "published",
                    })
                    published_count += 1
                else:
                    obsidian_manifest.append({
                        "asset_id": asset_id,
                        "asset_type": asset_type,
                        "target_path": str(target_file),
                        "status": "skipped_existing_newer",
                    })
                    published_count += 1

            except Exception as e:
                errors.append({"file": str(json_file), "error": str(e)})
                logger.error(f"Error publishing {json_file} to Obsidian: {e}")

    return {
        "published_count": published_count,
        "obsidian_manifest": obsidian_manifest,
        "errors": errors,
        "vault_root": str(OBSIDIAN_VAULT_ROOT),
    }


def sync_knowledge_to_db(project_id: str) -> dict[str, Any]:
    """Sync approved knowledge assets to SQLite DB.

    Args:
        project_id: Project identifier

    Returns:
        Dict with counts and manifest of DB records
    """
    conn = _get_sqlite_conn()
    machine_root = MACHINE_ASSETS_ROOT
    db_manifest: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    published_count = 0

    for asset_type_folder in machine_root.iterdir():
        if not asset_type_folder.is_dir():
            continue
        project_folder = asset_type_folder / project_id
        if not project_folder.exists():
            continue

        for json_file in project_folder.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    asset_data = json.load(f)

                # Only publish APPROVED assets
                metadata = asset_data.get("metadata", {})
                review_decision = metadata.get("review_decision", "").upper()
                if review_decision not in ("APPROVE", "APPROVED"):
                    continue

                asset_id = asset_data.get("asset_id")
                record = _machine_asset_to_db_record(asset_data)

                # Upsert knowledge_assets
                conn.execute("""
                    INSERT OR REPLACE INTO knowledge_assets
                    (asset_id, asset_type, title, summary, regulatory_context,
                     source_project_id, source_run_id, source_artifact_path,
                     source_excerpt, applicability_boundary, generalizability_level,
                     confidence, status, approved_by, approved_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record["asset_id"], record["asset_type"], record["title"],
                    record["summary"], record["regulatory_context"],
                    record["source_project_id"], record["source_run_id"],
                    record["source_artifact_path"], record["source_excerpt"],
                    record["applicability_boundary"], record["generalizability_level"],
                    record["confidence"], record["status"], record["approved_by"],
                    record["approved_at"], record["created_at"], record["updated_at"],
                ))

                # Record the review decision
                decision_id = f"KRD-{uuid.uuid4().hex[:12]}"
                conn.execute("""
                    INSERT OR REPLACE INTO knowledge_review_decisions
                    (id, asset_id, project_id, decision, notes, decided_by, decided_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    decision_id, asset_id, project_id,
                    metadata.get("review_decision", "APPROVED"),
                    metadata.get("review_notes"),
                    metadata.get("reviewed_by"),
                    metadata.get("reviewed_at"),
                ))

                conn.commit()
                db_manifest.append({
                    "asset_id": asset_id,
                    "asset_type": asset_data.get("asset_type"),
                    "status": "published",
                })
                published_count += 1

            except Exception as e:
                errors.append({"file": str(json_file), "error": str(e)})
                logger.error(f"Error publishing {json_file} to DB: {e}")

    conn.close()
    return {
        "published_count": published_count,
        "db_manifest": db_manifest,
        "errors": errors,
        "db_path": str(SQLITE_DB_PATH),
    }


def publish_knowledge_assets(project_id: str) -> dict[str, Any]:
    """Full publication pipeline: Obsidian + NocoDB/SQLite.

    Binding decision is delegated to cer_nocodb_binding.get_binding_status():
    - NOCODB_ACTIVE: write to NocoDB via sync_to_nocodb()
    - SQLITE_FALLBACK_ACTIVE: write to SQLite via sync_knowledge_to_db()
    - DB_UNAVAILABLE: log warning, skip DB write

    Args:
        project_id: Project identifier

    Returns:
        Combined manifest from both containers
    """
    PUBLICATION_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    obsidian_result = sync_knowledge_to_obsidian(project_id)

    # Delegate DB binding decision to cer_nocodb_binding
    binding_status = get_binding_status()

    if binding_status == DBBindingStatus.NOCODB_ACTIVE:
        db_result = nocodb_sync_to_nocodb(project_id)
    elif binding_status == DBBindingStatus.SQLITE_FALLBACK_ACTIVE:
        db_result = sync_knowledge_to_db(project_id)
    else:
        # DB_UNAVAILABLE — log warning and continue with empty result
        logger.warning(
            "publish_knowledge_assets: DB unavailable (binding_status=%s). "
            "Skipping DB write for project_id=%s",
            binding_status,
            project_id,
        )
        db_result = {
            "published_count": 0,
            "binding_status": binding_status,
            "nocodb_active": False,
            "errors": [{"error": "DB unavailable, write skipped"}],
        }

    now = datetime.now(timezone.utc).isoformat()

    # Build combined manifest
    combined_manifest = {
        "project_id": project_id,
        "published_at": now,
        "obsidian": obsidian_result,
        "machine_db": db_result,
        "machine_db_binding": binding_status,
    }

    # Write manifests
    obsidian_manifest_file = PUBLICATION_OUTPUT_ROOT / "obsidian_publication_manifest.json"
    machine_db_manifest_file = PUBLICATION_OUTPUT_ROOT / "machine_db_publication_manifest.json"

    obsidian_manifest_file.write_text(
        json.dumps({"project_id": project_id, "published_at": now, **obsidian_result}, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    machine_db_manifest_file.write_text(
        json.dumps({"project_id": project_id, "published_at": now, **db_result}, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Append to log
    log_file = PUBLICATION_OUTPUT_ROOT / "publication_log.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now, "project_id": project_id, "action": "publish", "result": {
            "obsidian_count": obsidian_result["published_count"],
            "db_count": db_result["published_count"],
        }}, ensure_ascii=False) + "\n")

    # Write errors
    all_errors = (obsidian_result.get("errors", []) or []) + (db_result.get("errors", []) or [])
    if all_errors:
        errors_file = PUBLICATION_OUTPUT_ROOT / "publication_errors.json"
        errors_file.write_text(json.dumps({"project_id": project_id, "errors": all_errors}, indent=2, ensure_ascii=False), encoding="utf-8")

    return combined_manifest


# ── Readback ───────────────────────────────────────────────────────────────

def query_approved_asset(asset_id: str) -> dict[str, Any] | None:
    """Query one approved knowledge asset from SQLite.

    Args:
        asset_id: Knowledge asset ID

    Returns:
        Asset record or None if not found / not approved
    """
    try:
        conn = _get_sqlite_conn()
        row = conn.execute(
            "SELECT * FROM knowledge_assets WHERE asset_id = ? AND status IN ('approved', 'published')",
            (asset_id,)
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Error querying asset {asset_id}: {e}")
        return None


def query_approved_assets_by_type(asset_type: str) -> list[dict[str, Any]]:
    """Query all approved knowledge assets of a given type.

    Args:
        asset_type: Asset type (e.g. 'TerminologyUnit')

    Returns:
        List of approved asset records
    """
    try:
        conn = _get_sqlite_conn()
        rows = conn.execute(
            "SELECT * FROM knowledge_assets WHERE asset_type = ? AND status IN ('approved', 'published') ORDER BY confidence DESC",
            (asset_type,)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error querying assets by type {asset_type}: {e}")
        return []


def readback_smoke_test() -> dict[str, Any]:
    """Smoke test: read back at least one approved asset from SQLite.

    Returns:
        Test result with asset data if found
    """
    try:
        conn = _get_sqlite_conn()
        row = conn.execute(
            "SELECT * FROM knowledge_assets WHERE status IN ('approved', 'published') LIMIT 1"
        ).fetchone()
        conn.close()

        if row:
            asset = dict(row)
            return {
                "passed": True,
                "asset_id": asset.get("asset_id"),
                "asset_type": asset.get("asset_type"),
                "source_project_id": asset.get("source_project_id"),
                "status": asset.get("status"),
                "message": "Readback smoke test PASSED",
            }
        else:
            return {
                "passed": False,
                "message": "No approved assets found in DB",
            }
    except Exception as e:
        return {
            "passed": False,
            "message": f"Readback smoke test FAILED: {e}",
        }
