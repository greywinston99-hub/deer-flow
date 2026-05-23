#!/usr/bin/env python3
"""End-to-end test: CER Review → Authoring weak-coupling pipeline.

Tests the complete data flow:
1. Review findings → feedback_writer → review_feedback/latest.json
2. Authoring init → _load_review_feedback (with resolved filtering)
3. Evidence appraisal → auto depth tagging → G41 gate
4. Claim decomposition → feedback sorting → resolution log
5. Feedback effectiveness report generation
6. Quick-scan graph + artifact generation

Run:
    cd backend && .venv/bin/python -m pytest tests/e2e/test_review_to_authoring_pipeline.py -v
    # Or standalone:
    cd backend && .venv/bin/python tests/e2e/test_review_to_authoring_pipeline.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "harness"))

from deerflow.runtime.cer_review.feedback_writer import ReviewFeedbackWriter
from deerflow.runtime.cer_authoring.graph import _load_review_feedback
from deerflow.runtime.cer_authoring.pipeline import _enrich_evidence_with_depth
from deerflow.runtime.cer_authoring.gates import evaluate_fulltext_basis_gate
from deerflow.runtime.cer_authoring.artifacts import _build_feedback_effectiveness_report
from deerflow.runtime.cer_review.review_assist_lead_agent import (
    build_review_assist_graph,
    build_review_quick_scan_graph,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_e2e_review_feedback_pipeline() -> None:
    """E2E-1: Review findings → feedback writer → versioned JSON."""
    print("\n=== E2E-1: Review → Feedback Writer ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = ReviewFeedbackWriter(tmpdir)

        # Simulate Review findings from gap-specialist + logic-qa
        findings = [
            {
                "finding_id": "F-LOGIC-001",
                "severity": "CRITICAL",
                "evidence_depth": "PRIMARY_VERBATIM",
                "category": "cross_doc_inconsistency",
                "description": "CER Section 4.2 claims indication X for population Y, but IFU restricts to Z.",
                "target_claim_id": "CER-4.2-IND-X",
                "suggested_rework_node": "claim_decomposition",
            },
            {
                "finding_id": "F-GAP-002",
                "severity": "HIGH",
                "evidence_depth": "SECONDARY_SUMMARY",
                "category": "evidence_quality_gap",
                "description": "Pivotal evidence E-205 lacks full-text verification.",
                "target_evidence_id": "E-205",
                "suggested_rework_node": "evidence_appraisal",
            },
            {
                "finding_id": "F-GAP-002",  # duplicate ID, longer desc should win
                "severity": "HIGH",
                "evidence_depth": "SECONDARY_SUMMARY",
                "category": "evidence_quality_gap",
                "description": "Pivotal evidence E-205 lacks full-text verification — abstract only available.",
                "target_evidence_id": "E-205",
                "suggested_rework_node": "evidence_appraisal",
            },
            {
                "finding_id": "F-LOGIC-003",
                "severity": "MEDIUM",
                "evidence_depth": "PRIMARY_DERIVED",
                "category": "terminology_non_standard",
                "description": "Non-standard term 'burn lesion' used instead of 'skin burn'.",
                "suggested_rework_node": "writer_synthesis",
            },
        ]

        path = writer.write_feedback(findings, source="cer_review_assist_sandbox_v2_0")

        # Verify versioned file exists
        _assert(path.exists(), f"Versioned file not found: {path}")
        print(f"  [OK] Versioned file: {path.name}")

        # Verify latest.json exists
        latest = Path(tmpdir) / "review_feedback" / "latest.json"
        _assert(latest.exists(), "latest.json not found")
        print(f"  [OK] latest.json exists")

        # Verify versions.json exists
        versions_file = Path(tmpdir) / "review_feedback" / "versions.json"
        _assert(versions_file.exists(), "versions.json not found")
        versions = json.loads(versions_file.read_text())
        _assert(len(versions["versions"]) == 1, "versions.json should have 1 entry")
        _assert(versions["latest"] is not None, "versions.json missing latest")
        print(f"  [OK] versions.json tracked: {versions['latest']}")

        # Verify deduplication (F-GAP-002 duplicate removed, longer desc kept)
        data = json.loads(path.read_text())
        fids = [f["finding_id"] for f in data["findings"]]
        _assert(fids.count("F-GAP-002") == 1, f"F-GAP-002 should be deduped, got: {fids}")
        gap_finding = next(f for f in data["findings"] if f["finding_id"] == "F-GAP-002")
        _assert("abstract only" in gap_finding["description"], "Longer description should win in dedup")
        print(f"  [OK] Deduplication: {len(data['findings'])} unique findings (from 4 raw)")

        # Verify advisory_only constraint
        _assert(data["advisory_only"] is True, "advisory_only must be True")
        _assert("auto_modify_claim_ledger" in data.get("prohibited_actions", []), "prohibited_actions missing")
        print(f"  [OK] advisory_only + prohibited_actions enforced")

        # Verify category → rework_node mapping
        cross_doc = next(f for f in data["findings"] if f["finding_id"] == "F-LOGIC-001")
        _assert(cross_doc["suggested_rework_node"] == "claim_decomposition", "cross_doc_inconsistency should map to claim_decomposition")
        print(f"  [OK] Category→node mapping correct")

        print("  E2E-1 PASSED ✅")


def test_e2e_authoring_feedback_loading() -> None:
    """E2E-2: Authoring init → load feedback → resolved filtering."""
    print("\n=== E2E-2: Authoring Feedback Loading ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        fb_dir = Path(tmpdir) / "review_feedback"
        fb_dir.mkdir()

        feedback = {
            "feedback_id": "RF-20250523000000",
            "source": "cer_review_assist_sandbox_v2_0",
            "advisory_only": True,
            "generated_at": "2025-05-23T00:00:00+00:00",
            "findings": [
                {"finding_id": "F-001", "severity": "CRITICAL", "evidence_depth": "PRIMARY_VERBATIM", "category": "cross_doc_inconsistency", "description": "Claim mismatch"},
                {"finding_id": "F-002", "severity": "HIGH", "evidence_depth": "PRIMARY_DERIVED", "category": "evidence_quality_gap", "description": "Missing fulltext"},
                {"finding_id": "F-003", "severity": "MEDIUM", "evidence_depth": "SECONDARY_SUMMARY", "category": "missing_evidence", "description": "No SOTA benchmark"},
                {"finding_id": "F-004", "severity": "LOW", "evidence_depth": "SECONDARY_SUMMARY", "category": "format_degradation", "description": "Table alignment off"},
            ],
            "prohibited_actions": ["auto_modify_claim_ledger"],
        }
        (fb_dir / "latest.json").write_text(json.dumps(feedback))

        # Test 1: Load without resolved filter → all 4 findings
        result1 = _load_review_feedback(tmpdir)
        _assert(result1 is not None, "Feedback should load")
        _assert(len(result1["findings"]) == 4, f"Expected 4 findings, got {len(result1['findings'])}")
        print(f"  [OK] Loaded all {len(result1['findings'])} findings")

        # Test 2: Load with resolved filter → only unresolved remain
        result2 = _load_review_feedback(tmpdir, resolved_ids=["F-001", "F-004"])
        _assert(len(result2["findings"]) == 2, f"Expected 2 findings after filter, got {len(result2['findings'])}")
        remaining_ids = {f["finding_id"] for f in result2["findings"]}
        _assert(remaining_ids == {"F-002", "F-003"}, f"Wrong findings after filter: {remaining_ids}")
        print(f"  [OK] Resolved filtering: F-001/F-004 removed, F-002/F-003 remain")

        # Test 3: Non-advisory feedback rejected
        bad_feedback = dict(feedback)
        bad_feedback["advisory_only"] = False
        (fb_dir / "latest.json").write_text(json.dumps(bad_feedback))
        result3 = _load_review_feedback(tmpdir)
        _assert(result3 is None, "Non-advisory feedback should be rejected")
        print(f"  [OK] Non-advisory feedback rejected")

        print("  E2E-2 PASSED ✅")


def test_e2e_evidence_depth_tagging_and_g41() -> None:
    """E2E-3: Evidence appraisal → auto depth tagging → G41 gate."""
    print("\n=== E2E-3: Evidence Depth + G41 Gate ===")

    # Simulate evidence registry entries from pipeline
    raw_registry = [
        {"evidence_id": "E-001", "appraisal_basis": "full_text_available", "source_type": "literature_pubmed_sota", "weight": "pivotal"},
        {"evidence_id": "E-002", "appraisal_basis": "abstract_or_bibliographic_only", "source_type": "literature_pubmed_sota", "weight": "pivotal"},
        {"evidence_id": "E-003", "appraisal_basis": "source_full_text_or_extended_record_available", "source_type": "literature_pubmed_sota", "weight": "supportive"},
        {"evidence_id": "E-GAP-001", "source_type": "gap_placeholder", "weight": "pivotal"},
        {"evidence_id": "E-005", "appraisal_basis": "full_text_available", "source_type": "subject_device_clinical_study", "weight": "pivotal"},
    ]

    enriched = _enrich_evidence_with_depth({"evidence_registry": raw_registry})

    # Verify auto-tagging
    depths = {r["evidence_id"]: r["evidence_depth"] for r in enriched}
    _assert(depths["E-001"] == "PRIMARY_VERBATIM", f"E-001 should be PRIMARY_VERBATIM, got {depths['E-001']}")
    _assert(depths["E-002"] == "SECONDARY_SUMMARY", f"E-002 should be SECONDARY_SUMMARY, got {depths['E-002']}")
    _assert(depths["E-003"] == "PRIMARY_DERIVED", f"E-003 should be PRIMARY_DERIVED, got {depths['E-003']}")
    _assert(depths["E-GAP-001"] == "MISSING_PRIMARY", f"E-GAP-001 should be MISSING_PRIMARY, got {depths['E-GAP-001']}")
    _assert(depths["E-005"] == "PRIMARY_VERBATIM", f"E-005 should be PRIMARY_VERBATIM, got {depths['E-005']}")
    print(f"  [OK] Auto depth tagging: {depths}")

    # Test G41 gate
    # Case 1: E-001 (PRIMARY_VERBATIM, pivotal) + E-002 (SECONDARY_SUMMARY, pivotal) → should FAIL
    state_fail = {"evidence_registry": enriched, "gate_overrides": {}}
    result_fail = evaluate_fulltext_basis_gate(state_fail)
    _assert(result_fail["status"] == "REWORK_REQUIRED", f"G41 should reject due to E-002 SECONDARY_SUMMARY pivotal, got {result_fail['status']}")
    print(f"  [OK] G41 rejects SECONDARY_SUMMARY pivotal evidence")

    # Case 2: Only E-001, E-003, E-005 (all sufficient depth + fulltext available) → should PASS
    registry_pass = [r for r in enriched if r["evidence_id"] not in {"E-002", "E-GAP-001"}]
    state_pass = {"evidence_registry": registry_pass, "gate_overrides": {}}
    result_pass = evaluate_fulltext_basis_gate(state_pass)
    _assert(result_pass["status"] == "PASS", f"G41 should pass with all sufficient depth, got {result_pass['status']}")
    print(f"  [OK] G41 passes with PRIMARY_VERBATIM/PRIMARY_DERIVED pivotal evidence")

    print("  E2E-3 PASSED ✅")


def test_e2e_claim_decomposition_feedback_integration() -> None:
    """E2E-4: Claim decomposition → feedback sorting + resolution log."""
    print("\n=== E2E-4: Claim Decomposition Feedback Integration ===")

    # Simulate state with review_feedback
    review_feedback = {
        "findings": [
            {"finding_id": "F-INFO-001", "severity": "INFORMATIONAL", "category": "format_degradation", "description": "Minor formatting", "suggested_rework_node": "cer_writing"},
            {"finding_id": "F-MED-001", "severity": "MEDIUM", "category": "missing_evidence", "description": "SOTA benchmark missing", "suggested_rework_node": "sota_search"},
            {"finding_id": "F-CRIT-001", "severity": "CRITICAL", "category": "cross_doc_inconsistency", "description": "IFU contradicts CER", "suggested_rework_node": "claim_decomposition"},
            {"finding_id": "F-HIGH-001", "severity": "HIGH", "category": "claim_evidence_mismatch", "description": "Claim lacks evidence", "suggested_rework_node": "claim_decomposition"},
            {"finding_id": "F-LOW-001", "severity": "LOW", "category": "terminology_non_standard", "description": "Term issue", "suggested_rework_node": "writer_synthesis"},
        ]
    }

    # Simulate relevant_feedback filtering + sorting (from graph.py _node_claim_decomposition)
    _SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFORMATIONAL": 4}
    relevant_feedback = sorted(
        [f for f in review_feedback["findings"]
         if f.get("suggested_rework_node") in {None, "claim_decomposition", "device_profile"}],
        key=lambda f: _SEVERITY_ORDER.get(str(f.get("severity", "")).upper(), 99),
    )

    # Verify sorting: CRITICAL first, then HIGH (MEDIUM finding has suggested_rework_node=sota_search, filtered out)
    severities = [f["severity"] for f in relevant_feedback]
    _assert(severities == ["CRITICAL", "HIGH"], f"Wrong sort order: {severities}")
    print(f"  [OK] Feedback sorted by severity: {severities}")

    # Verify only claim_decomposition/device_profile relevant findings kept
    _assert(len(relevant_feedback) == 2, f"Expected 2 relevant findings, got {len(relevant_feedback)}")
    for f in relevant_feedback:
        _assert(f["suggested_rework_node"] in {None, "claim_decomposition", "device_profile"},
                f"Finding {f['finding_id']} has wrong node: {f['suggested_rework_node']}")
    print(f"  [OK] Filtered to claim_decomposition/device_profile relevant: {len(relevant_feedback)} findings")

    # Simulate resolution log (from graph.py approval handling)
    resolution_log = [
        {"finding_id": "F-CRIT-001", "action": "adopted", "note": "Fixed IFU contradiction", "node": "claim_decomposition"},
        {"finding_id": "F-HIGH-001", "action": "partially_addressed", "note": "Added evidence E-102", "node": "claim_decomposition"},
    ]

    # Verify resolved IDs extraction
    resolved_ids = [str(entry["finding_id"]) for entry in resolution_log]
    _assert("F-CRIT-001" in resolved_ids, "F-CRIT-001 should be resolved")
    _assert("F-HIGH-001" in resolved_ids, "F-HIGH-001 should be resolved")
    print(f"  [OK] Resolution log captures {len(resolution_log)} actions")

    print("  E2E-4 PASSED ✅")


def test_e2e_feedback_effectiveness_report() -> None:
    """E2E-5: Feedback effectiveness report generation."""
    print("\n=== E2E-5: Feedback Effectiveness Report ===")

    state = {
        "feedback_resolution_log": [
            {"finding_id": "F-001", "action": "adopted", "note": "Fixed claim"},
            {"finding_id": "F-002", "action": "ignored", "note": "False positive"},
            {"finding_id": "F-003", "action": "adopted", "note": "Added evidence"},
            {"finding_id": "F-004", "action": "ignored", "note": "Not applicable"},
            {"finding_id": "F-005", "action": "ignored", "note": "Disagree"},
        ],
        "review_feedback": {
            "findings": [
                {"finding_id": "F-001", "category": "cross_doc_inconsistency", "severity": "CRITICAL"},
                {"finding_id": "F-002", "category": "cross_doc_inconsistency", "severity": "HIGH"},
                {"finding_id": "F-003", "category": "evidence_quality_gap", "severity": "HIGH"},
                {"finding_id": "F-004", "category": "terminology_non_standard", "severity": "LOW"},
                {"finding_id": "F-005", "category": "terminology_non_standard", "severity": "LOW"},
            ]
        },
    }

    report = _build_feedback_effectiveness_report(state)

    # Verify summary
    _assert(report["summary"]["adoption_rate"] == 0.4, f"Expected 40% adoption, got {report['summary']['adoption_rate']}")
    _assert(report["summary"]["ignore_rate"] == 0.6, f"Expected 60% ignore, got {report['summary']['ignore_rate']}")
    print(f"  [OK] Adoption rate: {report['summary']['adoption_rate']}, Ignore rate: {report['summary']['ignore_rate']}")

    # Verify false positive signals
    fp_signals = report.get("false_positive_signals", [])
    # terminology_non_standard has 2/2 ignored = 100% ignore rate → should be flagged
    terminology_fp = next((s for s in fp_signals if s["category"] == "terminology_non_standard"), None)
    _assert(terminology_fp is not None, "terminology_non_standard should be flagged as false positive")
    _assert(terminology_fp["ignore_rate"] == 1.0, f"Expected 100% ignore rate, got {terminology_fp['ignore_rate']}")
    print(f"  [OK] False positive detection: terminology_non_standard ignore_rate={terminology_fp['ignore_rate']}")

    # Verify category breakdown
    cross_doc = report["category_breakdown"].get("cross_doc_inconsistency", {})
    _assert(cross_doc.get("adopted", 0) == 1, "cross_doc_inconsistency should have 1 adopted")
    _assert(cross_doc.get("ignored", 0) == 1, "cross_doc_inconsistency should have 1 ignored")
    print(f"  [OK] Category breakdown: {report['category_breakdown']}")

    print("  E2E-5 PASSED ✅")


def test_e2e_quick_scan_graph() -> None:
    """E2E-6: Quick-scan graph compilation + artifact structure."""
    print("\n=== E2E-6: Quick-Scan Graph ===")

    # Test graph compilation
    graph = build_review_quick_scan_graph()
    nodes = set(graph.nodes.keys())
    # LangGraph __end__ is implicit; check core nodes exist
    expected_nodes = {"directory_inventory", "evidence_curator", "gap_specialist", "quick_scan_feedback_writer", "blocked"}
    _assert(expected_nodes.issubset(nodes), f"Quick-scan nodes missing. Expected {expected_nodes} subset of {nodes}")
    print(f"  [OK] Quick-Scan graph compiled with {len(graph.nodes)} nodes")

    # Verify quick_scan_feedback_writer artifact format
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = ReviewFeedbackWriter(tmpdir)
        findings = [
            {"finding_id": "F-QS-001", "severity": "CRITICAL", "category": "cross_doc_inconsistency", "description": "Quick scan finding", "evidence_depth": "PRIMARY_VERBATIM"},
            {"finding_id": "F-QS-002", "severity": "HIGH", "category": "missing_evidence", "description": "Another finding", "evidence_depth": "SECONDARY_SUMMARY"},
            {"finding_id": "F-QS-003", "severity": "MEDIUM", "category": "format_degradation", "description": "Format issue", "evidence_depth": "PRIMARY_DERIVED"},
            {"finding_id": "F-QS-004", "severity": "LOW", "category": "terminology_non_standard", "description": "Term issue", "evidence_depth": "SECONDARY_SUMMARY"},
            {"finding_id": "F-QS-005", "severity": "INFORMATIONAL", "category": "metadata_inconsistency", "description": "Meta issue", "evidence_depth": "SECONDARY_SUMMARY"},
            {"finding_id": "F-QS-006", "severity": "CRITICAL", "category": "regulatory_boundary_violation", "description": "Boundary issue", "evidence_depth": "PRIMARY_VERBATIM"},
        ]

        # Simulate quick-scan feedback writer behavior (top 5 by severity)
        _SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFORMATIONAL": 4}
        top5 = sorted(findings, key=lambda f: _SEVERITY_ORDER.get(str(f.get("severity", "")).upper(), 99))[:5]
        feedback = writer._build_feedback(top5, source="cer_review_quick_scan", source_project_id=None)

        _assert(len(feedback["findings"]) == 5, f"Quick-scan should limit to 5 findings, got {len(feedback['findings'])}")
        # First should be CRITICAL
        _assert(feedback["findings"][0]["severity"] == "CRITICAL", "First finding should be CRITICAL")
        # Last should be LOW (INFORMATIONAL excluded)
        _assert(feedback["findings"][-1]["severity"] == "LOW", "Last of top-5 should be LOW")
        print(f"  [OK] Top-5 severity filtering: {len(feedback['findings'])} findings, severities: {[f['severity'] for f in feedback['findings']]}")

    print("  E2E-6 PASSED ✅")


def run_all_tests() -> int:
    """Run all E2E tests and return exit code."""
    tests = [
        test_e2e_review_feedback_pipeline,
        test_e2e_authoring_feedback_loading,
        test_e2e_evidence_depth_tagging_and_g41,
        test_e2e_claim_decomposition_feedback_integration,
        test_e2e_feedback_effectiveness_report,
        test_e2e_quick_scan_graph,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  FAILED ❌: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR 💥: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"E2E TEST RESULTS: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*50}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
