#!/usr/bin/env python3
"""CER_D11 Run A: Native Gate A Block Verification.

Executes CERReviewRunner directly with:
- mode: formal-review
- gate_a_status: draft (should block formal review)
- artifact_root: CER-D11-NATIVE-GATE-A-BLOCK

Expected result:
- final_status = FORMAL_REVIEW_BLOCKED_GATE_A_NOT_ACCEPTED
- gate_a_blocked.json generated
- No downstream steps executed
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import yaml  # noqa: F401

# Add backend packages to path
sys.path.insert(0, str(Path(__file__).parents[1] / "backend" / "packages" / "harness"))

from deerflow.runtime.cer_review import CERReviewRunner
from deerflow.config.paths import get_paths

REPO_ROOT = Path(__file__).parents[1].resolve()
WORKFLOW_PATH = REPO_ROOT / "backend" / "workflows" / "cer_review_workflow_v1.yaml"
BASE_PROJECT_PROFILE = REPO_ROOT / "artifacts" / "cer" / "CER-D6-REAL-PROJECT" / "project_profile.yaml"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "cer" / "CER-D11-NATIVE-GATE-A-BLOCK" / "cer_review" / "cer-d11-native-gate-a-block-001"
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

RUN_ID = "cer-d11-native-gate-a-block-001"
MODE = "formal-review"

def main() -> int:
    # Load base project profile and modify for Run A
    base_profile = yaml.safe_load(BASE_PROJECT_PROFILE.read_text())

    # Override for Run A: gate_a_status = draft
    base_profile["gate_a_status"] = "draft"
    base_profile["gate_a_accepted"] = False
    base_profile["project_protocol"]["gate_a_status"] = "draft"
    base_profile["project_protocol"]["formal_review_requested"] = True
    base_profile["project_id"] = "CER-D11-NATIVE-GATE-A-BLOCK"
    base_profile["cer_run_id"] = RUN_ID
    base_profile["project_protocol"]["project_id"] = "CER-D11-NATIVE-GATE-A-BLOCK"
    base_profile["project_protocol"]["cer_run_id"] = RUN_ID
    base_profile["artifact_policy"]["artifact_root"] = str(ARTIFACT_ROOT / "${run_id}")

    # Write temp project profile as YAML
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, prefix='cer_d11_run_a_') as f:
        yaml.safe_dump(base_profile, f)
        temp_profile_path = Path(f.name)

    print(f"Run A: Native Gate A Block")
    print(f"  mode: {MODE}")
    print(f"  gate_a_status: draft")
    print(f"  artifact_root: {ARTIFACT_ROOT}")
    print(f"  temp_profile: {temp_profile_path}")
    print()

    try:
        runner = CERReviewRunner(
            repo_root=REPO_ROOT,
            workflow_path=WORKFLOW_PATH,
            project_profile_path=temp_profile_path,
            run_mode=MODE,
            run_id_override=RUN_ID,
            thread_id="cer-d11-native-gate-a-block",
            artifact_root_override=ARTIFACT_ROOT,
        )

        print(f"  runner.gate_a_status: {runner.gate_a_status}")
        print(f"  runner.workflow_mode: {runner.workflow_mode}")
        print()

        result = runner.run()

        print(f"Result:")
        print(f"  thread_id: {result.thread_id}")
        print(f"  run_id: {result.run_id}")
        print(f"  mode: {result.mode}")
        print(f"  workflow_name: {result.workflow_name}")
        print(f"  executed_steps: {result.executed_steps}")
        print(f"  artifact_root_actual: {result.artifact_root_actual}")
        print()

        # Check gate_a_blocked.json
        gate_a_blocked_path = ARTIFACT_ROOT / "00_manifest" / "gate_a_blocked.json"
        if gate_a_blocked_path.exists():
            blocked = json.loads(gate_a_blocked_path.read_text())
            print(f"Gate A Blocked artifact: {blocked.get('final_status')}")
            print(f"  blocked_reason: {blocked.get('blocked_reason')}")
        else:
            print("ERROR: gate_a_blocked.json NOT FOUND")

        # Check task_ledger
        task_ledger_path = ARTIFACT_ROOT / "00_manifest" / "task_ledger.json"
        if task_ledger_path.exists():
            ledger = json.loads(task_ledger_path.read_text())
            print(f"Task ledger entries: {len(ledger.get('entries', []))}")
            for entry in ledger.get('entries', []):
                print(f"  - status={entry.get('status')}, data={entry.get('final_status', 'N/A')}")

        # Check event_log
        event_log_path = ARTIFACT_ROOT / "00_manifest" / "event_log.json"
        if event_log_path.exists():
            events = json.loads(event_log_path.read_text())
            print(f"Event log entries: {len(events.get('events', []))}")
            for event in events.get('events', []):
                print(f"  - {event.get('event_type')}: {event.get('final_status', event.get('reason', 'N/A'))}")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        temp_profile_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
