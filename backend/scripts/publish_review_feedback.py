#!/usr/bin/env python3
"""Publish CER Review findings as advisory feedback for Authoring pipeline.

Usage:
    # Auto-detect review artifacts and publish feedback
    python backend/scripts/publish_review_feedback.py \
        --review-artifacts artifacts/cer/{project_id}/round_{round_id}

    # Target a specific Authoring project
    python backend/scripts/publish_review_feedback.py \
        --review-artifacts artifacts/cer/{project_id}/round_{round_id} \
        --authoring-project {authoring_project_id}

    # Dry-run (preview without writing)
    python backend/scripts/publish_review_feedback.py \
        --review-artifacts artifacts/cer/{project_id}/round_{round_id} \
        --dry-run

This script is the manual/CI bridge between Review and Authoring pipelines.
It is idempotent — running multiple times overwrites the same feedback file.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "harness"))

from deerflow.runtime.cer_review.feedback_writer import ReviewFeedbackWriter

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Review feedback for Authoring")
    parser.add_argument("--review-artifacts", required=True, help="Path to Review artifact root")
    parser.add_argument("--authoring-project", default="", help="Target Authoring project ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview feedback without writing")
    parser.add_argument("--source", default="cer_review_v1", help="Feedback source identifier")
    args = parser.parse_args()

    review_root = Path(args.review_artacts).expanduser().resolve()
    if not review_root.exists():
        logger.error("Review artifact root not found: %s", review_root)
        return 2

    # Detect review_package.json
    review_package_candidates = [
        review_root / "06_review_package" / "review_package.json",
        review_root / "10_gate_closure" / "review_package.json",
    ]
    review_package_path = next((p for p in review_package_candidates if p.exists()), None)

    if review_package_path is None:
        logger.error("No review_package.json found in %s", review_root)
        return 2

    logger.info("Detected review package: %s", review_package_path)

    # Determine target Authoring artifact root
    if args.authoring_project:
        authoring_root = Path("artifacts/cer_authoring") / args.authoring_project
    else:
        # Default: write feedback into the Review artifact root itself
        # Authoring will read from review_feedback/latest.json relative to its own artifact_root
        authoring_root = review_root

    writer = ReviewFeedbackWriter(authoring_root)

    if args.dry_run:
        with open(review_package_path, encoding="utf-8") as fh:
            package = json.load(fh)
        findings = writer._extract_findings_from_package(package)
        feedback = writer._build_feedback(findings, args.source, args.authoring_project or None)
        print(json.dumps(feedback, indent=2, ensure_ascii=False))
        logger.info("Dry-run: %d findings would be written to %s/review_feedback/latest.json", len(findings), authoring_root)
        return 0

    feedback_path = writer.write_feedback_from_review_package(
        review_package_path,
        source_project_id=args.authoring_project or None,
    )
    if feedback_path:
        logger.info("Feedback published: %s", feedback_path)
        return 0
    logger.error("Failed to publish feedback")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
