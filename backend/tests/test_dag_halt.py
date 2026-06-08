"""test_dag_halt.py — Prove DAG dynamic halt and state payload correctness.

Runs three scenarios:
1. SEVERITY_HALT: CER with missing benefit-risk elements triggers high-severity
   findings, causing the DAG to route to human_adjudication_pending before
   cer_gate_closure.
2. CLASS_III_CRITICAL: Device class "Class III" without data-access contract
   triggers a critical finding in equivalence assessment.
3. CROSS_DOMAIN_CONFLICT: Clinical evidence findings contradict intended
   purpose claims; conflict is logged in shared State.

Outputs a single JSON object to stdout with verdict, halted_node,
resume_from_node, and cross_domain_conflict evidence.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

# Ensure runner imports resolve
REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_ROOT = REPO_ROOT / "packages"
sys.path.insert(0, str(PKG_ROOT))

from deerflow.runtime.cer_review.runner import CERReviewRunner, _LANGGRAPH_AVAILABLE


def _write_project_profile(tmpdir: Path, project_id: str, device_class: str) -> Path:
    profile = {
        "project_id": project_id,
        "project_name": f"DAG Test {project_id}",
        "institution_profile": {"organization": "Test Org", "assessment_body": "Test Body"},
        "review_scope": {"mode": "smoke_precheck", "review_language": "en", "jurisdiction": "EU MDR"},
        "primary_review_object": "CER",
        "device_context": {
            "device_name": "Test Device",
            "device_family": "Test Family",
            "device_class": device_class,
            "intended_use": "Test device for pediatric lesion treatment.",
            "market_stage": "technical_documentation_review",
            "implantable_status": False,
            "intended_purpose_confirmed": True,
        },
        "project_protocol": {
            "project_id": project_id,
            "product_name": "Test Device",
            "device_class": device_class,
            "gate_a_status": "draft",
            "assessment_type": "smoke_precheck",
        },
        "input_package": {
            "root_path": str(tmpdir / "input"),
            "documents": [
                {
                    "doc_type": "CER",
                    "label": "Clinical Evaluation Report",
                    "path": "CER.txt",
                    "required_for_p0": True,
                    "source_ref": {"document_id": "cer_main", "path": "CER.txt"},
                }
            ],
        },
        "artifact_policy": {
            "artifact_root": str(tmpdir / "artifacts"),
            "persist_intermediate_artifacts": True,
        },
    }
    path = tmpdir / "project_profile.yaml"
    import yaml
    path.write_text(yaml.dump(profile), encoding="utf-8")
    return path


def _write_cer_text(path: Path, variant: str) -> None:
    """Write a CER text tailored to the test scenario."""
    if variant == "severity_halt":
        # Missing benefit-risk, ALARP present, no binary criterion -> high findings
        content = """
Clinical Evaluation Report

1. INTENDED PURPOSE
The device is intended for pediatric lesion treatment.

2. EQUIVALENCE
Equivalence is demonstrated with Predicate Device XYZ.
Technical: design, specification, energy.
Biological: material, biocompatibility, contact, duration, sterilization.
Clinical: patient population, indication, user, use environment, clinical outcome.

3. BENEFIT-RISK
ALARP (As Low As Reasonably Practicable) has been applied.
No explicit acceptable or unacceptable statements.
"""
    elif variant == "class_iii_critical":
        # Class III device, no data access contract mentioned
        content = """
Clinical Evaluation Report

1. INTENDED PURPOSE
The device is intended for implantable cardiac monitoring.

2. EQUIVALENCE
Equivalence is demonstrated with Predicate Device ABC.
Technical: design, specification.
Biological: material, biocompatibility.
Clinical: patient population, indication.
No predicate named explicitly in detail.
"""
    elif variant == "cross_domain_conflict":
        # Intended purpose says pediatric, but benefit-risk body does not mention pediatric.
        # All benefit-risk checks pass (no severity halt), but cross-domain conflict
        # detection flags the pediatric scope mismatch.
        content = """
Clinical Evaluation Report

1. INTENDED PURPOSE
The device is intended for pediatric lesion treatment in children under 12.

2. EQUIVALENCE
Equivalence is demonstrated with Predicate Device XYZ.
Technical: design, specification, energy, software, manufacturing.
Biological: material, biocompatibility, contact, duration, sterilization.
Clinical: patient population, indication, user, use environment, clinical outcome.

3. BENEFIT-RISK
Clinical benefits outweigh residual risks.
Risks are acceptable. Benefits are documented.
Treatment success is high. Pain reduction is documented.
"""
    else:
        content = "Clinical Evaluation Report\n"
    path.write_text(content, encoding="utf-8")


def _run_scenario(tmpdir: Path, variant: str, device_class: str) -> dict:
    input_dir = tmpdir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    _write_cer_text(input_dir / "CER.txt", variant)

    profile_path = _write_project_profile(tmpdir, f"DAG-{variant.upper()}-{uuid.uuid4().hex[:6]}", device_class)

    runner = CERReviewRunner(
        repo_root=str(REPO_ROOT),
        workflow_path=str(REPO_ROOT / "backend" / "workflows" / "cer_review_workflow_v1.yaml"),
        project_profile_path=str(profile_path),
        input_root=str(input_dir),
        artifact_root_override=str(tmpdir / "artifacts"),
        run_mode="smoke-run",
    )

    result = runner.run()

    # Read halt artifact if present
    halt_artifact = {}
    halt_path = Path(result.artifact_root_actual) / "00_manifest" / "human_adjudication_halt.json"
    if halt_path.exists():
        halt_artifact = json.loads(halt_path.read_text())

    # Read cross-domain conflict artifact if present
    conflict_artifact = {}
    conflict_path = Path(result.artifact_root_actual) / "00_manifest" / "cross_domain_conflicts.json"
    if conflict_path.exists():
        conflict_artifact = json.loads(conflict_path.read_text())

    # Read equivalence report for Class III check
    eq_report = {}
    eq_path = Path(result.artifact_root_actual) / "05_lanes" / "equivalence_report.json"
    if eq_path.exists():
        eq_report = json.loads(eq_path.read_text())

    return {
        "variant": variant,
        "dag_available": _LANGGRAPH_AVAILABLE,
        "executed_steps": result.executed_steps,
        "halt_state": result.halt_state,
        "halt_artifact": halt_artifact,
        "conflict_artifact": conflict_artifact,
        "equivalence_report_findings": eq_report.get("findings", []),
        "equivalence_depth": eq_report.get("equivalence_depth", {}),
    }


def main() -> int:
    report: dict[str, Any] = {
        "langgraph_available": _LANGGRAPH_AVAILABLE,
        "scenarios": {},
        "overall_pass": False,
    }

    tmpdir = Path(tempfile.mkdtemp(prefix="cer_dag_test_"))
    try:
        # Scenario 1: Severity-based halt
        report["scenarios"]["severity_halt"] = _run_scenario(tmpdir / "s1", "severity_halt", "Class IIa")

        # Scenario 2: Class III critical finding
        report["scenarios"]["class_iii_critical"] = _run_scenario(tmpdir / "s2", "class_iii_critical", "Class III")

        # Scenario 3: Cross-domain conflict
        report["scenarios"]["cross_domain_conflict"] = _run_scenario(tmpdir / "s3", "cross_domain_conflict", "Class IIa")

        # Assertions
        s1 = report["scenarios"]["severity_halt"]
        s2 = report["scenarios"]["class_iii_critical"]
        s3 = report["scenarios"]["cross_domain_conflict"]

        checks = {
            "dag_executed": _LANGGRAPH_AVAILABLE,
            "s1_halted": s1["halt_state"] is not None,
            "s1_halted_node_is_gate_closure_or_before": (
                s1["halt_state"].get("halted_node") in (
                    "cer_intake", "cer_structure_compliance", "cer_intended_purpose",
                    "cer_cep_methodology", "cer_clinical_evidence_panel", "cer_ifu_sscp_label",
                    "cer_qa_gate", "cer_cear_style_finding_formatter", "cer_human_boundary"
                )
            ) if s1["halt_state"] else False,
            "s1_resume_from_node_present": (
                s1["halt_state"].get("resume_from_node") is not None
            ) if s1["halt_state"] else False,
            "s2_has_critical_finding": any(
                f.get("severity") == "critical" and "Data Access Contract" in f.get("item", "")
                for f in s2["equivalence_report_findings"]
            ),
            "s3_cross_domain_logged": len(s3.get("conflict_artifact", {}).get("conflicts", [])) > 0,
            "s3_has_pediatric_conflict": any(
                "pediatric" in c.get("description", "").lower()
                for c in s3.get("conflict_artifact", {}).get("conflicts", [])
            ),
        }

        report["checks"] = checks
        report["overall_pass"] = all(checks.values())

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
