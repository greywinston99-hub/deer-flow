#!/usr/bin/env python3
"""CER_D11 Runner — Gate A Block & Pilot Smoke Verification.

Usage:
  python scripts/cer_d11_runner.py --mode gate-a-block
  python scripts/cer_d11_runner.py --mode pilot-smoke
"""

from __future__ import annotations

import argparse, json, sys, tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parents[1] / "backend" / "packages" / "harness"))
from deerflow.runtime.cer_review import CERReviewRunner

REPO_ROOT = Path(__file__).parents[1].resolve()
WORKFLOW_PATH = REPO_ROOT / "backend" / "workflows" / "cer_review_workflow_v1.yaml"
BASE_PROJECT_PROFILE = REPO_ROOT / "artifacts" / "cer" / "CER-D6-REAL-PROJECT" / "project_profile.yaml"

MODE_CONFIG = {
    "gate-a-block": {
        "label": "Run A: Native Gate A Block",
        "run_mode": "formal-review",
        "project_id": "CER-D11-NATIVE-GATE-A-BLOCK",
        "run_id": "cer-d11-native-gate-a-block-001",
        "thread_id": "cer-d11-native-gate-a-block",
        "artifact_subdir": "CER-D11-NATIVE-GATE-A-BLOCK",
        "gate_a_override": {"gate_a_status": "draft", "gate_a_accepted": False},
        "expected_checks": ["gate_a_blocked"],
    },
    "pilot-smoke": {
        "label": "Run B: Native Limited Pilot Smoke",
        "run_mode": "smoke-run",
        "project_id": "CER-D11-NATIVE-PILOT-SMOKE",
        "run_id": "cer-d11-native-pilot-smoke-001",
        "thread_id": "cer-d11-native-pilot-smoke",
        "artifact_subdir": "CER-D11-NATIVE-PILOT-SMOKE",
        "gate_a_override": None,
        "expected_checks": ["run_context", "artifact_index"],
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="CER_D11 verification runner")
    parser.add_argument(
        "--mode",
        choices=list(MODE_CONFIG.keys()),
        required=True,
        help="Test mode: gate-a-block or pilot-smoke",
    )
    args = parser.parse_args()
    cfg = MODE_CONFIG[args.mode]

    artifact_root = (
        REPO_ROOT / "artifacts" / "cer" / cfg["artifact_subdir"] / "cer_review" / cfg["run_id"]
    )
    artifact_root.mkdir(parents=True, exist_ok=True)

    # Load and customize base profile
    base_profile = yaml.safe_load(BASE_PROJECT_PROFILE.read_text())
    base_profile["project_id"] = cfg["project_id"]
    base_profile["cer_run_id"] = cfg["run_id"]
    base_profile["project_protocol"]["project_id"] = cfg["project_id"]
    base_profile["project_protocol"]["cer_run_id"] = cfg["run_id"]
    base_profile["artifact_policy"]["artifact_root"] = str(artifact_root / "${run_id}")

    if cfg["gate_a_override"]:
        base_profile["gate_a_status"] = cfg["gate_a_override"]["gate_a_status"]
        base_profile["gate_a_accepted"] = cfg["gate_a_override"]["gate_a_accepted"]
        base_profile["project_protocol"]["gate_a_status"] = cfg["gate_a_override"]["gate_a_status"]
        base_profile["project_protocol"]["formal_review_requested"] = True

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, prefix=f"cer_d11_{args.mode}_"
    ) as f:
        yaml.safe_dump(base_profile, f)
        temp_profile_path = Path(f.name)

    print(f"{cfg['label']}")
    print(f"  mode: {cfg['run_mode']}")
    if cfg["gate_a_override"]:
        print(f"  gate_a_status: {cfg['gate_a_override']['gate_a_status']}")
    print(f"  artifact_root: {artifact_root}")
    print(f"  temp_profile: {temp_profile_path}")
    print()

    try:
        runner = CERReviewRunner(
            repo_root=REPO_ROOT,
            workflow_path=WORKFLOW_PATH,
            project_profile_path=temp_profile_path,
            run_mode=cfg["run_mode"],
            run_id_override=cfg["run_id"],
            thread_id=cfg["thread_id"],
            artifact_root_override=artifact_root,
        )

        if cfg["gate_a_override"]:
            print(f"  runner.gate_a_status: {runner.gate_a_status}")
        print(f"  runner.workflow_mode: {runner.workflow_mode}")

        if args.mode == "pilot-smoke":
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

        # Mode-specific output verification
        if args.mode == "gate-a-block":
            _verify_gate_a_block(artifact_root)
        elif args.mode == "pilot-smoke":
            _verify_pilot_smoke(artifact_root)

        # Common verifications
        _verify_common(artifact_root)
        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        temp_profile_path.unlink(missing_ok=True)


def _verify_gate_a_block(artifact_root: Path) -> None:
    gate_a_blocked_path = artifact_root / "00_manifest" / "gate_a_blocked.json"
    if gate_a_blocked_path.exists():
        blocked = json.loads(gate_a_blocked_path.read_text())
        print(f"Gate A Blocked artifact: {blocked.get('final_status')}")
        print(f"  blocked_reason: {blocked.get('blocked_reason')}")
    else:
        print("ERROR: gate_a_blocked.json NOT FOUND")


def _verify_pilot_smoke(artifact_root: Path) -> None:
    run_context_path = artifact_root / "00_manifest" / "run_context.json"
    if run_context_path.exists():
        ctx = json.loads(run_context_path.read_text())
        print(f"Run context: {json.dumps(ctx, indent=2)}")
    else:
        print("WARNING: run_context.json not found")

    artifact_index_path = artifact_root / "00_manifest" / "artifact_index.json"
    if artifact_index_path.exists():
        idx = json.loads(artifact_index_path.read_text())
        print(f"Artifact index: {idx.get('total', 0)} artifacts")
    else:
        print("WARNING: artifact_index.json not found")


def _verify_common(artifact_root: Path) -> None:
    task_ledger_path = artifact_root / "00_manifest" / "task_ledger.json"
    if task_ledger_path.exists():
        ledger = json.loads(task_ledger_path.read_text())
        print(f"Task ledger entries: {len(ledger.get('entries', []))}")
        for entry in ledger.get("entries", []):
            print(f"  - status={entry.get('status')}, "
                  f"data={entry.get('final_status', entry.get('run_id', 'N/A'))}")

    event_log_path = artifact_root / "00_manifest" / "event_log.json"
    if event_log_path.exists():
        events = json.loads(event_log_path.read_text())
        print(f"Event log entries: {len(events.get('events', []))}")
        for event in events.get("events", []):
            print(f"  - {event.get('event_type')}: "
                  f"{event.get('final_status', event.get('reason', event.get('run_id', 'N/A')))}")


if __name__ == "__main__":
    sys.exit(main())
