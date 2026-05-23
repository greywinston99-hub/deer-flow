#!/usr/bin/env python3
"""Checkpoint DB maintenance script.

Performs retention-based cleanup of LangGraph SQLite checkpointer:
- Keeps N most recent checkpoints per (thread_id, checkpoint_ns)
- Deletes orphaned writes
- Runs VACUUM to reclaim space
- Generates JSON report

Usage:
    python backend/scripts/maintenance_checkpoint_db.py \
        --db-path backend/.deer-flow/checkpoints.db \
        --keep-per-thread 10 \
        --dry-run

    # Cron example (weekly, keep 20 checkpoints per thread)
    0 3 * * 0 cd /path/to/deer-flow && python backend/scripts/maintenance_checkpoint_db.py --keep-per-thread 20
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "backend" / ".deer-flow" / "checkpoints.db"


def analyze_db(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return current DB statistics."""
    cursor = conn.cursor()
    stats: dict[str, Any] = {}

    for table in ("checkpoints", "writes", "store", "store_migrations"):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        stats[f"{table}_rows"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints")
    stats["distinct_threads"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT checkpoint_ns) FROM checkpoints")
    stats["distinct_namespaces"] = cursor.fetchone()[0]

    # DB file size
    db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    stats["db_file_size_mb"] = round(db_path.stat().st_size / (1024 * 1024), 2)

    return stats


def cleanup_checkpoints(
    conn: sqlite3.Connection,
    keep_per_thread: int = 10,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete old checkpoints, keeping N most recent per (thread_id, checkpoint_ns)."""
    cursor = conn.cursor()
    deleted_checkpoints = 0
    deleted_writes = 0
    affected_threads: set[str] = set()

    # Find all (thread_id, checkpoint_ns) pairs
    cursor.execute("SELECT DISTINCT thread_id, checkpoint_ns FROM checkpoints")
    thread_ns_pairs = cursor.fetchall()

    for thread_id, checkpoint_ns in thread_ns_pairs:
        # Get checkpoint_ids to delete (all except the N most recent)
        # UUID v6 is time-sortable, so ORDER BY checkpoint_id DESC works
        cursor.execute(
            """
            SELECT checkpoint_id FROM checkpoints
            WHERE thread_id = ? AND checkpoint_ns = ?
            ORDER BY checkpoint_id DESC
            LIMIT -1 OFFSET ?
            """,
            (thread_id, checkpoint_ns, keep_per_thread),
        )
        to_delete = [row[0] for row in cursor.fetchall()]

        if not to_delete:
            continue

        affected_threads.add(thread_id)

        if dry_run:
            deleted_checkpoints += len(to_delete)
            # Estimate writes (can't know exact count without querying)
            cursor.execute(
                "SELECT COUNT(*) FROM writes WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id IN ({})".format(
                    ",".join("?" * len(to_delete))
                ),
                (thread_id, checkpoint_ns, *to_delete),
            )
            deleted_writes += cursor.fetchone()[0]
            continue

        # Delete writes first (foreign key-like dependency)
        cursor.execute(
            "DELETE FROM writes WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id IN ({})".format(
                ",".join("?" * len(to_delete))
            ),
            (thread_id, checkpoint_ns, *to_delete),
        )
        deleted_writes += cursor.rowcount

        # Delete checkpoints
        cursor.execute(
            "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id IN ({})".format(
                ",".join("?" * len(to_delete))
            ),
            (thread_id, checkpoint_ns, *to_delete),
        )
        deleted_checkpoints += cursor.rowcount

    return {
        "affected_threads": len(affected_threads),
        "deleted_checkpoints": deleted_checkpoints,
        "deleted_writes": deleted_writes,
    }


def vacuum_db(conn: sqlite3.Connection, dry_run: bool = False) -> dict[str, Any]:
    """Run VACUUM and return size change."""
    db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    size_before = db_path.stat().st_size

    if dry_run:
        return {
            "vacuumed": False,
            "dry_run": True,
            "size_before_mb": round(size_before / (1024 * 1024), 2),
        }

    conn.commit()  # VACUUM cannot run inside a transaction
    conn.execute("VACUUM")
    size_after = db_path.stat().st_size

    return {
        "vacuumed": True,
        "size_before_mb": round(size_before / (1024 * 1024), 2),
        "size_after_mb": round(size_after / (1024 * 1024), 2),
        "reclaimed_mb": round((size_before - size_after) / (1024 * 1024), 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Checkpoint DB maintenance")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to checkpoints.db (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--keep-per-thread",
        type=int,
        default=10,
        help="Number of most recent checkpoints to keep per (thread_id, namespace)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze but do not delete or vacuum",
    )
    parser.add_argument(
        "--skip-vacuum",
        action="store_true",
        help="Skip VACUUM step",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON report to this file",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not args.db_path.exists():
        logger.error("Database not found: %s", args.db_path)
        return 1

    conn = sqlite3.connect(str(args.db_path))
    conn.execute("PRAGMA foreign_keys = OFF")  # SQLite doesn't have real FKs here, but be safe

    report: dict[str, Any] = {
        "script": "maintenance_checkpoint_db",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(args.db_path),
        "dry_run": args.dry_run,
        "keep_per_thread": args.keep_per_thread,
    }

    # Phase 1: Analyze
    logger.info("Analyzing database: %s", args.db_path)
    report["before"] = analyze_db(conn)
    logger.info(
        "Before: %s checkpoints, %s writes, %s threads, %.1f MB",
        report["before"]["checkpoints_rows"],
        report["before"]["writes_rows"],
        report["before"]["distinct_threads"],
        report["before"]["db_file_size_mb"],
    )

    # Phase 2: Cleanup
    logger.info("Cleaning up old checkpoints (keep=%d per thread)...", args.keep_per_thread)
    cleanup_result = cleanup_checkpoints(conn, keep_per_thread=args.keep_per_thread, dry_run=args.dry_run)
    report["cleanup"] = cleanup_result
    logger.info(
        "Cleanup: %d checkpoints, %d writes deleted across %d threads",
        cleanup_result["deleted_checkpoints"],
        cleanup_result["deleted_writes"],
        cleanup_result["affected_threads"],
    )

    # Phase 3: Vacuum
    if not args.skip_vacuum:
        logger.info("Running VACUUM...")
        vacuum_result = vacuum_db(conn, dry_run=args.dry_run)
        report["vacuum"] = vacuum_result
        if vacuum_result.get("vacuumed"):
            logger.info(
                "VACUUM: %.1f MB → %.1f MB (reclaimed %.1f MB)",
                vacuum_result["size_before_mb"],
                vacuum_result["size_after_mb"],
                vacuum_result["reclaimed_mb"],
            )
        else:
            logger.info("VACUUM skipped (dry_run=%s)", args.dry_run)
    else:
        report["vacuum"] = {"skipped": True, "reason": "--skip-vacuum"}
        logger.info("VACUUM skipped (--skip-vacuum)")

    # Phase 4: Post-analysis
    if not args.dry_run:
        report["after"] = analyze_db(conn)
        logger.info(
            "After: %s checkpoints, %s writes, %.1f MB",
            report["after"]["checkpoints_rows"],
            report["after"]["writes_rows"],
            report["after"]["db_file_size_mb"],
        )

    report["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Output report
    report_json = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(report_json, encoding="utf-8")
        logger.info("Report written to: %s", args.output)
    else:
        print(report_json)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
