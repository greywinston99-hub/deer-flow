"""Shared knowledge assets registry for CER Review and CER Authoring.

This module provides a single source of truth for knowledge assets that are
intentionally shared across the Review and Authoring pipelines. It enforces
version contracts and append-only update policies to prevent cross-pipeline
coupling via mutable shared state.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[5]

# ── Shared Asset Registry ────────────────────────────────────────────────────

SHARED_KNOWLEDGE_ASSETS: dict[str, dict[str, Any]] = {
    "device_knowledge_base": {
        "path": "knowledge/device_knowledge_base.json",
        "owners": ["review", "authoring"],
        "version_field": "metadata.version",
        "update_policy": "append_only",
        "description": "661 NB observations across device types",
    },
    "device_alias_map": {
        "path": "knowledge/device_alias_map.json",
        "owners": ["review", "authoring"],
        "version_field": "version",
        "update_policy": "append_only",
        "description": "Device alias mappings for 9 device types",
    },
    "evidence_depth_schema": {
        "path": "schemas/cer_evidence_depth.schema.json",
        "owners": ["review", "authoring"],
        "version_field": None,
        "update_policy": "immutable",
        "description": "Unified evidence depth taxonomy",
    },
}

# ── Severity caps aligned with Review evidence_depth_policy ──────────────────

EVIDENCE_DEPTH_SEVERITY_CAPS: dict[str, str] = {
    "PRIMARY_VERBATIM": "CRITICAL",
    "PRIMARY_DERIVED": "HIGH",
    "SECONDARY_SUMMARY": "MEDIUM",
    "MISSING_PRIMARY": "LOW",
}

EVIDENCE_DEPTH_LEVELS: list[str] = list(EVIDENCE_DEPTH_SEVERITY_CAPS.keys())


# ── Loaders ──────────────────────────────────────────────────────────────────

def _resolve_path(relative_path: str) -> Path:
    """Resolve a project-relative path to an absolute Path."""
    candidate = _PROJECT_ROOT / relative_path
    if candidate.exists():
        return candidate
    # Fallback: search under backend/packages/harness/ as well
    alt = _PROJECT_ROOT / "backend" / "packages" / "harness" / relative_path
    if alt.exists():
        return alt
    raise FileNotFoundError(f"Shared asset not found: {relative_path}")


def load_shared_asset(asset_id: str) -> dict[str, Any]:
    """Load a shared knowledge asset by its registry ID.

    Returns the parsed JSON content with metadata injected.
    """
    meta = SHARED_KNOWLEDGE_ASSETS.get(asset_id)
    if meta is None:
        raise KeyError(f"Unknown shared asset: {asset_id}. Registered: {list(SHARED_KNOWLEDGE_ASSETS)}")

    path = _resolve_path(meta["path"])
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    # Inject provenance metadata
    data["_shared_asset_meta"] = {
        "asset_id": asset_id,
        "loaded_from": str(path.relative_to(_PROJECT_ROOT)),
        "owners": meta["owners"],
        "update_policy": meta["update_policy"],
    }
    return data


def get_asset_version(asset_id: str, data: dict[str, Any] | None = None) -> str | None:
    """Extract the version string from a loaded asset."""
    meta = SHARED_KNOWLEDGE_ASSETS.get(asset_id)
    if meta is None:
        return None
    version_field = meta.get("version_field")
    if version_field is None:
        return None
    if data is None:
        data = load_shared_asset(asset_id)
    # Support dotted path like "metadata.version"
    node = data
    for part in version_field.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return None
    return str(node) if node is not None else None


def validate_evidence_depth(depth: str, severity: str) -> tuple[bool, str]:
    """Validate that a severity does not exceed the cap for the given evidence depth.

    Returns (is_valid, reason).
    """
    cap = EVIDENCE_DEPTH_SEVERITY_CAPS.get(depth)
    if cap is None:
        return False, f"Unknown evidence_depth: {depth}"

    severity_rank = {"INFORMATIONAL": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    actual = severity_rank.get(severity, -1)
    allowed = severity_rank.get(cap, -1)

    if actual <= allowed:
        return True, f"{severity} within cap {cap} for depth {depth}"
    return False, f"Severity {severity} exceeds cap {cap} for evidence_depth {depth}"
