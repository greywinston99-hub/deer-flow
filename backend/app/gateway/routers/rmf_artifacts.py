"""RMF Artifact Read API.

Provides artifact read endpoints for inline preview:
  - GET /api/rmf/projects/{id}/artifacts/latest/{path*}  -> latest cycle artifact
  - GET /api/rmf/projects/{id}/artifacts/{cycle_id}/{path*} -> specific cycle artifact

Supports: .md (text/markdown), .json (application/json), .txt (text/plain)
"""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response

from deerflow.runtime.rmf_review import RMFProjectStore

router = APIRouter(prefix="/api/rmf/projects", tags=["rmf-artifacts"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store() -> RMFProjectStore:
    return RMFProjectStore()


def _resolve_artifact_path(
    project_id: str,
    cycle_id: str | None,
    path: str,
) -> tuple[Path, str]:
    """Resolve artifact path. Returns (full_path, content_type).

    Args:
        project_id: Project ID
        cycle_id: Cycle ID (None = use latest)
        path: Relative artifact path (e.g. "06_final/final_report.md")

    Returns:
        (resolved_path, content_type)
    """
    store = _store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Find the cycle
    if cycle_id:
        target_cycle = next((c for c in project.review_cycles if c.cycle_id == cycle_id), None)
        if target_cycle is None:
            raise HTTPException(status_code=404, detail=f"Cycle {cycle_id} not found")
    else:
        # Use latest completed cycle
        completed = [c for c in project.review_cycles if c.status == "completed"]
        if not completed:
            # Fall back to any cycle with a run_id
            with_runs = [c for c in project.review_cycles if c.run_id]
            if not with_runs:
                raise HTTPException(status_code=404, detail="No cycles with runs found")
            target_cycle = sorted(with_runs, key=lambda c: c.cycle_number, reverse=True)[0]
        else:
            target_cycle = sorted(completed, key=lambda c: c.cycle_number, reverse=True)[0]

    if not target_cycle.run_id:
        raise HTTPException(status_code=404, detail=f"Cycle {target_cycle.cycle_id} has no run_id")

    from deerflow.config.paths import get_paths
    paths = get_paths()
    artifact_dir = paths.sandbox_outputs_dir(target_cycle.thread_id) / "rmf_review_v1_1" / target_cycle.run_id / "artifacts"
    full_path = artifact_dir / path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Artifact not found: {path}")

    # Determine content type
    suffix = full_path.suffix.lower()
    if suffix == ".md":
        content_type = "text/markdown"
    elif suffix == ".json":
        content_type = "application/json"
    elif suffix == ".txt":
        content_type = "text/plain"
    elif suffix in (".html", ".xhtml"):
        content_type = "text/html"
    else:
        content_type = "text/plain"

    return full_path, content_type


def _read_artifact_content(full_path: Path, content_type: str) -> str | dict:
    """Read artifact content, parsed for JSON."""
    if content_type == "application/json":
        return json.loads(full_path.read_text())
    return full_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Routes: latest cycle artifact
# ---------------------------------------------------------------------------

@router.get("/{project_id}/artifacts/latest/{path:path}")
async def read_latest_artifact(
    project_id: str,
    path: str,
    raw: bool = Query(False, alias="raw"),
    summary: bool = Query(False, alias="summary"),
) -> Response:
    """Read artifact from the latest completed cycle.

    Use ?raw=true to return raw text for JSON (no formatting).
    Use ?summary=true to return a key-field summary for JSON artifacts.
    """
    try:
        full_path, content_type = _resolve_artifact_path(project_id, None, path)
    except HTTPException:
        raise

    data = _read_artifact_content(full_path, content_type)

    if raw or content_type != "application/json":
        text = data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False)
        return PlainTextResponse(content=text, media_type=content_type)

    # Summary mode — extract key fields
    if summary and isinstance(data, dict):
        return _build_artifact_summary(full_path.name, data)

    # Full JSON
    if isinstance(data, dict):
        return Response(
            content=json.dumps(data, indent=2, ensure_ascii=False),
            media_type="application/json",
        )

    return PlainTextResponse(content=str(data), media_type="text/plain")


def _build_artifact_summary(filename: str, data: dict) -> Response:
    """Build key-field summary for known artifact types."""
    if filename == "final_report.json":
        return Response(
            content=json.dumps({
                "recommended_gate": data.get("recommended_gate"),
                "overall_risk_level": data.get("overall_risk_level"),
                "items_reviewed": data.get("items_reviewed"),
                "items_passed": data.get("items_passed"),
                "items_rejected": data.get("items_rejected"),
                "blocking_items": data.get("blocking_items", []),
                "capa_count": data.get("capa_count"),
                "backflow_candidates": data.get("backflow_candidates", []),
                "executive_summary": data.get("executive_summary"),
                "key_findings": data.get("key_findings", []),
                "critical_issues": data.get("critical_issues", []),
            }, indent=2, ensure_ascii=False),
            media_type="application/json",
        )

    if filename == "gate_closure_report.json":
        return Response(
            content=json.dumps({
                "final_decision": data.get("final_decision"),
                "decision_rationale": data.get("decision_rationale"),
                "conditions": data.get("conditions", []),
                "next_steps": data.get("next_steps", []),
                "sign_off_required": data.get("sign_off_required"),
                "closure_date": data.get("closure_date"),
            }, indent=2, ensure_ascii=False),
            media_type="application/json",
        )

    if filename == "next_action_packet.json":
        return Response(
            content=json.dumps({
                "packet_type": data.get("packet_type"),
                "priority": data.get("priority"),
                "actions": data.get("actions", []),
                "responsible_parties": data.get("responsible_parties", []),
                "due_date": data.get("due_date"),
                "status": data.get("status"),
            }, indent=2, ensure_ascii=False),
            media_type="application/json",
        )

    if filename == "human_review_queue.json":
        return Response(
            content=json.dumps({
                "total_items": data.get("total_items"),
                "high_priority": data.get("high_priority"),
                "medium_priority": data.get("medium_priority"),
                "low_priority": data.get("low_priority"),
                "items": data.get("items", [])[:10],
            }, indent=2, ensure_ascii=False),
            media_type="application/json",
        )

    if filename == "capa_action_list.json":
        return Response(
            content=json.dumps({
                "total_capas": data.get("total_capas"),
                "open": data.get("open", []),
                "in_progress": data.get("in_progress", []),
                "closed": data.get("closed", []),
            }, indent=2, ensure_ascii=False),
            media_type="application/json",
        )

    # Generic summary
    summary = {}
    for k, v in data.items():
        if isinstance(v, (str, int, float, bool)):
            summary[k] = v
        elif isinstance(v, list):
            summary[k] = f"[{len(v)} items]"
        elif isinstance(v, dict):
            summary[k] = f"{{{len(v)} fields}}"
    return Response(content=json.dumps(summary, indent=2, ensure_ascii=False), media_type="application/json")


# ---------------------------------------------------------------------------
# Routes: specific cycle artifact
# ---------------------------------------------------------------------------

@router.get("/{project_id}/artifacts/{cycle_id}/{path:path}")
async def read_cycle_artifact(
    project_id: str,
    cycle_id: str,
    path: str,
    raw: bool = Query(False, alias="raw"),
) -> Response:
    """Read artifact from a specific cycle."""
    try:
        full_path, content_type = _resolve_artifact_path(project_id, cycle_id, path)
    except HTTPException:
        raise

    data = _read_artifact_content(full_path, content_type)

    if raw or content_type != "application/json":
        text = data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False)
        return PlainTextResponse(content=text, media_type=content_type)

    if isinstance(data, dict):
        return Response(
            content=json.dumps(data, indent=2, ensure_ascii=False),
            media_type="application/json",
        )

    return PlainTextResponse(content=str(data), media_type="text/plain")
