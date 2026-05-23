#!/usr/bin/env python3
"""Standalone Review Quick-Scan runner.

Triggered by Authoring pipeline when a mid-pipeline review is requested.
Produces review_feedback/quick_scan_latest.json without blocking Authoring.

Usage:
    python backend/scripts/run_review_quick_scan.py \
        --input-dir artifacts/cer/PROJ \
        --output-dir artifacts/cer/PROJ
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add harness to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "harness"))

from deerflow.runtime.cer_review.review_assist_lead_agent import (
    ReviewAssistState,
    build_review_quick_scan_graph,
)

logger = logging.getLogger(__name__)


async def run_quick_scan(input_dir: Path, output_dir: Path, project_id: str = "") -> dict:
    """Run the 2-stage quick-scan graph on input artifacts."""
    artifact_root = output_dir
    artifact_root.mkdir(parents=True, exist_ok=True)

    # Initialize state
    initial_state: ReviewAssistState = {
        "project_id": project_id,
        "artifact_root": str(artifact_root),
        "input_root": str(input_dir),
        "review_session_id": f"quick-scan-{project_id}",
        "current_stage": None,
        "stage_result": None,
        "flavor_profile": "FAST_GAP_TRIAGE",
        "stage_results": [],
        "state_machine": None,
        "status": None,
        "inline_file_context": "",
        "stage_data": {},
    }

    graph = build_review_quick_scan_graph()

    # Run graph (simplified — no checkpointer for quick scan)
    try:
        result = await graph.ainvoke(initial_state)
        feedback_path = artifact_root / "review_feedback" / "quick_scan_latest.json"
        if feedback_path.exists():
            feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
            return {
                "status": "completed",
                "findings_count": len(feedback.get("findings", [])),
                "feedback_path": str(feedback_path),
            }
        return {"status": "completed", "findings_count": 0, "feedback_path": None}
    except Exception as exc:
        logger.exception("Quick-scan failed")
        return {"status": "failed", "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Review Quick-Scan")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--project-id", type=str, default="")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(run_quick_scan(args.input_dir, args.output_dir, args.project_id))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
