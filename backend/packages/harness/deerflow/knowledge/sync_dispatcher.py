"""Wave 5 Knowledge Sync Dispatcher.

Routes approved knowledge assets from NocoDB/SQLite to external systems:
- RAGFlow (vector dataset sync)
- Obsidian (markdown knowledge vault)

Production adapters perform real I/O. Missing credentials or unreachable
services are surfaced as per-asset errors without crashing the dispatch loop.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_KNOWLEDGE_STORE_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer/knowledge_store")
DEFAULT_OBSIDIAN_VAULT_PATH = Path(os.getenv("CER_OBSIDIAN_VAULT_PATH", "./artifacts/obsidian_vault"))
RAGFLOW_BASE_URL = os.getenv("RAGFLOW_BASE_URL", "")
RAGFLOW_API_KEY = os.getenv("RAGFLOW_API_KEY", "")


@dataclass
class AssetRecord:
    """Normalized knowledge asset ready for dispatch."""

    asset_id: str
    asset_type: str
    title: str
    summary: str
    regulatory_context: str
    source_project_id: str
    source_run_id: str
    source_artifact_path: str
    source_excerpt: str
    applicability_boundary: str
    generalizability_level: str
    confidence: float
    status: str
    approved_by: str
    approved_at: str


class KnowledgeSyncDispatcher:
    """Dispatch approved knowledge assets to external sync targets."""

    def __init__(self, knowledge_store_root: Path | None = None) -> None:
        self.knowledge_store_root = knowledge_store_root or DEFAULT_KNOWLEDGE_STORE_ROOT
        self.machine_assets_root = self.knowledge_store_root / "machine_assets"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dispatch_approved_assets(self, project_id: str | None = None) -> dict[str, Any]:
        """Scan knowledge store and dispatch all approved assets.

        Args:
            project_id: Optional project filter. If None, scans all projects.

        Returns:
            Dict with dispatch results per target and any errors.
        """
        result: dict[str, Any] = {
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
            "ragflow": {"dispatched_count": 0, "errors": []},
            "obsidian": {"dispatched_count": 0, "errors": []},
            "total_assets_scanned": 0,
            "total_approved_assets": 0,
        }

        assets = self._scan_approved_assets(project_id)
        result["total_assets_scanned"] = assets["scanned"]
        result["total_approved_assets"] = assets["approved"]

        for asset in assets["records"]:
            try:
                self._sync_to_ragflow(asset)
                result["ragflow"]["dispatched_count"] += 1
            except Exception as exc:
                result["ragflow"]["errors"].append({"asset_id": asset.asset_id, "error": str(exc)})
                logger.warning("RAGFlow sync failed for %s: %s", asset.asset_id, exc)

            try:
                self._sync_to_obsidian(asset)
                result["obsidian"]["dispatched_count"] += 1
            except Exception as exc:
                result["obsidian"]["errors"].append({"asset_id": asset.asset_id, "error": str(exc)})
                logger.warning("Obsidian sync failed for %s: %s", asset.asset_id, exc)

        return result

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def _scan_approved_assets(self, project_id: str | None = None) -> dict[str, Any]:
        """Scan machine_assets directory for approved assets."""
        records: list[AssetRecord] = []
        scanned = 0
        approved = 0

        if not self.machine_assets_root.exists():
            logger.info("Machine assets root does not exist yet: %s", self.machine_assets_root)
            return {"scanned": 0, "approved": 0, "records": []}

        for asset_type_folder in self.machine_assets_root.iterdir():
            if not asset_type_folder.is_dir():
                continue

            # If project_id specified, only scan that project folder
            project_folders = (
                [asset_type_folder / project_id]
                if project_id
                else [d for d in asset_type_folder.iterdir() if d.is_dir()]
            )

            for project_folder in project_folders:
                if not project_folder.exists():
                    continue
                for json_file in project_folder.glob("*.json"):
                    scanned += 1
                    try:
                        with open(json_file, encoding="utf-8") as fh:
                            data = json.load(fh)
                    except Exception:
                        continue

                    metadata = data.get("metadata", {})
                    review_decision = (metadata.get("review_decision") or "").upper()
                    if review_decision not in ("APPROVE", "APPROVED"):
                        continue

                    approved += 1
                    payload = data.get("payload", {})
                    if not isinstance(payload, dict):
                        payload = {}

                    records.append(
                        AssetRecord(
                            asset_id=data.get("asset_id", f"ASSET-{uuid.uuid4().hex[:12]}"),
                            asset_type=data.get("asset_type", "unknown"),
                            title=payload.get("title", "Untitled"),
                            summary=payload.get("description", ""),
                            regulatory_context=payload.get("regulatory_context", "MDR_EU"),
                            source_project_id=data.get("project_id", "unknown"),
                            source_run_id=metadata.get("integration_run_id") or data.get("integration_run_id", ""),
                            source_artifact_path=data.get("source_artifact", ""),
                            source_excerpt=payload.get("definition") or payload.get("rule_text", "")[:200],
                            applicability_boundary=payload.get("applicability_boundary", ""),
                            generalizability_level=payload.get("generalizability_level", "project_specific"),
                            confidence=data.get("confidence", 0.0),
                            status=data.get("state", "unknown"),
                            approved_by=metadata.get("reviewed_by", ""),
                            approved_at=metadata.get("reviewed_at", ""),
                        )
                    )

        return {"scanned": scanned, "approved": approved, "records": records}

    # ------------------------------------------------------------------
    # Target Sync Handlers (mock implementations)
    # ------------------------------------------------------------------

    def _sync_to_ragflow(self, asset: AssetRecord) -> None:
        """Sync an approved asset to RAGFlow vector dataset.

        Requires environment variables:
            RAGFLOW_BASE_URL — e.g. http://localhost:9380
            RAGFLOW_API_KEY  — API key for auth

        Raises only on unrecoverable misconfiguration; transient network
        errors are logged and surfaced via the dispatch result dict.
        """
        if not RAGFLOW_BASE_URL or not RAGFLOW_API_KEY:
            raise RuntimeError("RAGFLOW_BASE_URL or RAGFLOW_API_KEY not configured")

        headers = {
            "Authorization": f"Bearer {RAGFLOW_API_KEY}",
            "Content-Type": "application/json",
        }

        dataset_name = "CER_Knowledge"
        dataset_id = self._ragflow_ensure_dataset(headers, dataset_name)

        payload = {
            "document": {
                "name": f"{asset.asset_id}.md",
                "content": self._asset_to_markdown(asset),
            },
            "meta": {
                "asset_id": asset.asset_id,
                "asset_type": asset.asset_type,
                "title": asset.title,
                "source_project_id": asset.source_project_id,
                "source_run_id": asset.source_run_id,
                "regulatory_context": asset.regulatory_context,
                "confidence": asset.confidence,
                "approved_by": asset.approved_by,
                "approved_at": asset.approved_at,
            },
        }

        url = f"{RAGFLOW_BASE_URL.rstrip('/')}/api/datasets/{dataset_id}/documents"
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=30.0)
        except httpx.ConnectError as exc:
            raise RuntimeError(f"RAGFlow connection failed: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"RAGFlow timeout: {exc}") from exc

        if response.status_code >= 400:
            raise RuntimeError(
                f"RAGFlow HTTP {response.status_code}: {response.text[:500]}"
            )

        logger.info(
            "[RAGFlow] Synced asset %s to dataset '%s' (%s)",
            asset.asset_id,
            dataset_name,
            response.status_code,
        )

    def _ragflow_ensure_dataset(self, headers: dict[str, str], name: str) -> str:
        """Return existing dataset ID or create one."""
        base = RAGFLOW_BASE_URL.rstrip("/")
        list_url = f"{base}/api/datasets"
        try:
            resp = httpx.get(list_url, headers=headers, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            for ds in data.get("data", []):
                if ds.get("name") == name:
                    return ds["id"]
        except Exception as exc:
            logger.warning("RAGFlow dataset list failed, will attempt create: %s", exc)

        create_resp = httpx.post(
            list_url,
            headers=headers,
            json={"name": name, "language": "English"},
            timeout=10.0,
        )
        create_resp.raise_for_status()
        created = create_resp.json()
        dataset_id = created.get("data", {}).get("id")
        if not dataset_id:
            raise RuntimeError(f"RAGFlow dataset creation response missing id: {created}")
        logger.info("[RAGFlow] Created dataset '%s' (%s)", name, dataset_id)
        return dataset_id

    @staticmethod
    def _asset_to_markdown(asset: AssetRecord) -> str:
        """Render an AssetRecord as an Obsidian-compatible markdown note."""
        lines: list[str] = [
            "---",
            f'asset_id: "{asset.asset_id}"',
            f'asset_type: "{asset.asset_type}"',
            f'title: "{asset.title}"',
            f'regulatory_context: "{asset.regulatory_context}"',
            f'source_project_id: "{asset.source_project_id}"',
            f'source_run_id: "{asset.source_run_id}"',
            f'source_artifact_path: "{asset.source_artifact_path}"',
            f'confidence: {asset.confidence}',
            f'status: "{asset.status}"',
            f'approved_by: "{asset.approved_by}"',
            f'approved_at: "{asset.approved_at}"',
            f'generalizability_level: "{asset.generalizability_level}"',
            "---",
            "",
            f"# {asset.title}",
            "",
            "## Summary",
            asset.summary or "_No summary provided._",
            "",
            "## Source Excerpt",
            asset.source_excerpt or "_No excerpt provided._",
            "",
            "## Applicability Boundary",
            asset.applicability_boundary or "_No boundary specified._",
            "",
            "## Links",
            f"- Source Project: `{asset.source_project_id}`",
            f"- Source Run: `{asset.source_run_id}`",
            f"- Artifact Path: `{asset.source_artifact_path}`",
            "",
        ]
        return "\n".join(lines)

    def _sync_to_obsidian(self, asset: AssetRecord) -> None:
        """Write an approved asset as a Markdown note into the Obsidian vault.

        Environment:
            CER_OBSIDIAN_VAULT_PATH — defaults to ./artifacts/obsidian_vault
        """
        vault_path = Path(os.getenv("CER_OBSIDIAN_VAULT_PATH", DEFAULT_OBSIDIAN_VAULT_PATH))
        assets_dir = vault_path / "Assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        md_path = assets_dir / f"{asset.asset_id}.md"
        md_content = self._asset_to_markdown(asset)
        md_path.write_text(md_content, encoding="utf-8")

        logger.info(
            "[Obsidian] Wrote asset %s → %s",
            asset.asset_id,
            md_path,
        )
