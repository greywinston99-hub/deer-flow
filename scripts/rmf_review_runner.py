#!/usr/bin/env python3
"""Executable entrypoint for the minimal RMF review runner glue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_ROOT = REPO_ROOT / "backend" / "packages" / "harness"
if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))

from deerflow.runtime.rmf_review import RMFReviewRunner  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the minimal RMF Review Workflow v1.1 glue.")
    parser.add_argument(
        "--workflow",
        default=str(REPO_ROOT / "workflows" / "rmf_review_v1_1.yaml"),
        help="Path to the workflow yaml.",
    )
    parser.add_argument(
        "--project-profile",
        required=True,
        help="Path to project_profile.yaml.",
    )
    parser.add_argument(
        "--input-root",
        help="Optional override for the input root. Defaults to project_profile.input_package.root_path.",
    )
    parser.add_argument(
        "--thread-id",
        help="Optional DeerFlow thread id for artifact placement.",
    )
    parser.add_argument(
        "--mode",
        choices=("dry-run", "smoke-run", "closure-only"),
        default="smoke-run",
        help="dry-run validates and writes the run plan; smoke-run executes all nodes; closure-only runs only the gate closure step.",
    )
    parser.add_argument(
        "--artifact-root-override",
        help="Absolute path to existing artifact root (for closure-only mode).",
    )
    parser.add_argument(
        "--run-id-override",
        help="Run ID to reuse (for closure-only mode).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    runner_kwargs: dict[str, object] = {
        "repo_root": REPO_ROOT,
        "workflow_path": args.workflow,
        "project_profile_path": args.project_profile,
        "input_root": args.input_root,
        "thread_id": args.thread_id,
    }
    if args.artifact_root_override:
        runner_kwargs["artifact_root_override"] = args.artifact_root_override
    if args.run_id_override:
        runner_kwargs["run_id_override"] = args.run_id_override
    runner = RMFReviewRunner(**runner_kwargs)
    result = runner.run(mode=args.mode)
    print(
        json.dumps(
            {
                "thread_id": result.thread_id,
                "run_id": result.run_id,
                "mode": result.mode,
                "workflow_name": result.workflow_name,
                "executed_steps": result.executed_steps,
                "artifact_root_virtual": result.artifact_root_virtual,
                "artifact_root_actual": result.artifact_root_actual,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
