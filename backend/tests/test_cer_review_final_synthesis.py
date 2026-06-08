from pathlib import Path
import json

from deerflow.runtime.cer_review import CERReviewRunner


REPO_ROOT = Path(__file__).resolve().parents[1].parent


def test_review_runner_expands_brace_run_id_and_writes_final_synthesis(tmp_path: Path) -> None:
    runner = CERReviewRunner(
        repo_root=REPO_ROOT,
        workflow_path=REPO_ROOT / "backend" / "workflows" / "cer_review_workflow_v1.yaml",
        project_profile_path=REPO_ROOT / "examples" / "cer_review" / "project_profile.example.yaml",
        artifact_root_override=tmp_path / "{run_id}",
        run_id_override="cer-run-test1234",
        thread_id="review-final-synthesis-test",
        run_mode="smoke-run",
    )
    assert "{run_id}" not in str(runner.artifact_root_actual)
    runner._write_json(
        runner._artifact_path("05_lanes", "panel_summary.json"),
        {
            "findings": [
                {"finding_id": "F-001", "severity": "critical", "description": "Blocking finding"},
                {"finding_id": "F-002", "severity": "major", "description": "Major finding"},
            ]
        },
    )
    synthesis = runner._write_final_synthesis(executed_steps=["cer_clinical_evidence_panel"])
    assert synthesis["decision"] == "REWORK_REQUIRED"
    assert synthesis["critical"] == 1
    assert (runner.artifact_root_actual / "final_synthesis.json").exists()
    assert (runner.artifact_root_actual / "12_final_synthesis" / "final_synthesis.json").exists()


def test_closure_only_final_synthesis_flags_authoring_human_hold(tmp_path: Path) -> None:
    input_root = tmp_path / "review_input"
    input_root.mkdir()
    (input_root / "final_gate_closure_report.json").write_text(
        json.dumps({"decision": "HUMAN_HOLD"}),
        encoding="utf-8",
    )
    (input_root / "source_preflight_gate_report.json").write_text(
        json.dumps({"status": "BLOCKED", "blocking_issues": [{"issue_id": "IFU-P0"}]}),
        encoding="utf-8",
    )
    profile = tmp_path / "project_profile.yaml"
    profile.write_text(
        "\n".join(
            [
                "project_id: closure-blocked",
                "input_package:",
                f"  root_path: {input_root}",
            ]
        ),
        encoding="utf-8",
    )
    runner = CERReviewRunner(
        repo_root=REPO_ROOT,
        workflow_path=REPO_ROOT / "backend" / "workflows" / "cer_review_workflow_v1.yaml",
        project_profile_path=profile,
        artifact_root_override=tmp_path / "review" / "{run_id}",
        run_id_override="cer-run-blocked",
        thread_id="review-blocked-synthesis-test",
        run_mode="closure-only",
    )
    synthesis = runner._write_final_synthesis(executed_steps=["cer_gate_closure_agent"])
    assert synthesis["decision"] == "REWORK_REQUIRED"
    assert synthesis["critical"] == 1
    assert synthesis["authoring_blocked_context"]["source_preflight_status"] == "BLOCKED"
