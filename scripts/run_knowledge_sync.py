#!/usr/bin/env python3
"""CLI entrypoint for manually triggering the Wave 5 Knowledge Sync Dispatcher.

Usage:
    python scripts/run_knowledge_sync.py
    python scripts/run_knowledge_sync.py --project-id PROJ-123
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_ROOT = REPO_ROOT / "backend" / "packages" / "harness"
if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))

from deerflow.knowledge.sync_dispatcher import KnowledgeSyncDispatcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trigger Knowledge Sync Dispatcher (Wave 5)")
    parser.add_argument(
        "--project-id",
        help="Optional project ID to filter assets. If omitted, all approved assets are dispatched.",
    )
    parser.add_argument(
        "--knowledge-store-root",
        default=str(REPO_ROOT / "artifacts" / "cer" / "knowledge_store"),
        help="Root path to the knowledge store directory.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    dispatcher = KnowledgeSyncDispatcher(
        knowledge_store_root=Path(args.knowledge_store_root)
    )
    result = dispatcher.dispatch_approved_assets(project_id=args.project_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
