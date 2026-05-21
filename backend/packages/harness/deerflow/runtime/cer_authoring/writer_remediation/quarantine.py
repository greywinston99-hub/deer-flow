"""Quarantine routing for gate-failed CER drafts.

When any writer gate returns HARD_FAIL:
1. The CER draft is saved to quarantine/ instead of the output directory.
2. A failed_gate_report.json is generated.
3. The rejection ledger is updated.

CCD | 2026-05-15 | RELEASE_QUARANTINE_POLICY
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def route_to_quarantine(
    output_root: str | Path,
    cer_body_text: str,
    gate_results: dict[str, Any],
    report_id: str = "",
) -> dict[str, Any]:
    """Write gate-failed CER draft to quarantine directory.

    Args:
        output_root: The 02_AI_BASELINE_OUTPUT_FREEZE directory.
        cer_body_text: Full CER markdown text.
        gate_results: Combined gate results from run_all_writer_gates().
        report_id: Optional report identifier for tracking.

    Returns:
        Dict with quarantine_path, failed_gate_report_path, and ledger_path.
    """
    root = Path(output_root)
    quarantine_dir = root / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    device_name = ""
    if gate_results.get("gates", {}).get("gate_1_domain_consistency", {}).get("device_name"):
        device_name = gate_results["gates"]["gate_1_domain_consistency"]["device_name"]

    # Write quarantined CER draft
    quarantined_draft = quarantine_dir / "CER_draft_QUARANTINED.md"
    quarantined_draft.write_text(cer_body_text, encoding="utf-8")

    # Write failed gate report
    failed_gate_report = _build_failed_gate_report(gate_results, report_id, device_name, timestamp)
    report_path = quarantine_dir / f"failed_gate_report_{timestamp}.json"
    report_path.write_text(json.dumps(failed_gate_report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Update rejection ledger
    ledger_path = quarantine_dir / "rejection_ledger.json"
    _update_rejection_ledger(ledger_path, failed_gate_report)

    return {
        "quarantine_dir": str(quarantine_dir),
        "quarantined_draft": str(quarantined_draft),
        "failed_gate_report": str(report_path),
        "rejection_ledger": str(ledger_path),
    }


def write_failed_gate_report(
    quarantine_dir: str | Path,
    gate_results: dict[str, Any],
    report_id: str = "",
    device_name: str = "",
) -> str:
    """Write a standalone failed_gate_report.json to a quarantine directory.

    Returns the path to the written report.
    """
    qdir = Path(quarantine_dir)
    qdir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = _build_failed_gate_report(gate_results, report_id, device_name, timestamp)
    path = qdir / f"failed_gate_report_{timestamp}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def update_rejection_ledger(
    quarantine_dir: str | Path,
    gate_results: dict[str, Any],
    report_id: str = "",
    device_name: str = "",
) -> str:
    """Update the rejection ledger in a quarantine directory.

    Returns the path to the ledger.
    """
    qdir = Path(quarantine_dir)
    qdir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = _build_failed_gate_report(gate_results, report_id, device_name, timestamp)
    ledger_path = qdir / "rejection_ledger.json"
    _update_rejection_ledger(ledger_path, report)
    return str(ledger_path)


# ── Internal helpers ────────────────────────────────────────────────────────


def _build_failed_gate_report(
    gate_results: dict[str, Any],
    report_id: str,
    device_name: str,
    timestamp: str,
) -> dict[str, Any]:
    """Build a structured failed gate report."""
    failing_gates = []
    gates = gate_results.get("gates", {})
    for gate_key, gate in gates.items():
        if gate.get("status") == "HARD_FAIL":
            failing_gates.append({
                "gate_key": gate_key,
                "gate_name": gate.get("gate", gate_key),
                "failure_reason": gate.get("message", ""),
                "findings": gate.get("findings", []),
                "offending_section": _extract_offending_sections(gate.get("findings", [])),
            })

    return {
        "schema_name": "failed_gate_report_v1",
        "report_id": report_id,
        "device_name": device_name,
        "timestamp": timestamp,
        "overall_status": gate_results.get("overall_status", "UNKNOWN"),
        "failing_gates": failing_gates,
        "total_failing_gates": len(failing_gates),
        "gate_summary": {
            gate_key: gate.get("status")
            for gate_key, gate in gates.items()
        },
    }


def _extract_offending_sections(findings: list[dict]) -> list[str]:
    """Extract unique section names from gate findings."""
    sections = set()
    for f in findings:
        sec = f.get("section") or f.get("banned_string") or f.get("phrase") or f.get("term") or f.get("pattern")
        if sec:
            sections.add(str(sec)[:100])
    return sorted(sections)


def _update_rejection_ledger(ledger_path: Path, report: dict[str, Any]) -> None:
    """Append a rejection entry to the ledger JSON file."""
    if ledger_path.exists():
        try:
            existing = json.loads(ledger_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {"entries": []}
    else:
        existing = {"entries": []}

    if not isinstance(existing, dict):
        existing = {"entries": []}

    entry = {
        "report_id": report.get("report_id", ""),
        "device": report.get("device_name", ""),
        "timestamp": report.get("timestamp", ""),
        "failed_gates": [g["gate_key"] for g in report.get("failing_gates", [])],
        "offending_sections": [],
        "reason": "; ".join(
            g.get("failure_reason", "") for g in report.get("failing_gates", [])
        ),
    }
    # Collect all offending sections
    for g in report.get("failing_gates", []):
        entry["offending_sections"].extend(g.get("offending_section", []))

    existing["entries"].append(entry)
    existing["last_updated"] = report.get("timestamp", "")
    existing["total_rejections"] = len(existing["entries"])

    ledger_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
