"""Evidence persistence helper for CER/RMF review runs.

Package 2 — copies run artifacts from the live artifact root to a fixed
evidence directory, generates an ``evidence_manifest.json``, a command log,
and a source artifact index.  It also enforces the acceptance-vs-diagnostic
classification rules so that contaminated runs can never be mislabeled as
acceptance evidence.

Usage (direct call)::

    from deerflow.runtime.evidence_persistence import persist_evidence

    result = persist_evidence(
        artifact_root=Path("/tmp/cer_review/run-20260426-001"),
        evidence_dir=Path("artifacts/cer_rmf_review_engine/evidence"),
        run_id="run-20260426-001",
        review_type="CER",
        mode="smoke",
        command_used="python scripts/cer_review_runner.py --mode smoke",
        severity_bypass_applied=False,
        monkey_patch_applied=False,
        schema_validated=True,
        agent_trace_available=True,
        llm_provider_available=True,
    )
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── classification ────────────────────────────────────────────────────────────


def classify_acceptance(
    *,
    severity_bypass_applied: bool,
    monkey_patch_applied: bool,
    schema_validated: bool | str,
    agent_trace_available: bool | str,
    trace_file_exists: bool,
    mode: str,
    findings_non_empty: bool,
) -> tuple[str, str | None]:
    """Determine whether a run qualifies as *acceptance* evidence.

    Returns ``(acceptance_type, not_acceptable_reason)``.  ``reason`` is
    ``None`` only when the classification is ``"acceptance"``.
    """
    reasons: list[str] = []

    if severity_bypass_applied:
        reasons.append("severity_bypass_applied=true")
    if monkey_patch_applied:
        reasons.append("monkey_patch_applied=true")
    if schema_validated is False:
        reasons.append("schema_validated=false")
    if agent_trace_available is False:
        reasons.append("agent_trace_available=false")
    if not trace_file_exists:
        reasons.append("agent_invocation_trace.jsonl missing from artifact root")
    if mode == "diagnostic":
        reasons.append("mode=diagnostic")
    if not findings_non_empty:
        reasons.append("findings_non_empty=false (empty or missing findings)")

    if reasons:
        return ("diagnostic", "; ".join(reasons))
    return ("acceptance", None)


# ── file manifest ─────────────────────────────────────────────────────────────


@dataclass
class _SourceItem:
    source: str  # relative path inside artifact root
    dest: str  # relative path inside evidence run dir
    required: bool = False
    rename_hint: str | None = None  # renamed copy (e.g. halt → human_gate_status)


MANIFEST_FILES: list[_SourceItem] = [
    _SourceItem("00_manifest/agent_invocation_trace.jsonl", "agent_invocation_trace.jsonl", required=True),
    _SourceItem("00_manifest/agent_usage_ledger.json", "agent_usage_ledger.json"),
    _SourceItem("00_manifest/event_log.json", "event_log.json"),
    _SourceItem("00_manifest/task_ledger.json", "task_ledger.json"),
    _SourceItem("00_manifest/run_manifest.json", "run_manifest.json"),
    _SourceItem("00_manifest/run_summary.json", "run_summary.json"),
    _SourceItem("00_manifest/schema_validation_summary.json", "schema_validation_summary.json"),
    _SourceItem("00_manifest/human_adjudication_halt.json", "human_gate_status.json", rename_hint="human_adjudication_halt.json"),
    _SourceItem("human_gate_decision.json", "human_gate_decision.json"),
    _SourceItem("gate_closure.json", "gate_closure_report.json"),
    _SourceItem("05_human_boundary/gate_closure_report.json", "gate_closure_report.json"),
]


# ── persist ───────────────────────────────────────────────────────────────────


def persist_evidence(
    *,
    artifact_root: Path,
    evidence_dir: Path,
    run_id: str,
    review_type: str,
    mode: str,
    command_used: str,
    severity_bypass_applied: bool = False,
    monkey_patch_applied: bool = False,
    schema_validated: bool | str = True,
    agent_trace_available: bool | str = True,
    llm_provider_available: bool | str = True,
    workflow_id: str = "",
    project_id: str = "",
    notes: str = "",
    findings_non_empty: bool = True,
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Copy run artifacts into a fixed evidence directory and produce a manifest.

    Parameters
    ----------
    artifact_root:
        The live artifact directory produced by the review runner (contains
        ``00_manifest/`` and step sub-directories).
    evidence_dir:
        The parent evidence directory (e.g.
        ``artifacts/cer_rmf_review_engine/evidence``).  A sub-directory named
        ``run_id`` will be created inside it.
    run_id:
        Unique identifier for this run (directory-safe string).
    review_type:
        ``"CER"`` or ``"RMF"``.
    mode:
        ``"smoke"``, ``"closure-only"``, ``"resume"``, ``"diagnostic"``, or
        ``"acceptance"``.
    command_used:
        The exact command-line or script invocation that produced this run.
    severity_bypass_applied:
        ``True`` when ``--no-severity-scan`` or equivalent was used.
    monkey_patch_applied:
        ``True`` when any runtime monkey-patch was active.
    schema_validated:
        ``True``, ``False``, or ``"partial"``.
    agent_trace_available:
        ``True`` when ``agent_invocation_trace.jsonl`` has at least one live
        trace entry with ``duration_ms > 0``.
    llm_provider_available:
        ``True`` when the LLM was reachable during the run.
    workflow_id:
        Workflow identifier (e.g. ``"cer_review_v2"``).
    project_id:
        Project identifier from the project profile.
    notes:
        Free-form human-readable notes.
    findings_non_empty:
        ``True`` when at least one review artifact has a non-empty
        ``findings`` array.
    dry_run:
        When ``True``, compute the manifest and file list but do not write
        anything to disk.
    overwrite:
        When ``True``, remove an existing evidence directory for the same
        ``run_id`` before writing.  When ``False`` (default), raise
        ``FileExistsError`` if the target directory already exists.

    Returns
    -------
    dict
        A summary dict with keys ``"run_dir"``, ``"acceptance_type"``,
        ``"copied_files"``, ``"missing_files"``, ``"dry_run"`` and, when
        ``dry_run=True``, ``"would_copy"``.
    """
    artifact_root = artifact_root.resolve()
    evidence_dir = evidence_dir.resolve()
    run_dir = evidence_dir / run_id

    # ── overwrite protection ──────────────────────────────────────────────
    if run_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"Evidence directory already exists: {run_dir}. "
                "Use overwrite=True to replace it."
            )
        shutil.rmtree(run_dir)

    # ── collect file status ────────────────────────────────────────────────
    copied: list[str] = []
    missing: list[str] = []
    would_copy: list[dict[str, str]] = []
    trace_file_exists = False

    for item in MANIFEST_FILES:
        src = artifact_root / item.source
        if src.exists():
            copied.append(item.source)
            would_copy.append({"source": item.source, "dest": item.dest})
            if item.source == "00_manifest/agent_invocation_trace.jsonl":
                trace_file_exists = True
                # Verify it has actual content (not just empty)
                try:
                    content = src.read_text(encoding="utf-8").strip()
                    if not content:
                        trace_file_exists = False
                except Exception:
                    trace_file_exists = False
        else:
            missing.append(item.source)
            # Optional files can be missing without error; required files
            # will cause the acceptance_type guard to fire below.

    # ── acceptance classification ──────────────────────────────────────────
    acceptance_type, not_acceptable_reason = classify_acceptance(
        severity_bypass_applied=severity_bypass_applied,
        monkey_patch_applied=monkey_patch_applied,
        schema_validated=schema_validated,
        agent_trace_available=agent_trace_available,
        trace_file_exists=trace_file_exists,
        mode=mode,
        findings_non_empty=findings_non_empty,
    )

    # ── build manifest ─────────────────────────────────────────────────────
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "workflow_id": workflow_id,
        "project_id": project_id,
        "review_type": review_type,
        "mode": mode,
        "acceptance_type": acceptance_type,
        "severity_bypass_applied": severity_bypass_applied,
        "monkey_patch_applied": monkey_patch_applied,
        "schema_validated": schema_validated,
        "agent_trace_available": agent_trace_available,
        "llm_provider_available": llm_provider_available,
        "findings_non_empty": findings_non_empty,
        "evidence_created_at": datetime.now(timezone.utc).isoformat(),
        "command_used": command_used,
        "artifact_root_source": str(artifact_root),
        "evidence_root": str(run_dir),
        "notes": notes,
        "copied_files": copied,
        "missing_files": missing,
    }

    if acceptance_type != "acceptance":
        manifest["not_acceptable_for_full_pass_reason"] = not_acceptable_reason

    result: dict[str, Any] = {
        "run_dir": str(run_dir),
        "acceptance_type": acceptance_type,
        "copied_files": copied,
        "missing_files": missing,
    }

    if dry_run:
        result["dry_run"] = True
        result["would_copy"] = would_copy
        return result

    # ── write files ────────────────────────────────────────────────────────
    run_dir.mkdir(parents=True, exist_ok=False)

    # Copy artifact files
    for item in MANIFEST_FILES:
        src = artifact_root / item.source
        if not src.exists():
            continue
        dest_name = item.dest
        dest = run_dir / dest_name
        shutil.copy2(src, dest)

    # Write manifest
    (run_dir / "evidence_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Write command log
    cmd_log_lines = [
        f"# Evidence persistence command log",
        f"# Run ID: {run_id}",
        f"# Review Type: {review_type}",
        f"# Mode: {mode}",
        f"# Persisted at: {manifest['evidence_created_at']}",
        f"#",
        f"{command_used}",
    ]
    (run_dir / "command_log.txt").write_text("\n".join(cmd_log_lines) + "\n", encoding="utf-8")

    # Write source artifact index
    index_entries: list[dict[str, Any]] = []
    for item in MANIFEST_FILES:
        src = artifact_root / item.source
        status = "copied" if src.exists() else "missing"
        entry: dict[str, Any] = {
            "source": item.source,
            "dest": item.dest,
            "status": status,
        }
        if item.required:
            entry["required"] = True
        if src.exists():
            entry["size_bytes"] = src.stat().st_size
        index_entries.append(entry)

    (run_dir / "source_artifact_index.json").write_text(
        json.dumps({"files": index_entries}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    result["dry_run"] = False
    return result
