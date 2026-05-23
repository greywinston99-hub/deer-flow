"""CER Knowledge Assets — Reusable Approved Assets Query.

Provides read-only endpoints for querying approved reusable knowledge assets
from NocoDB or SQLite, with strict anti-pollution filters.

Key constraint: This module is READ-ONLY. It never writes to NocoDB/SQLite,
never creates assets, and never modifies approval status.

Anti-pollution rules enforced at the query level:
  - Only returns status IN ('approved', 'active')
  - Excludes: candidate, human_review_required, rejected, parked, machine_draft
  - Returns [] if no approved/active exist (NO fallback to candidate)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.gateway.routers.cer_nocodb_binding import (
    DBBindingStatus,
    get_binding_status,
    query_approved_reusable_assets,
)
from deerflow.runtime.cer_authoring.evidence_lineage import EvidenceLineageGraph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cer-review", tags=["cer-knowledge-assets"])


# ── Response Models ───────────────────────────────────────────────────────────


class AntiPollutionInfo(BaseModel):
    """Anti-pollution filter metadata embedded in responses."""

    allowed_status: list[str] = Field(
        default=["approved", "active"],
        description="Statuses that are allowed through the filter",
    )
    excluded_status: list[str] = Field(
        default=[
            "candidate",
            "human_review_required",
            "rejected",
            "parked",
            "machine_draft",
        ],
        description="Statuses that are always excluded by the filter",
    )


class ReusableAssetsResponse(BaseModel):
    """Response for reusable assets query."""

    status: str = Field(
        ...,
        description="Response status: 'ok' (NocoDB active), 'degraded' (SQLite fallback), or 'hold' (DB unavailable)",
    )
    assets: list[dict[str, Any]] = Field(
        default=[],
        description="List of approved/active reusable asset records",
    )
    filters_applied: dict[str, Any] = Field(
        default={},
        description="Filters that were applied to this query",
    )
    anti_pollution: AntiPollutionInfo = Field(
        default_factory=AntiPollutionInfo,
        description="Anti-pollution filter metadata",
    )
    source: str = Field(
        ...,
        description="Data source: 'nocodb', 'sqlite', or 'unavailable'",
    )
    warnings: list[str] = Field(
        default=[],
        description="Warning messages, if any",
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.get(
    "/knowledge/assets/reusable",
    response_model=ReusableAssetsResponse,
    summary="Query approved reusable knowledge assets",
    description=(
        "Returns approved/active knowledge assets marked as reusable. "
        "Strictly enforces anti-pollution filters: candidate, human_review_required, "
        "rejected, parked, and machine_draft statuses are always excluded. "
        "This endpoint is READ-ONLY and never writes to NocoDB or SQLite."
    ),
)
async def get_reusable_assets(
    domain: str | None = Query(
        None,
        alias="domain",
        description="Filter by regulatory domain (e.g., 'EU MDR 2017/745')",
    ),
    asset_type: str | None = Query(
        None,
        alias="asset_type",
        description="Filter by asset type (e.g., 'finding_knowledge_card', 'sota_claim')",
    ),
    regulatory_boundary: str | None = Query(
        None,
        alias="regulatory_boundary",
        description="Filter by regulatory boundary",
    ),
    device_category_boundary: str | None = Query(
        None,
        alias="device_category_boundary",
        description="Filter by device category (e.g., 'blood_purification')",
    ),
    notified_body_boundary: str | None = Query(
        None,
        alias="notified_body_boundary",
        description="Filter by notified body (e.g., 'TÜV')",
    ),
    generalizability: str | None = Query(
        None,
        alias="generalizability",
        description="Filter by generalizability level",
    ),
    reusable: bool | None = Query(
        None,
        description="If True, only return assets where reusable=True is set",
    ),
    reuse_allowed: bool | None = Query(
        None,
        description="If True, only return assets where reuse_allowed=True is set",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of records to return (1-1000)",
    ),
) -> ReusableAssetsResponse:
    """Query approved reusable knowledge assets with anti-pollution filters.

    This is a READ-ONLY endpoint. It never:
      - Creates or modifies NocoDB/SQLite records
      - Changes asset status
      - Sets reusable=true or reuse_allowed=true
      - Triggers backflow or approval workflows

    Anti-pollution is enforced at the query layer:
      - Only status IN ('approved', 'active') is ever returned
      - candidate, human_review_required, rejected, parked, machine_draft
        are always excluded, even if they somehow exist in the DB
      - Empty result (no approved/active) returns [] with status="ok", NOT an error
    """
    # Build filters dict for response metadata
    filters_applied: dict[str, Any] = {}
    if domain is not None:
        filters_applied["domain"] = domain
    if asset_type is not None:
        filters_applied["asset_type"] = asset_type
    if regulatory_boundary is not None:
        filters_applied["regulatory_boundary"] = regulatory_boundary
    if device_category_boundary is not None:
        filters_applied["device_category_boundary"] = device_category_boundary
    if notified_body_boundary is not None:
        filters_applied["notified_body_boundary"] = notified_body_boundary
    if generalizability is not None:
        filters_applied["generalizability"] = generalizability
    if reusable is not None:
        filters_applied["reusable"] = reusable
    if reuse_allowed is not None:
        filters_applied["reuse_allowed"] = reuse_allowed
    filters_applied["limit"] = limit

    # Map domain -> regulatory_boundary (semantic alias)
    regulatory = regulatory_boundary or domain

    # Check DB binding status first
    binding_status = get_binding_status()
    source: str
    status_str: str
    warnings: list[str] = []

    if binding_status == DBBindingStatus.DB_UNAVAILABLE:
        source = "unavailable"
        status_str = "hold"
        warnings.append(
            "NocoDB and SQLite are both unavailable. "
            "Cannot query approved reusable assets at this time."
        )
        return ReusableAssetsResponse(
            status=status_str,
            assets=[],
            filters_applied=filters_applied,
            source=source,
            warnings=warnings,
        )

    if binding_status == DBBindingStatus.NOCODB_ACTIVE:
        source = "nocodb"
        status_str = "ok"
    elif binding_status == DBBindingStatus.SQLITE_FALLBACK_ACTIVE:
        source = "sqlite"
        status_str = "degraded"
        warnings.append(
            "Using SQLite fallback. NocoDB is not available. "
            "Query results may be incomplete or stale."
        )
    else:
        source = "unavailable"
        status_str = "hold"
        warnings.append(f"Unknown binding status: {binding_status}")
        return ReusableAssetsResponse(
            status=status_str,
            assets=[],
            filters_applied=filters_applied,
            source=source,
            warnings=warnings,
        )

    # Execute query with anti-pollution filters
    # Note: device_category_boundary maps to device_category param
    #        notified_body_boundary maps to notified_body param
    try:
        assets = query_approved_reusable_assets(
            device_category=device_category_boundary,
            notified_body=notified_body_boundary,
            asset_type=asset_type,
            regulatory_boundary=regulatory,
            generalizability=generalizability,
            reusable=reusable,
            reuse_allowed=reuse_allowed,
            limit=limit,
        )
    except Exception as exc:
        logger.error("get_reusable_assets query failed: %s", exc)
        warnings.append(f"Query error: {exc!s}. Returning empty list.")
        return ReusableAssetsResponse(
            status="hold",
            assets=[],
            filters_applied=filters_applied,
            source=source,
            warnings=warnings,
        )

    # Defensive: double-filter to ensure no polluted statuses slip through
    # (should be impossible given the function's internal filters, but defense-in-depth)
    ALLOWED_STATUSES = {"approved", "active"}
    POLLUTED_STATUSES = {"candidate", "human_review_required", "rejected", "parked", "machine_draft", None}

    clean_assets: list[dict[str, Any]] = []
    for asset in assets:
        asset_status = asset.get("status")
        if asset_status in POLLUTED_STATUSES:
            logger.warning(
                "get_reusable_assets: anti-pollution filter bypass detected! "
                "Asset %s has status=%r (excluded). Dropping.",
                asset.get("asset_id"),
                asset_status,
            )
            continue
        if asset_status in ALLOWED_STATUSES:
            clean_assets.append(asset)

    if len(clean_assets) < len(assets):
        warnings.append(
            f"Anti-pollution: dropped {len(assets) - len(clean_assets)} "
            "assets with excluded statuses (defensive filter)."
        )

    return ReusableAssetsResponse(
        status=status_str,
        assets=clean_assets,
        filters_applied=filters_applied,
        source=source,
        warnings=warnings,
    )


# ── Part 4: Evidence Lineage endpoints ────────────────────────────────────────

@router.get("/lineage/{project_id}")
async def get_evidence_lineage(project_id: str) -> dict[str, Any]:
    """Return evidence lineage graph for a project."""
    from pathlib import Path
    artifact_root = Path("artifacts/cer") / project_id
    db_path = artifact_root / "evidence_lineage.db"
    if not db_path.exists():
        return {"status": "not_found", "project_id": project_id}
    graph = EvidenceLineageGraph(db_path=db_path)
    graph.load(project_id=project_id)
    return graph.export_for_audit()


@router.get("/lineage/{project_id}/breaks")
async def get_evidence_lineage_breaks(project_id: str) -> dict[str, Any]:
    """Return detected chain breaks for a project."""
    from pathlib import Path
    artifact_root = Path("artifacts/cer") / project_id
    db_path = artifact_root / "evidence_lineage.db"
    if not db_path.exists():
        return {"status": "not_found", "project_id": project_id, "breaks": []}
    graph = EvidenceLineageGraph(db_path=db_path)
    graph.load(project_id=project_id)
    return {
        "project_id": project_id,
        "break_count": len(graph.detect_chain_breaks()),
        "breaks": graph.detect_chain_breaks(),
    }
