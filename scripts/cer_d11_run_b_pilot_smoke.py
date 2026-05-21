#!/usr/bin/env python3
"""CER_D11 Run B: Native Limited Pilot Smoke Verification.

Executes CERReviewRunner directly with:
- mode: smoke-run (actual workflow execution)
- artifact_root: CER-D11-NATIVE-PILOT-SMOKE

Expected result:
- Native runtime path (direct import, no subprocess)
- workflow_id = cer_review_workflow_v1
- ordered_steps = 10 (D1 mode)
- Step 5 = cer_clinical_evidence_panel executes
- schema validation PASS
- NocoDB read/write/read-after-write (if enabled)
- Human Gate preserved
- pilot watermark applied
- no official CEAR
- no final decision
- backflow candidate-only
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import yaml

# Add backend packages to path
sys.path.insert(0, str(Path(__file__).parents[1] / "backend" / "packages" / "harness"))

from deerflow.runtime.cer_review import CERReviewRunner

REPO_ROOT = Path(__file__).parents[1].resolve()
WORKFLOW_PATH = REPO_ROOT / "backend" / "workflows" / "cer_review_workflow_v1.yaml"
BASE_PROJECT_PROFILE = REPO_ROOT / "artifacts" / "cer" / "CER-D6-REAL-PROJECT" / "project_profile.yaml"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "cer" / "CER-D11-NATIVE-PILOT-SMOKE" / "cer_review" / "cer-d11-native-pilot-smoke-001"
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

RUN_ID = "cer-d11-native-pilot-smoke-001"
MODE = "smoke-run"  # actual execution mode

def main() -> int:
    # Load base project profile for Run B
    base_profile = yaml.safe_load(BASE_PROJECT_PROFILE.read_text())

    # Override for Run B: smoke-run mode
    base_profile["project_id"] = "CER-D11-NATIVE-PILOT-SMOKE"
    base_profile["cer_run_id"] = RUN_ID
    base_profile["project_protocol"]["project_id"] = "CER-D11-NATIVE-PILOT-SMOKE"
    base_profile["project_protocol"]["cer_run_id"] = RUN_ID
    base_profile["artifact_policy"]["artifact_root"] = str(ARTIFACT_ROOT / "${run_id}")

    # Write temp project profile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, prefix='cer_d11_run_b_') as f:
        yaml.safe_dump(base_profile, f)
        temp_profile_path = Path(f.name)

    print(f"Run B: Native Limited Pilot Smoke")
    print(f"  mode: {MODE}")
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
            thread_id="cer-d11-native-pilot-smoke",
            artifact_root_override=ARTIFACT_ROOT,
        )

        print(f"  runner.workflow_mode: {runner.workflow_mode}")
        print(f"  runner.gate_a_status: {runner.gate_a_status}")
        ordered_steps = runner.workflow.get("ordered_steps", [])
        print(f"  ordered_steps count: {len(ordered_steps)}")
        step_ids = [s.get("step_id") for s in ordered_steps]
        print(f"  step_ids: {step_ids}")
        if len(step_ids) >= 5:
            print(f"  Step 5: {step_ids[4]}")
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

        # Check run_context.json
        run_context_path = ARTIFACT_ROOT / "00_manifest" / "run_context.json"
        if run_context_path.exists():
            ctx = json.loads(run_context_path.read_text())
            print(f"Run context: {json.dumps(ctx, indent=2)}")
        print()

        # Check artifact index
        artifact_index_path = ARTIFACT_ROOT / "00_manifest" / "artifact_index.json"
        if artifact_index_path.exists():
            idx = json.loads(artifact_index_path.read_text())
            print(f"Artifact index: {idx.get('total', 0)} artifacts")
        print()

        # Check task ledger
        task_ledger_path = ARTIFACT_ROOT / "00_manifest" / "task_ledger.json"
        if task_ledger_path.exists():
            ledger = json.loads(task_ledger_path.read_text())
            print(f"Task ledger entries: {len(ledger.get('entries', []))}")
            for entry in ledger.get('entries', []):
                print(f"  - run_id={entry.get('run_id')}, status={entry.get('status')}")

        # Check event log
        event_log_path = ARTIFACT_ROOT / "00_manifest" / "event_log.json"
        if event_log_path.exists():
            events = json.loads(event_log_path.read_text())
            print(f"Event log entries: {len(events.get('events', []))}")
            for event in events.get('events', []):
                print(f"  - {event.get('event_type')}: {event.get('run_id', 'N/A')}")

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
