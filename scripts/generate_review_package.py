#!/usr/bin/env python3
"""Generate human-readable review package Markdown from 3-stage pipeline artifacts.

Reads source_inventory.json, candidate_findings.json, and review_report.json
from a build directory and outputs a formatted Markdown review package suitable
for human expert review.

Usage:
    cd ~/Documents/Playground/deer-flow/backend
    PYTHONPATH=. python ../scripts/generate_review_package.py --project-id 082_tianjinhengyu
    PYTHONPATH=. python ../scripts/generate_review_package.py --project-id 052_zhuhai_jianfan
    PYTHONPATH=. python ../scripts/generate_review_package.py --artifact-dir /path/to/artifacts --output /path/to/output.md
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import os

_CER_RAG_ROOT = Path(os.environ.get("CER_RAG_ROOT", Path.home() / "CER-RAG"))
BUILD_V8 = _CER_RAG_ROOT / "00_knowledge_extraction_build/harness_native_agent_capability_slice/build_v8"
OUTPUT_DIR = BUILD_V8 / "review_packages_v2"
FEEDBACK_DIR = BUILD_V8 / "feedback"

SEVERITY_ICON = {
    "CRITICAL": "🔴 CRITICAL",
    "HIGH": "🟠 HIGH",
    "MEDIUM": "🟡 MEDIUM",
    "LOW": "🟢 LOW",
}

EVIDENCE_DEPTH_LABEL = {
    "PRIMARY": "Primary Source",
    "SECONDARY": "Secondary",
    "TERTIARY": "Tertiary",
    "INDIRECT": "Indirect",
}

EVIDENCE_DEPTH_LABEL_V2 = {
    "PRIMARY_VERBATIM": "Primary Source ✅",
    "PRIMARY_SUMMARY": "Primary Summary 📋",
    "SECONDARY": "Secondary 🔍",
    "INDIRECT": "Indirect ⚠️",
    "SYNTHESIZED": "Synthesized ⚠️",
}

EVIDENCE_CONFIDENCE_LABEL = {
    "PRIMARY_VERBATIM": "PRIMARY_VERBATIM ✅",
    "PRIMARY_SUMMARY": "PRIMARY_SUMMARY 📋",
    "SECONDARY": "SECONDARY 🔍",
    "INDIRECT": "INDIRECT ⚠️",
    "SYNTHESIZED": "SYNTHESIZED ⚠️",
}

DOCUMENT_STATUS_LABEL = {
    "COMPLETE": "✅ 完整",
    "PARTIAL": "⚠️ 部分",
    "PLACEHOLDER": "⚠️ 占位符",
    "EXTRACTION_FAILED": "❌ 提取失败",
    "UNSUPPORTED_FORMAT": "❌ 不支持格式",
    "EMPTY_AFTER_EXTRACTION": "❌ 提取后为空",
    "NOT_REQUIRED": "— 不需要",
}


def _get_severity_icon(finding: dict) -> str:
    """Get severity icon using severity_advisory with fallback to severity."""
    sev = str(finding.get("severity_advisory") or finding.get("severity", "")).upper()
    return SEVERITY_ICON.get(sev, sev)


def _get_document_status(entry: dict) -> str:
    """Get document status label, inferring from flags if missing."""
    status = entry.get("document_status")
    if status:
        return DOCUMENT_STATUS_LABEL.get(status, status)
    # Infer from flags for older schema
    flags = entry.get("flags", [])
    if "empty_file" in flags or "placeholder_content" in flags:
        return DOCUMENT_STATUS_LABEL["PLACEHOLDER"]
    if "truncated_content" in flags:
        return DOCUMENT_STATUS_LABEL["PARTIAL"]
    return DOCUMENT_STATUS_LABEL["COMPLETE"]


def load_artifact(artifact_dir: Path, filename: str) -> dict:
    """Load a JSON artifact file, returning empty dict on failure."""
    path = artifact_dir / filename
    if not path.exists():
        print(f"  WARNING: {filename} not found at {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  WARNING: Could not parse {filename}: {e}")
        return {}


def _count_severity(findings: list[dict]) -> dict[str, int]:
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        sev = str(f.get("severity_advisory") or f.get("calibrated_severity") or f.get("severity", "")).upper()
        if sev in counts:
            counts[sev] += 1
    return counts


def _truncate(text: str, max_len: int = 300) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _render_evidence_block(finding: dict) -> list[str]:
    """Render structured evidence block for a finding (P0-1)."""
    lines = []
    evidence = finding.get("evidence")
    needs_primary = finding.get("needs_primary_source_verification", False)

    if not evidence:
        lines.append("⚠️ MISSING_REQUIRED_FIELD: evidence not available in upstream artifact")
        if needs_primary:
            lines.append("⚠️ NEEDS_PRIMARY_SOURCE_VERIFICATION")
        return lines

    lines.append("**证据 (Evidence):**")
    lines.append("| Source File | Location | Excerpt | Status |")
    lines.append("|------------|----------|---------|--------|")
    for ev in evidence:
        source_file = ev.get("source_file", "?")
        location = ev.get("location", "?")
        excerpt = ev.get("excerpt", "")
        status = ev.get("status", "?")
        lines.append(f'| {source_file} | {location} | "{_truncate(excerpt, 200)}" | {status} |')

    if needs_primary:
        lines.append("⚠️ NEEDS_PRIMARY_SOURCE_VERIFICATION")
    return lines


def _render_severity_line(sig: dict) -> list[str]:
    """Render unified three-field severity (P0-3)."""
    lines = []
    sev_icon = _get_severity_icon(sig)
    blocking = sig.get("blocking_level", "")
    human_gate = sig.get("human_gate_required", False)

    parts = [sev_icon]
    if blocking:
        parts.append(blocking)
    if human_gate:
        parts.append("⚠️ Human Gate Required")

    lines.append(f'- **Severity:** {" | ".join(parts)}')
    return lines


def _render_severity_rationale(finding: dict) -> list[str]:
    """Render severity rationale block for HIGH/CRITICAL (P0-4)."""
    lines = []
    sev = str(finding.get("severity_advisory") or finding.get("severity", "")).upper()
    if sev not in ("CRITICAL", "HIGH"):
        return lines

    rationale = finding.get("severity_rationale")
    if not rationale:
        lines.append("⚠️ MISSING_REQUIRED_FIELD: severity_rationale")
        return lines

    lines.append("**严重度理由 (Severity Rationale):**")
    lines.append(f'- 证据深度: {rationale.get("evidence_depth", "⚠️ NEEDS_PIPELINE_FIX: severity_rationale stage failed to produce this field")}')
    lines.append(f'- 法规依据: {rationale.get("regulatory_basis", "⚠️ NEEDS_PIPELINE_FIX: severity_rationale stage failed to produce this field")}')
    lines.append(f'- 风险影响: {rationale.get("risk_impact", "⚠️ NEEDS_PIPELINE_FIX: severity_rationale stage failed to produce this field")}')
    lines.append(f'- 为何不能更低: {rationale.get("why_not_lower", "⚠️ NEEDS_PIPELINE_FIX: severity_rationale stage failed to produce this field")}')
    lines.append(f'- 为何不能更高: {rationale.get("why_not_higher", "⚠️ NEEDS_PIPELINE_FIX: severity_rationale stage failed to produce this field")}')
    return lines


def _render_repair_task_card(repair: dict) -> list[str]:
    """Render repair recommendation as task card (P0-5)."""
    lines = []
    lines.append("**修复任务卡 (Repair Task Card):**")

    # V2 schema fields
    if any(k in repair for k in ("task_id", "target_section", "suggested_wording", "owner_role", "regulatory_reference")):
        lines.append(f'- 任务ID: {repair.get("task_id", "⚠️ NEEDS_PIPELINE_FIX: repair stage failed to produce this field")}')
        lines.append(f'- 目标文档: {repair.get("target_document", "?")} / {repair.get("target_section", "⚠️ NEEDS_PIPELINE_FIX: repair stage failed to produce this field")}')
        lines.append(f'- 当前问题: {repair.get("current_text", "N/A")}')
        lines.append(f'- 建议措辞: {repair.get("suggested_wording", "⚠️ NEEDS_PIPELINE_FIX: repair stage failed to produce this field")}')
        lines.append(f'- 负责人角色: {repair.get("owner_role", "⚠️ NEEDS_PIPELINE_FIX: repair stage failed to produce this field")}')
        lines.append(f'- 法规引用: {repair.get("regulatory_reference", "⚠️ NEEDS_PIPELINE_FIX: repair stage failed to produce this field")}')
        lines.append(f'- 需要人工确认: {repair.get("requires_human_confirmation", True)}')
    else:
        # V1 fallback
        lines.append(f'- Action: {repair.get("action_type", "N/A")}')
        lines.append(f'- Target: {repair.get("target_document", "N/A")}')
        lines.append(f'- Current: "{_truncate(repair.get("current_text", ""), 100)}"')
        lines.append(f'- Suggested: "{_truncate(repair.get("suggested_text", ""), 100)}"')
        lines.append(f'- Confidence: {repair.get("confidence", "N/A")}')
        lines.append(f'- Requires Human Confirmation: {repair.get("requires_human_confirmation", True)}')

    return lines


def _render_evidence_confidence(finding: dict) -> list[str]:
    """Render evidence confidence with visual indicators (P1-2)."""
    lines = []
    confidence = finding.get("evidence_confidence", "")
    label = EVIDENCE_CONFIDENCE_LABEL.get(confidence, confidence) if confidence else "⚠️ MISSING_REQUIRED_FIELD: evidence_confidence"
    lines.append(f"**证据置信度:** {label}")
    if finding.get("needs_primary_source_verification", False):
        lines.append("⚠️ 需要原始来源验证")
    return lines


def _render_reviewer_feedback() -> list[str]:
    """Render reviewer feedback table after each finding (P1-3)."""
    return [
        "### 审阅人反馈 (Reviewer Feedback)",
        "| 真实问题? | 严重度合理? | 修复可执行? | 备注 |",
        "|-----------|------------|------------|------|",
        "| □ Yes □ No □ Unclear | □ Too high □ OK □ Too low | □ Yes □ Partly □ No | |",
    ]


def generate_review_package(project_id: str, artifact_dir: Path, output_path: Path) -> str:
    """Generate a human-readable Markdown review package.

    Returns the output path on success.
    """
    source_inv = load_artifact(artifact_dir, "source_inventory.json")
    findings = load_artifact(artifact_dir, "candidate_findings.json")
    report = load_artifact(artifact_dir, "review_report.json")
    state = load_artifact(artifact_dir, "review_state.json")
    manifest = load_artifact(artifact_dir, "directory_manifest.json")

    # ── Extract data ──────────────────────────────────────────────────────────
    inventory = source_inv.get("source_inventory", [])
    if isinstance(inventory, dict):
        inventory = [inventory]  # Normalize single-object format

    # D1 fix: handle flat single-object format (V7) and wrapped format (V6)
    if "finding_id" in findings:
        # Flat single-object: the loaded JSON IS a finding
        candidate_findings = [findings]
    else:
        candidate_findings = findings.get("candidate_findings", [])
        if isinstance(candidate_findings, dict):
            candidate_findings = [candidate_findings]

    # Build repair recommendation lookup from candidate_findings
    repair_map: dict[str, dict] = {}
    for f in candidate_findings:
        repair = f.get("repair_recommendation")
        if repair and isinstance(repair, dict):
            repair_map[f.get("finding_id", "")] = repair

    severity_signals = report.get("severity_signals", [])
    human_gate = report.get("human_gate_items", [])
    # D3 fix: handle V7 nested structure (under review_report key) and V6 flat structure
    nested = report.get("review_report", {}) if isinstance(report.get("review_report"), dict) else {}
    pipeline_limitations = report.get("pipeline_limitations") or nested.get("pipeline_limitations", [])
    calibration_summary = report.get("calibration_summary") or nested.get("calibration_summary", {})
    exec_summary = report.get("executive_summary") or nested.get("executive_summary", {})

    manifest_files = manifest.get("files", [])
    empty_files = manifest.get("empty_files", [])
    placeholder_files = manifest.get("placeholder_files", [])

    # Counts
    total_docs = len(inventory)
    n_empty = len(empty_files)
    n_placeholder = len(placeholder_files)
    sev_counts = _count_severity(severity_signals)
    n_blocking = sum(
        1
        for s in severity_signals
        if str(s.get("severity_advisory") or s.get("calibrated_severity") or s.get("severity", "")).upper() in ("CRITICAL", "HIGH")
    )
    n_human_gate = len(human_gate)
    n_repairs = len(repair_map)

    # Determine recommendation
    if sev_counts.get("CRITICAL", 0) > 0:
        recommendation = "HOLD — Critical gaps require resolution before CER finalization"
    elif n_blocking > 3:
        recommendation = "REVIEW — Multiple HIGH findings need human expert assessment"
    elif n_blocking > 0:
        recommendation = "PROCEED WITH CAUTION — Address HIGH findings before submission"
    else:
        recommendation = "ADVISORY COMPLETE — No blocking gaps identified"

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # ── Build Markdown ────────────────────────────────────────────────────────
    lines = []
    lines.append(f"# CER Review Assist — Project {project_id} Review Package")
    lines.append(f"")
    lines.append(f"**Generated:** {timestamp}  ")
    lines.append(f"**Pipeline Version:** V2.0 (3-Stage Advisory + Repair Recommendations)  ")
    lines.append(f"**Review Session:** {state.get('review_session_id', 'N/A')}  ")
    lines.append(f"**Flavor Profile:** {report.get('flavor_profile', 'BALANCED')}  ")
    lines.append(f"**Reviewer Decision:** PENDING (advisory only — no terminal verdicts)  ")
    lines.append(f"")

    # ── Executive Summary ─────────────────────────────────────────────────────
    lines.append(f"## Executive Summary")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total documents in manifest | {len(manifest_files)} |")
    lines.append(f"| Documents analyzed (source inventory) | {total_docs} |")
    lines.append(f"| Empty / placeholder files | {n_empty} / {n_placeholder} |")
    lines.append(f"| G-Points (total findings) | {len(severity_signals)} |")
    lines.append(f"| BLOCKING (CRITICAL + HIGH) | {n_blocking} |")
    lines.append(f"| Human gate items | {n_human_gate} |")
    lines.append(f"| Repair recommendations | {n_repairs} |")
    lines.append(f"| Calibration rules triggered | {len(calibration_summary.get('rules_triggered', []))} |")
    lines.append(f"| Severity adjustments | {calibration_summary.get('severity_adjustments', 0)} |")
    lines.append(f"| Pipeline limitations | {len(pipeline_limitations)} |")
    lines.append(f"")
    lines.append(f"**Workflow Recommendation:** {recommendation}")
    lines.append(f"")
    if exec_summary:
        lines.append(f"**Overall Assessment:** {exec_summary.get('overall_assessment', 'N/A')}")
        lines.append(f"")

    # ── Source Inventory ──────────────────────────────────────────────────────
    lines.append(f"## Source Inventory")
    lines.append(f"")
    if inventory:
        lines.append(f"| # | File | Type | Document Status | Evidence Depth | Size (chars) | Flags |")
        lines.append(f"|---|------|------|-----------------|----------------|-------------|-------|")
        for entry in inventory:
            fid = entry.get("file_id", "?")
            name = _truncate(entry.get("relative_path", ""), 50)
            dtype = entry.get("document_type", "?")
            doc_status = _get_document_status(entry)
            depth = EVIDENCE_DEPTH_LABEL_V2.get(entry.get("evidence_depth", ""), entry.get("evidence_depth", "?"))
            size = entry.get("character_count", 0)
            flags = ", ".join(entry.get("flags", [])) if entry.get("flags") else "—"
            lines.append(f"| {fid} | {name} | {dtype} | {doc_status} | {depth} | {size:,} | {flags} |")
        lines.append(f"")
    else:
        lines.append(f"*(No source inventory entries)*")
        lines.append(f"")

    # Coverage note
    batch_summary = source_inv.get("batch_summary", {})
    if batch_summary:
        lines.append(f"**Coverage:** {batch_summary.get('files_covered', 0)}/{batch_summary.get('total_files', 0)} files ({batch_summary.get('coverage_pct', 0)}%) across {batch_summary.get('total_batches', 0)} batches")
        lines.append(f"")

    # Empty/placeholder files callout
    if empty_files:
        lines.append(f"**Empty files (0 bytes):** {', '.join(empty_files)}")
        lines.append(f"")
    if placeholder_files:
        lines.append(f"**Placeholder files (<100 bytes):** {', '.join(placeholder_files)}")
        lines.append(f"")

    # ── Gap Findings ──────────────────────────────────────────────────────────
    lines.append(f"## Gap Findings")
    lines.append(f"")

    # Severity distribution
    lines.append(f"| Severity | Count |")
    lines.append(f"|----------|-------|")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        lines.append(f"| {SEVERITY_ICON.get(sev, sev)} | {sev_counts.get(sev, 0)} |")
    lines.append(f"")

    # BLOCKING section
    blocking = [
        s
        for s in severity_signals
        if str(s.get("severity_advisory") or s.get("calibrated_severity") or s.get("severity", "")).upper() in ("CRITICAL", "HIGH")
    ]
    if blocking:
        lines.append(f"### BLOCKING ({len(blocking)})")
        lines.append(f"")
        for i, sig in enumerate(blocking, 1):
            lines.append(f"**{i}. {sig.get('signal_id', '?')}** | {sig.get('finding_ref', '?')}")
            lines.append(f"")
            lines.extend(_render_severity_line(sig))
            depth_label = EVIDENCE_DEPTH_LABEL_V2.get(
                sig.get("evidence_depth_at_finding", ""), sig.get("evidence_depth_at_finding", "?")
            )
            lines.append(f"- **Evidence Depth:** {depth_label}")
            lines.append(f"- **Calibration Rule:** {sig.get('calibration_rule_ref', '?')}")
            lines.append(f"- **Rationale:** {sig.get('calibration_rationale', 'N/A')}")
            if sig.get("severity_adjustment") and sig["severity_adjustment"] != "none":
                lines.append(f"- **Severity Adjustment:** {sig['severity_adjustment']} — {sig.get('adjustment_reason', 'N/A')}")

            # P0-1 Evidence block
            finding_ref = sig.get("finding_ref", "")
            candidate = next((f for f in candidate_findings if f.get("finding_id") == finding_ref), {})
            lines.extend(_render_evidence_block(candidate))
            lines.append(f"")

            # P0-4 Severity rationale
            lines.extend(_render_severity_rationale(candidate))
            lines.append(f"")

            # P1-2 Evidence confidence
            lines.extend(_render_evidence_confidence(candidate))
            lines.append(f"")

            # P0-5 Repair recommendation
            repair = repair_map.get(finding_ref)
            if repair:
                lines.extend(_render_repair_task_card(repair))
            else:
                lines.append("⚠️ MISSING_REQUIRED_FIELD: repair_recommendation not available in upstream artifact")
            lines.append(f"")

            # P1-3 Reviewer feedback
            lines.extend(_render_reviewer_feedback())
            lines.append(f"")
    else:
        lines.append(f"### BLOCKING (0)")
        lines.append(f"")
        lines.append(f"*No CRITICAL or HIGH severity findings.*")
        lines.append(f"")

    # WARNING section
    warnings = [
        s
        for s in severity_signals
        if str(s.get("severity_advisory") or s.get("calibrated_severity") or s.get("severity", "")).upper() in ("MEDIUM", "LOW")
    ]
    if warnings:
        lines.append(f"### WARNING ({len(warnings)})")
        lines.append(f"")
        for i, sig in enumerate(warnings, 1):
            lines.append(f"**{i}. {sig.get('signal_id', '?')}** | {sig.get('finding_ref', '?')} — {_get_severity_icon(sig)}")
            lines.append(f"  {sig.get('calibration_rationale', 'N/A')}")

            # P0-1 Evidence block for warnings
            finding_ref = sig.get("finding_ref", "")
            candidate = next((f for f in candidate_findings if f.get("finding_id") == finding_ref), {})
            for ev_line in _render_evidence_block(candidate):
                lines.append(f"  {ev_line}")

            # P0-4 Severity rationale for warnings
            for sr_line in _render_severity_rationale(candidate):
                lines.append(f"  {sr_line}")

            # P1-2 Evidence confidence for warnings
            for ec_line in _render_evidence_confidence(candidate):
                lines.append(f"  {ec_line}")

            # Repair recommendation for warnings
            repair = repair_map.get(finding_ref)
            if repair:
                for rp_line in _render_repair_task_card(repair):
                    lines.append(f"  {rp_line}")
            else:
                lines.append("  ⚠️ MISSING_REQUIRED_FIELD: repair_recommendation not available in upstream artifact")

            # P1-3 Reviewer feedback for warnings
            for fb_line in _render_reviewer_feedback():
                lines.append(f"  {fb_line}")
            lines.append(f"")

    # ── Human Gate Items ──────────────────────────────────────────────────────
    lines.append(f"## Human Gate Items ({n_human_gate})")
    lines.append(f"")
    if human_gate:
        lines.append(f"| # | Finding | Severity | Trigger Rule | Auto-Route Reason |")
        lines.append(f"|---|---------|----------|-------------|-------------------|")
        for item in human_gate:
            iid = item.get("item_id", "?")
            ref = item.get("finding_ref", "?")
            sev = _get_severity_icon(item)
            rule = item.get("auto_route_rule_ref", "?")
            reason = _truncate(item.get("auto_route_reason", "?"), 60)
            lines.append(f"| {iid} | {ref} | {sev} | {rule} | {reason} |")
        lines.append(f"")

        # Detailed actions
        lines.append(f"### Recommended Reviewer Actions")
        lines.append(f"")
        for item in human_gate:
            lines.append(f"**{item.get('item_id', '?')} — {item.get('finding_ref', '?')}**")
            lines.append(f"- **Evidence:** {item.get('evidence_summary', 'N/A')}")
            lines.append(f"- **Action:** {item.get('recommended_reviewer_action', 'N/A')}")
            lines.append(f"- **Controlled Hold:** {'Yes' if item.get('controlled_hold') else 'No'}")
            lines.append(f"")
    else:
        lines.append(f"*No human gate items.*")
        lines.append(f"")

    # ── Repair Recommendations ──────────────────────────────────────────────
    lines.append(f"## Repair Recommendations ({n_repairs})")
    lines.append(f"")
    if repair_map:
        lines.append(f"| Finding | Action Type | Target Document | Suggested Change | Confidence |")
        lines.append(f"|---------|-------------|-----------------|-----------------|------------|")
        for finding_id, repair in sorted(repair_map.items()):
            action = repair.get("action_type", "?")
            target = _truncate(repair.get("target_document", "?"), 35)
            suggestion = _truncate(repair.get("suggested_text", repair.get("suggested_wording", "?")), 50)
            conf = repair.get("confidence", "?")
            needs_human = "Yes" if repair.get("requires_human_confirmation", True) else "No"
            lines.append(f"| {finding_id} | {action} | {target} | {suggestion} | {conf} |")
        lines.append(f"")
        lines.append(f"**All repair recommendations require human confirmation before execution.**")
        lines.append(f"")
    else:
        lines.append(f"*No repair recommendations generated.*")
        lines.append(f"")

    # ── Calibration Summary ───────────────────────────────────────────────────
    lines.append(f"## Calibration Summary")
    lines.append(f"")
    if calibration_summary:
        lines.append(f"- **Rules Triggered:** {', '.join(calibration_summary.get('rules_triggered', []))}")
        lines.append(f"- **Severity Adjustments:** {calibration_summary.get('severity_adjustments', 0)}")
        lines.append(f"- **Auto-Routed to Human:** {calibration_summary.get('auto_routed_to_human', 0)}")
        lines.append(f"")

    # ── Known Limitations ─────────────────────────────────────────────────────
    lines.append(f"## Known Limitations & Pipeline Notes")
    lines.append(f"")
    if pipeline_limitations:
        for i, lim in enumerate(pipeline_limitations, 1):
            lines.append(f"**{i}. {lim.get('limitation_type', 'Unknown')}**")
            lines.append(f"  {lim.get('description', 'N/A')}")
            if lim.get("affected_findings"):
                affected = lim['affected_findings']
                lines.append(f"  Affected findings: {', '.join(affected)}")
            lines.append(f"")

    # File not analyzed
    docs_not_analyzed = len(manifest_files) - total_docs
    if docs_not_analyzed > 0:
        analyzed_names = {e.get("relative_path", "") for e in inventory}
        not_analyzed = [f["name"] for f in manifest_files if f["name"] not in analyzed_names]
        lines.append(f"- **Files not analyzed:** {docs_not_analyzed} — {', '.join(not_analyzed)}")
        lines.append(f"")

    lines.append(f"- **Empty files:** {n_empty}")
    lines.append(f"- **Pipeline mode:** Advisory-only, all decisions PENDING")
    lines.append(f"- **State machine:** {state.get('current_state', 'unknown')}")
    lines.append(f"")

    # ── Reviewer Checklist ────────────────────────────────────────────────────
    lines.append(f"## Reviewer Checklist")
    lines.append(f"")
    lines.append(f"- [ ] All critical documents are in source inventory")
    lines.append(f"- [ ] Evidence depth classifications look correct")
    lines.append(f"- [ ] BLOCKING gaps are truly blocking (confirm {n_blocking} items)")
    lines.append(f"- [ ] WARNING gaps are actionable")
    lines.append(f"- [ ] Human gate items include all CRITICAL/HIGH findings")
    lines.append(f"- [ ] Repair recommendations are actionable and target correct documents")
    lines.append(f"- [ ] All repair recommendations have requires_human_confirmation=true")
    lines.append(f"- [ ] Severity levels are appropriate (review {calibration_summary.get('severity_adjustments', 0)} adjustments)")
    lines.append(f"- [ ] Calibration rules triggered are relevant to this device class")
    lines.append(f"- [ ] Pipeline limitations do not mask additional gaps")
    lines.append(f"")

    lines.append(f"---")
    lines.append(f"*Generated by CER Review Assist 3-Stage Pipeline. All decisions are advisory (PENDING). No terminal verdicts.*")

    # ── Write output ──────────────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")
    print(f"Review package written to: {output_path} ({len(content)} chars)")

    return str(output_path)


def generate_feedback_form(project_id: str, output_path: Path) -> str:
    """Generate a simplified feedback form for human expert review."""
    lines = []
    lines.append(f"# Feedback — Project {project_id}")
    lines.append(f"")
    lines.append(f"**Reviewer:** _____________  ")
    lines.append(f"**Role:** □ Clinical  □ Regulatory  □ Technical  □ PM  ")
    lines.append(f"**Date:** _____________  ")
    lines.append(f"")

    for section, items in [
        ("Source Inventory", [
            "Coverage adequate (all key docs present)",
            "Evidence depth classifications correct",
            "Anti-pattern flags accurate",
        ]),
        ("Gap Findings", [
            "Real gaps caught (no major misses)",
            "False positives acceptable",
            "Severity levels appropriate",
        ]),
        ("Human Gate", [
            "All critical items included",
            "Routing makes clinical/regulatory sense",
        ]),
        ("Calibration", [
            "Rules triggered are relevant",
            "Severity adjustments are justified",
        ]),
    ]:
        lines.append(f"## {section} (rate 1–5)")
        lines.append(f"")
        for item in items:
            lines.append(f"- [ ] _{'☆' * 5}_  **{item}**")
        lines.append(f"")
        lines.append(f"**Comments:** ___________________________")
        lines.append(f"")

    lines.append(f"## Overall")
    lines.append(f"")
    lines.append(f"**Would you trust this as a first-pass review?** □ Yes □ No □ With reservations")
    lines.append(f"")
    lines.append(f"**Biggest improvement needed:** ___________________________")
    lines.append(f"")
    lines.append(f"**Additional notes:** ___________________________")
    lines.append(f"")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")
    print(f"Feedback form written to: {output_path}")

    return str(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate human-readable review package from 3-stage pipeline artifacts",
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="Project ID to look up in build_v7 (e.g., 052_zhuhai_jianfan)",
    )
    parser.add_argument(
        "--artifact-dir",
        default=None,
        help="Direct path to artifact directory (overrides --project-id)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for review package .md (default: build_v6/review_packages/REVIEW_PACKAGE_{id}.md)",
    )
    args = parser.parse_args()

    if args.artifact_dir:
        artifact_dir = Path(args.artifact_dir)
        project_id = artifact_dir.name
    elif args.project_id:
        project_id = args.project_id
        artifact_dir = BUILD_V8.parent / "build_v7" / project_id  # V7 artifacts are the baseline
        if not artifact_dir.exists():
            print(f"ERROR: Artifact directory not found: {artifact_dir}")
            return
    else:
        print("ERROR: Either --project-id or --artifact-dir is required")
        return

    output_path = Path(args.output) if args.output else OUTPUT_DIR / f"REVIEW_PACKAGE_{project_id}.md"
    feedback_path = FEEDBACK_DIR / f"FEEDBACK_{project_id}.md"

    print(f"Project: {project_id}")
    print(f"Artifacts: {artifact_dir}")
    print()

    # Generate review package
    generate_review_package(project_id, artifact_dir, output_path)

    # Generate feedback form
    generate_feedback_form(project_id, feedback_path)

    print()
    print("Done. Ready for human review.")


if __name__ == "__main__":
    main()
