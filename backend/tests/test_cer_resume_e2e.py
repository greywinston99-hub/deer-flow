"""test_cer_resume_e2e.py — Full E2E: start → halt → resume → complete.

Runs a CER workflow with a document that triggers a severity-based halt,
then resumes from the human adjudication checkpoint and verifies the
workflow completes through cer_gate_closure.

Outputs a single JSON object to stdout with verdict.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

# Ensure runner imports resolve
REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_ROOT = REPO_ROOT / "backend" / "packages" / "harness"
sys.path.insert(0, str(PKG_ROOT))

from deerflow.runtime.cer_review.runner import CERReviewRunner, _LANGGRAPH_AVAILABLE


_CER_TEXT_HALT = """
Clinical Evaluation Report

1. INTENDED PURPOSE
The device is intended for pediatric lesion treatment.

2. EQUIVALENCE
Equivalence is demonstrated with Predicate Device XYZ.
Technical: design, specification, energy, software, manufacturing.
Biological: material, biocompatibility, contact, duration, sterilization.
Clinical: patient population, indication, user, use environment, clinical outcome.

3. BENEFIT-RISK
ALARP (As Low As Reasonably Practicable) has been applied.
No explicit acceptable or unacceptable statements.
Benefits are documented but not specific.
"""


def _write_project_profile(tmpdir: Path, project_id: str) -> Path:
    import yaml
    profile = {
        "project_id": project_id,
        "project_name": f"Resume E2E {project_id}",
        "institution_profile": {"organization": "Test Org", "assessment_body": "Test Body"},
        "review_scope": {"mode": "smoke_precheck", "review_language": "en", "jurisdiction": "EU MDR"},
        "primary_review_object": "CER",
        "device_context": {
            "device_name": "Test Device",
            "device_family": "Test Family",
            "device_class": "Class IIa",
            "intended_use": "Test device for pediatric lesion treatment.",
            "market_stage": "technical_documentation_review",
            "implantable_status": False,
            "intended_purpose_confirmed": True,
        },
        "project_protocol": {
            "project_id": project_id,
            "product_name": "Test Device",
            "device_class": "Class IIa",
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
    path.write_text(yaml.dump(profile), encoding="utf-8")
    return path


def main() -> int:
    report: dict = {
        "langgraph_available": _LANGGRAPH_AVAILABLE,
        "pass": False,
    }

    tmpdir = Path(tempfile.mkdtemp(prefix="cer_resume_e2e_"))
    try:
        input_dir = tmpdir / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        (input_dir / "CER.txt").write_text(_CER_TEXT_HALT, encoding="utf-8")

        profile_path = _write_project_profile(tmpdir, f"RESUME-E2E-{uuid.uuid4().hex[:6]}")

        # Step 1: Start the run (expect halt before gate_closure)
        runner_start = CERReviewRunner(
            repo_root=str(REPO_ROOT),
            workflow_path=str(REPO_ROOT / "backend" / "workflows" / "cer_review_workflow_v1.yaml"),
            project_profile_path=str(profile_path),
            input_root=str(input_dir),
            artifact_root_override=str(tmpdir / "artifacts"),
            run_mode="smoke-run",
        )
        result_start = runner_start.run()

        report["start_executed_steps"] = result_start.executed_steps
        report["halt_state"] = result_start.halt_state

        # Verify halt occurred
        assert result_start.halt_state is not None, "Expected workflow to halt, but it did not"
        assert result_start.halt_state.get("status") == "human_adjudication_pending", "Expected human_adjudication_pending"

        # Read halt artifact for resume_from_node
        halt_path = Path(result_start.artifact_root_actual) / "00_manifest" / "human_adjudication_halt.json"
        halt_data = json.loads(halt_path.read_text())
        resume_from_node = halt_data.get("resume_from_node")
        halted_after_step = halt_data.get("halted_after_step")

        report["halted_after_step"] = halted_after_step
        report["resume_from_node"] = resume_from_node

        assert resume_from_node is not None, "Expected resume_from_node in halt artifact"

        # Step 2: Resume the run
        runner_resume = CERReviewRunner(
            repo_root=str(REPO_ROOT),
            workflow_path=str(REPO_ROOT / "backend" / "workflows" / "cer_review_workflow_v1.yaml"),
            project_profile_path=str(profile_path),
            input_root=str(input_dir),
            artifact_root_override=str(tmpdir / "artifacts"),
            run_mode="smoke-run",
            resume_from_node=resume_from_node,
            run_id_override=result_start.run_id,
        )
        result_resume = runner_resume.run()

        report["resume_executed_steps"] = result_resume.executed_steps
        report["resume_halt_state"] = result_resume.halt_state

        # Step 3: Verify completion through gate_closure
        all_steps = result_start.executed_steps + result_resume.executed_steps
        report["all_executed_steps"] = all_steps

        gate_closure_reached = "cer_gate_closure" in all_steps or "cer_gate_closure_agent_v1" in all_steps
        report["gate_closure_reached"] = gate_closure_reached

        # Resume signal artifact should exist
        resume_signal_path = Path(result_start.artifact_root_actual) / "00_manifest" / "resume_signal.json"
        report["resume_signal_exists"] = resume_signal_path.exists()

        # Final verdict
        checks = {
            "started_and_halted": result_start.halt_state is not None,
            "resume_node_present": resume_from_node is not None,
            "resumed_without_new_halt": result_resume.halt_state is None,
            "gate_closure_reached": gate_closure_reached,
            "resume_signal_written": resume_signal_path.exists(),
        }
        report["checks"] = checks
        report["pass"] = all(checks.values())

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
