"""RMF Governance / Audit Export API.

Provides export endpoints for project governance artifacts:
  - GET /api/rmf/projects/{id}/export/summary      -> project overview
  - GET /api/rmf/projects/{id}/export/decisions    -> human decision history
  - GET /api/rmf/projects/{id}/export/gate-history -> gate progression
  - GET /api/rmf/projects/{id}/export/artifacts    -> artifact index

All support ?format=json|markdown
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import Response

from deerflow.runtime.rmf_review import RMFProjectStore

router = APIRouter(prefix="/api/rmf/projects", tags=["rmf-export"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store() -> RMFProjectStore:
    return RMFProjectStore()


def _format_markdown(text: str) -> str:
    """Simple JSON → readable markdown converter for export."""
    return text


def _read_artifact(thread_id: str, run_id: str | None, rel_path: str) -> dict | None:
    """Try to read a JSON artifact. Returns None if not found. Workflow-agnostic."""
    try:
        from deerflow.config.paths import get_paths
        paths = get_paths()
        outputs_dir = paths.sandbox_outputs_dir(thread_id)
        if not outputs_dir.exists():
            return None
        if run_id:
            # Find the run directory by scanning for matching run_id
            artifact_base = None
            for workflow_dir in outputs_dir.iterdir():
                if not workflow_dir.is_dir():
                    continue
                run_dir = workflow_dir / run_id
                if run_dir.is_dir() and (run_dir / "artifacts" / "00_manifest" / "run_summary.json").exists():
                    artifact_base = run_dir / "artifacts"
                    break
            if artifact_base is None:
                return None
        else:
            # Find latest run across all workflows
            all_runs: list[tuple[Path, Path]] = []
            for workflow_dir in outputs_dir.iterdir():
                if not workflow_dir.is_dir():
                    continue
                for run_dir in workflow_dir.iterdir():
                    if not run_dir.is_dir():
                        continue
                    if (run_dir / "artifacts" / "00_manifest" / "run_summary.json").exists():
                        all_runs.append((run_dir, run_dir / "artifacts"))
            if not all_runs:
                return None
            all_runs.sort(key=lambda x: x[0].stat().st_mtime, reverse=True)
            artifact_base = all_runs[0][1]
        full_path = artifact_base / rel_path
        if full_path.exists():
            return json.loads(full_path.read_text())
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Export: Project Summary
# ---------------------------------------------------------------------------

def _build_summary_export(project, store: RMFProjectStore) -> dict:
    """Build a complete project summary export dict."""
    cycles = store.get_cycle_history(project.project_id)
    audit = store.get_audit_trail(project.project_id)

    return {
        "export_type": "project_summary",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": {
            "project_id": project.project_id,
            "project_name": project.project_name,
            "product_name": project.product_name,
            "project_profile_path": project.project_profile_path,
            "input_root": project.input_root,
            "current_status": project.current_status.value,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        },
        "statistics": {
            "total_runs": project.total_runs,
            "total_rework_rounds": project.total_rework_rounds,
            "total_human_decisions": len(audit),
        },
        "latest_state": {
            "latest_thread_id": project.latest_thread_id,
            "latest_run_id": project.latest_run_id,
            "latest_machine_recommendation": project.latest_machine_recommendation,
            "latest_human_decision": project.latest_human_decision,
            "latest_gate_status": project.latest_gate_status,
        },
        "cycles_summary": [
            {
                "cycle_id": c.cycle_id,
                "cycle_number": c.cycle_number,
                "thread_id": c.thread_id,
                "run_id": c.run_id,
                "mode": c.mode,
                "started_at": c.started_at,
                "completed_at": c.completed_at,
                "machine_recommendation": c.machine_recommendation,
                "human_decision": c.human_decision,
                "final_gate": c.final_gate,
                "status": c.status,
            }
            for c in cycles
        ],
    }


def _summary_to_markdown(data: dict) -> str:
    p = data["project"]
    s = data["statistics"]
    ls = data["latest_state"]
    lines = [
        f"# RMF Project Summary: {p['project_name']}",
        "",
        f"**Project ID:** `{p['project_id']}`",
        f"**Product:** {p['product_name']}",
        f"**Status:** `{p['current_status']}`",
        f"**Created:** {p['created_at']}",
        f"**Updated:** {p['updated_at']}",
        "",
        "## Statistics",
        "",
        f"- Total Runs: {s['total_runs']}",
        f"- Total Rework Rounds: {s['total_rework_rounds']}",
        f"- Human Decisions: {s['total_human_decisions']}",
        "",
        "## Latest State",
        "",
        f"- Machine Recommendation: `{ls['latest_machine_recommendation'] or 'N/A'}`",
        f"- Human Decision: `{ls['latest_human_decision'] or 'N/A'}`",
        f"- Final Gate: `{ls['latest_gate_status'] or 'N/A'}`",
        f"- Latest Thread: `{ls['latest_thread_id'] or 'N/A'}`",
        f"- Latest Run: `{ls['latest_run_id'] or 'N/A'}`",
        "",
        "## Cycles",
        "",
    ]
    for c in data["cycles_summary"]:
        lines.append(f"### Round {c['cycle_number']} ({c['cycle_id']})")
        lines.append(f"- Status: `{c['status']}`")
        lines.append(f"- Thread: `{c['thread_id']}`")
        lines.append(f"- Machine Rec: `{c['machine_recommendation'] or 'N/A'}`")
        lines.append(f"- Human Decision: `{c['human_decision'] or 'N/A'}`")
        lines.append(f"- Final Gate: `{c['final_gate'] or 'N/A'}`")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Export: Decision History
# ---------------------------------------------------------------------------

def _build_decisions_export(project, store: RMFProjectStore) -> dict:
    audit = store.get_audit_trail(project.project_id)
    return {
        "export_type": "decision_history",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_id": project.project_id,
        "project_name": project.project_name,
        "total_decisions": len(audit),
        "decisions": [
            {
                "decision_id": a.decision_id,
                "cycle_id": a.source_cycle_id,
                "reviewer": a.reviewer,
                "decision": a.decision,
                "decision_date": a.decision_date,
                "rationale": a.rationale,
                "linked_review_items": a.linked_review_items,
                "linked_capa_ids": a.linked_capa_ids,
                "source_thread_id": a.source_thread_id,
                "source_run_id": a.source_run_id,
            }
            for a in audit
        ],
    }


def _decisions_to_markdown(data: dict) -> str:
    lines = [
        f"# Decision History: {data['project_name']}",
        "",
        f"**Project ID:** `{data['project_id']}`",
        f"**Exported:** {data['exported_at']}",
        f"**Total Decisions:** {data['total_decisions']}",
        "",
    ]
    for d in data["decisions"]:
        lines.append(f"## {d['decision']} by {d['reviewer']} ({d['decision_date']})")
        lines.append(f"**Decision ID:** `{d['decision_id']}`")
        lines.append(f"**Cycle:** {d['cycle_id']}")
        lines.append(f"**Thread:** `{d['source_thread_id']}`")
        lines.append(f"**Run:** `{d['source_run_id']}`")
        if d["rationale"]:
            lines.append(f"**Rationale:** {d['rationale']}")
        if d["linked_review_items"]:
            lines.append(f"**Linked Items:** {', '.join(d['linked_review_items'])}")
        if d["linked_capa_ids"]:
            lines.append(f"**Linked CAPAs:** {', '.join(d['linked_capa_ids'])}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Export: Gate History
# ---------------------------------------------------------------------------

def _build_gate_history_export(project, store: RMFProjectStore) -> dict:
    cycles = store.get_cycle_history(project.project_id)
    return {
        "export_type": "gate_history",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_id": project.project_id,
        "project_name": project.project_name,
        "current_status": project.current_status.value,
        "rounds": [
            {
                "round": c.cycle_number,
                "cycle_id": c.cycle_id,
                "thread_id": c.thread_id,
                "run_id": c.run_id,
                "started_at": c.started_at,
                "completed_at": c.completed_at,
                "machine_recommendation": c.machine_recommendation,
                "human_decision": c.human_decision,
                "final_gate": c.final_gate,
                "status": c.status,
            }
            for c in cycles
        ],
    }


def _gate_history_to_markdown(data: dict) -> str:
    lines = [
        f"# Gate History: {data['project_name']}",
        "",
        f"**Project ID:** `{data['project_id']}`",
        f"**Current Status:** `{data['current_status']}`",
        f"**Exported:** {data['exported_at']}",
        "",
        "| Round | Thread | Machine Rec | Human Decision | Final Gate | Status |",
        "|-------|--------|-------------|----------------|------------|--------|",
    ]
    for r in data["rounds"]:
        lines.append(
            f"| {r['round']} | `{r['thread_id']}` | "
            f"`{r['machine_recommendation'] or 'N/A'}` | "
            f"`{r['human_decision'] or 'N/A'}` | "
            f"`{r['final_gate'] or 'N/A'}` | "
            f"`{r['status']}` |"
        )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Export: Artifact Index
# ---------------------------------------------------------------------------

def _build_artifact_index_export(project, store: RMFProjectStore) -> dict:
    cycles = store.get_cycle_history(project.project_id)
    artifact_index: list[dict[str, Any]] = []

    for c in cycles:
        if not c.run_id:
            continue
        thread_id = c.thread_id
        run_id = c.run_id

        # List all artifacts from the known step directories
        step_artifacts = [
            ("00_manifest", "run_manifest.json"),
            ("00_manifest", "run_summary.json"),
            ("00_manifest", "input_inventory.json"),
            ("00_manifest", "missing_items_report.md"),
            ("01_parse", "project_profile.normalized.json"),
            ("01_parse", "rmf_normalized.json"),
            ("01_parse", "fmea_normalized.json"),
            ("01_parse", "cross_doc_entities.json"),
            ("01_parse", "term_map.json"),
            ("02_fmea_precheck", "fmea_precheck_report.json"),
            ("02_fmea_precheck", "fmea_precheck_report.md"),
            ("03_rmf_precheck", "rmf_precheck_report.json"),
            ("03_rmf_precheck", "rmf_precheck_report.md"),
            ("04_dimension_review", "dimension_assessment.json"),
            ("04_dimension_review", "dimension_review_report.md"),
            ("05_human_boundary", "human_review_queue.json"),
            ("05_human_boundary", "provisional_gate_recommendation.json"),
            ("05_human_boundary", "human_gate_decision.json"),
            ("06_final", "final_report.md"),
            ("06_final", "final_report.json"),
            ("06_final", "capa_action_list.json"),
            ("06_final", "backflow_candidates.json"),
            ("07_gate_closure", "gate_closure_report.md"),
            ("07_gate_closure", "gate_closure_report.json"),
            ("07_gate_closure", "next_action_packet.json"),
        ]

        from deerflow.config.paths import get_paths
        paths = get_paths()
        outputs_dir = paths.sandbox_outputs_dir(thread_id)
        # Workflow-agnostic: find the run directory by scanning for matching run_id
        base = None
        if outputs_dir.exists():
            for workflow_dir in outputs_dir.iterdir():
                if not workflow_dir.is_dir():
                    continue
                run_dir = workflow_dir / run_id
                if run_dir.is_dir() and (run_dir / "artifacts" / "00_manifest" / "run_summary.json").exists():
                    base = run_dir / "artifacts"
                    break
        if base is None:
            continue  # Skip this cycle if run not found

        for step_dir, artifact_name in step_artifacts:
            full_path = base / step_dir / artifact_name
            artifact_index.append({
                "round": c.cycle_number,
                "cycle_id": c.cycle_id,
                "thread_id": thread_id,
                "run_id": run_id,
                "step_dir": step_dir,
                "artifact_name": artifact_name,
                "present": full_path.exists(),
                "path": str(full_path) if full_path.exists() else None,
            })

    return {
        "export_type": "artifact_index",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_id": project.project_id,
        "project_name": project.project_name,
        "total_artifacts": len(artifact_index),
        "present_count": sum(1 for a in artifact_index if a["present"]),
        "artifacts": artifact_index,
    }


def _artifact_index_to_markdown(data: dict) -> str:
    lines = [
        f"# Artifact Index: {data['project_name']}",
        "",
        f"**Project ID:** `{data['project_id']}`",
        f"**Exported:** {data['exported_at']}",
        f"**Total Entries:** {data['total_artifacts']}",
        f"**Present:** {data['present_count']}",
        "",
    ]
    # Group by round
    by_round: dict[int, list] = {}
    for a in data["artifacts"]:
        by_round.setdefault(a["round"], []).append(a)
    for round_num in sorted(by_round.keys()):
        lines.append(f"## Round {round_num}")
        for a in by_round[round_num]:
            step = a["step_dir"]
            name = a["artifact_name"]
            present = "✅" if a["present"] else "❌"
            lines.append(f"- {present} `{step}/{name}`")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/{project_id}/export/summary")
async def export_project_summary(
    project_id: str,
    format: str = Query("json", alias="format", pattern="^(json|markdown)$"),
    x_rmf_role: str | None = Header(None, alias="X-RMF-Role"),
) -> Response:
    """Export project summary in JSON or Markdown format."""
    store = _store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    data = _build_summary_export(project, store)
    if format == "markdown":
        md = _summary_to_markdown(data)
        return Response(content=md, media_type="text/markdown")
    return Response(content=json.dumps(data, indent=2, ensure_ascii=False), media_type="application/json")


@router.get("/{project_id}/export/decisions")
async def export_decisions(
    project_id: str,
    format: str = Query("json", alias="format", pattern="^(json|markdown)$"),
    x_rmf_role: str | None = Header(None, alias="X-RMF-Role"),
) -> Response:
    """Export human decision history in JSON or Markdown format."""
    store = _store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    data = _build_decisions_export(project, store)
    if format == "markdown":
        md = _decisions_to_markdown(data)
        return Response(content=md, media_type="text/markdown")
    return Response(content=json.dumps(data, indent=2, ensure_ascii=False), media_type="application/json")


@router.get("/{project_id}/export/gate-history")
async def export_gate_history(
    project_id: str,
    format: str = Query("json", alias="format", pattern="^(json|markdown)$"),
    x_rmf_role: str | None = Header(None, alias="X-RMF-Role"),
) -> Response:
    """Export gate progression history in JSON or Markdown format."""
    store = _store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    data = _build_gate_history_export(project, store)
    if format == "markdown":
        md = _gate_history_to_markdown(data)
        return Response(content=md, media_type="text/markdown")
    return Response(content=json.dumps(data, indent=2, ensure_ascii=False), media_type="application/json")


@router.get("/{project_id}/export/artifacts")
async def export_artifacts(
    project_id: str,
    format: str = Query("json", alias="format", pattern="^(json|markdown)$"),
    x_rmf_role: str | None = Header(None, alias="X-RMF-Role"),
) -> Response:
    """Export artifact index in JSON or Markdown format."""
    store = _store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    data = _build_artifact_index_export(project, store)
    if format == "markdown":
        md = _artifact_index_to_markdown(data)
        return Response(content=md, media_type="text/markdown")
    return Response(content=json.dumps(data, indent=2, ensure_ascii=False), media_type="application/json")
