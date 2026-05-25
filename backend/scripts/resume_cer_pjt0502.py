#!/usr/bin/env python3
"""Resume CER-PJT-0502 from human adjudication halt."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow")
PKG_ROOT = REPO_ROOT / "backend" / "packages" / "harness"
sys.path.insert(0, str(PKG_ROOT))

from deerflow.runtime.cer_review.runner import CERReviewRunner


def main() -> int:
    project_profile = REPO_ROOT / "artifacts" / "cer" / "CER-PJT-0502" / "project_profile.yaml"
    input_root = REPO_ROOT / "artifacts" / "cer" / "CER-PJT-0502" / "input"
    artifact_root = REPO_ROOT / "artifacts" / "cer" / "CER-PJT-0502" / "round_001" / "artifacts"
    workflow_path = REPO_ROOT / "backend" / "workflows" / "cer_review_workflow_v1.yaml"

    # Read halt artifact for resume metadata
    halt_path = artifact_root / "00_manifest" / "human_adjudication_halt.json"
    halt_data = json.loads(halt_path.read_text())
    resume_from_node = halt_data["resume_from_node"]
    run_id = "cer-run-6953c2b7"

    print(f"Resuming CER review {run_id} from node: {resume_from_node}")
    print(f"Artifact root: {artifact_root}")

    runner = CERReviewRunner(
        repo_root=str(REPO_ROOT),
        workflow_path=str(workflow_path),
        project_profile_path=str(project_profile),
        input_root=str(input_root),
        artifact_root_override=str(artifact_root),
        run_mode="smoke-run",
        resume_from_node=resume_from_node,
        run_id_override=run_id,
    )

    result = runner.run()

    report = {
        "run_id": run_id,
        "resume_from_node": resume_from_node,
        "executed_steps": result.executed_steps,
        "halt_state": result.halt_state,
        "artifact_root_actual": str(result.artifact_root_actual),
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Check if we reached gate closure
    gate_closure_reached = "cer_gate_closure" in result.executed_steps or "cer_gate_closure_agent_v1" in result.executed_steps
    if gate_closure_reached:
        print("\n✅ Gate closure reached. Workflow completed.")
    elif result.halt_state:
        print(f"\n⚠️  Workflow halted again: {result.halt_state}")
    else:
        print("\n⚠️  Workflow ended without reaching gate closure.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
