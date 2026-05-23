#!/usr/bin/env python3
"""Unified maintenance cron entrypoint for DeerFlow CER pipeline.

Runs weekly (recommended) or on-demand:
- Checkpoint DB retention cleanup
- Expired review_feedback cleanup
- Disk usage monitoring with threshold alerts
- Persistent JSON report generation

Usage:
    # Cron (weekly Sunday 03:00)
    0 3 * * 0 cd /path/to/deer-flow && python backend/scripts/maintenance_cron.py

    # Manual with custom thresholds
    python backend/scripts/maintenance_cron.py \
        --disk-threshold 75 \
        --keep-per-thread 15 \
        --artifact-root ./artifacts

    # Dry-run
    python backend/scripts/maintenance_cron.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "backend" / ".deer-flow" / "checkpoints.db"
DEFAULT_ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / "artifacts" / "maintenance"


def check_disk_usage(threshold_percent: int = 80, paths: list[Path] | None = None) -> dict[str, Any]:
    """Check disk usage for configured paths. Alert if above threshold."""
    paths = paths or [Path("/"), Path(__file__).resolve().parents[2]]
    alerts: list[dict[str, Any]] = []
    ok: list[dict[str, Any]] = []

    for p in paths:
        try:
            total, used, free = shutil.disk_usage(str(p))
            pct = round(used / total * 100, 1)
            entry = {
                "path": str(p),
                "total_gb": round(total / (1024 ** 3), 2),
                "used_gb": round(used / (1024 ** 3), 2),
                "free_gb": round(free / (1024 ** 3), 2),
                "usage_percent": pct,
            }
            if pct >= threshold_percent:
                entry["alert"] = True
                alerts.append(entry)
                logger.warning("DISK ALERT: %s at %.1f%% (threshold %d%%)", p, pct, threshold_percent)
            else:
                entry["alert"] = False
                ok.append(entry)
                logger.info("Disk OK: %s at %.1f%%", p, pct)
        except Exception as exc:
            alerts.append({"path": str(p), "error": str(exc), "alert": True})
            logger.error("Disk check failed for %s: %s", p, exc)

    return {
        "threshold_percent": threshold_percent,
        "paths_checked": len(paths),
        "alerts": alerts,
        "ok": ok,
        "alert_count": len(alerts),
    }


def run_checkpoint_maintenance(
    db_path: Path,
    keep_per_thread: int,
    dry_run: bool,
) -> dict[str, Any]:
    """Delegate to maintenance_checkpoint_db.py."""
    script = Path(__file__).resolve().parent / "maintenance_checkpoint_db.py"
    cmd = [
        sys.executable,
        str(script),
        "--db-path", str(db_path),
        "--keep-per-thread", str(keep_per_thread),
    ]
    if dry_run:
        cmd.append("--dry-run")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode == 0:
            # Parse JSON report from stdout
            lines = proc.stdout.strip().splitlines()
            for line in reversed(lines):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
            return {"status": "unknown_output", "stdout_preview": proc.stdout[:500]}
        else:
            return {"status": "error", "stderr": proc.stderr[:1000]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "timeout_seconds": 600}
    except Exception as exc:
        return {"status": "exception", "error": str(exc)}


def run_feedback_cleanup(
    artifact_root: Path,
    dry_run: bool,
) -> dict[str, Any]:
    """Delegate to ReviewFeedbackWriter.cleanup_expired_feedback via maintenance_checkpoint_db.py."""
    script = Path(__file__).resolve().parent / "maintenance_checkpoint_db.py"
    # Find all review_feedback directories under artifact_root
    results: list[dict[str, Any]] = []
    for feedback_dir in artifact_root.rglob("review_feedback"):
        if not feedback_dir.is_dir():
            continue
        cmd = [
            sys.executable,
            str(script),
            "--cleanup-feedback", str(feedback_dir),
        ]
        if dry_run:
            cmd.append("--dry-run")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            # Parse JSON from stdout
            lines = proc.stdout.strip().splitlines()
            parsed: dict[str, Any] = {}
            for line in reversed(lines):
                try:
                    parsed = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
            fb_cleanup = parsed.get("feedback_cleanup", {})
            results.append({
                "feedback_dir": str(feedback_dir),
                "removed_count": len(fb_cleanup.get("removed", [])),
                "kept_count": len(fb_cleanup.get("kept", [])),
                "dry_run": dry_run,
            })
        except Exception as exc:
            results.append({"feedback_dir": str(feedback_dir), "error": str(exc)})

    total_removed = sum(r.get("removed_count", 0) for r in results)
    total_kept = sum(r.get("kept_count", 0) for r in results)
    return {
        "feedback_dirs_scanned": len(results),
        "total_removed": total_removed,
        "total_kept": total_kept,
        "details": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="DeerFlow unified maintenance cron")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to checkpoints.db (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=None,
        help="Root directory to scan for review_feedback folders (default: auto-detect)",
    )
    parser.add_argument(
        "--keep-per-thread",
        type=int,
        default=15,
        help="Checkpoints to keep per thread (default: 15)",
    )
    parser.add_argument(
        "--disk-threshold",
        type=int,
        default=80,
        help="Disk usage alert threshold %% (default: 80)",
    )
    parser.add_argument(
        "--skip-checkpoints",
        action="store_true",
        help="Skip checkpoint DB maintenance",
    )
    parser.add_argument(
        "--skip-feedback",
        action="store_true",
        help="Skip expired feedback cleanup",
    )
    parser.add_argument(
        "--skip-disk",
        action="store_true",
        help="Skip disk monitoring",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze only, do not delete",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_ROOT,
        help=f"Directory to write JSON reports (default: {DEFAULT_ARTIFACT_ROOT})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    report: dict[str, Any] = {
        "script": "maintenance_cron",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
    }

    # Phase 1: Disk monitoring
    if not args.skip_disk:
        logger.info("=== Phase 1: Disk monitoring ===")
        disk_result = check_disk_usage(threshold_percent=args.disk_threshold)
        report["disk"] = disk_result
        if disk_result["alert_count"] > 0:
            logger.warning("Disk alerts: %d paths above %d%%", disk_result["alert_count"], args.disk_threshold)

    # Phase 2: Checkpoint DB maintenance
    if not args.skip_checkpoints and args.db_path.exists():
        logger.info("=== Phase 2: Checkpoint DB maintenance ===")
        checkpoint_result = run_checkpoint_maintenance(
            args.db_path, args.keep_per_thread, args.dry_run
        )
        report["checkpoints"] = checkpoint_result
    elif not args.skip_checkpoints:
        logger.warning("Checkpoint DB not found at %s — skipping", args.db_path)
        report["checkpoints"] = {"status": "skipped", "reason": "db_not_found"}

    # Phase 3: Expired feedback cleanup
    if not args.skip_feedback:
        logger.info("=== Phase 3: Expired feedback cleanup ===")
        artifact_root = args.artifact_root
        if artifact_root is None:
            # Auto-detect: look for common artifact roots
            candidates = [
                Path(__file__).resolve().parents[2] / "artifacts",
                Path(__file__).resolve().parents[2] / "examples",
            ]
            for c in candidates:
                if c.exists():
                    artifact_root = c
                    break
        if artifact_root and artifact_root.exists():
            feedback_result = run_feedback_cleanup(artifact_root, args.dry_run)
            report["feedback"] = feedback_result
        else:
            logger.warning("No artifact root found — skipping feedback cleanup")
            report["feedback"] = {"status": "skipped", "reason": "no_artifact_root"}

    report["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Persist report
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_file = args.output_dir / f"maintenance_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Report written to: %s", report_file)

    # Also print latest report path for cron piping
    latest_link = args.output_dir / "latest.json"
    latest_link.unlink(missing_ok=True)
    latest_link.symlink_to(report_file.name)

    # Exit code: 1 if disk alerts or any phase error
    has_errors = bool(
        report.get("disk", {}).get("alert_count", 0) > 0
        or report.get("checkpoints", {}).get("status") in {"error", "timeout", "exception"}
        or report.get("feedback", {}).get("status") == "error"
    )
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
