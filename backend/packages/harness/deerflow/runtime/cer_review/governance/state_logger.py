"""CER State Transition Logger — JSONL-Based Transition Log

Implements:
- JSONL-based state transition log (state_transition_log.jsonl)
- ST-XXX auto-incrementing entry IDs
- before/after state, trigger, actor, duration in source state
- Thread-safe append
- Query API for filtering by run_id, round_id, from_state, to_state

Frozen baseline: CER_GOVERNANCE_AND_OBSERVABILITY_PLAN_V1.md Section 3
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── State Logger ──────────────────────────────────────────────────────────────


class StateLogger:
    """CER state transition logger.

    Writes to: governance/state_transition_log.jsonl
    (one JSON object per line, newline-delimited JSON — append-only)

    Entry format:
    {
      "entry_id": "ST-001",
      "run_id": "cer-real-pjt0001-ca0b3709",
      "round_id": "round_001",
      "from_state": "S00",
      "to_state": "S01",
      "timestamp": "2026-04-16T16:03:28.654399+00:00",
      "actor": "system",
      "trigger": "run_started",
      "duration_sec": null
    }

    Rules:
    - Entries are NEVER modified after creation (append-only)
    - entry_id is assigned by StateLogger.log() — never by caller
    - Lines are never deleted from the log file
    """

    LOG_FILENAME = "governance/state_transition_log.jsonl"
    SCHEMA_NAME = "cer_state_transition_log"
    SCHEMA_VERSION = "v1"

    def __init__(self, artifact_root: Path):
        self.artifact_root = Path(artifact_root)
        self._lock = threading.Lock()
        self._ensure_governance_dir()
        self._entry_counter = self._load_counter()

    def _ensure_governance_dir(self) -> None:
        governance_dir = self.artifact_root / "governance"
        governance_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _log_path(self) -> Path:
        return self.artifact_root / self.LOG_FILENAME

    def _load_counter(self) -> int:
        """Count existing entries to continue sequence."""
        path = self._log_path
        if not path.exists():
            return 0
        try:
            with open(path, encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            max_num = 0
            for line in lines:
                try:
                    obj = json.loads(line)
                    eid = obj.get("entry_id", "")
                    if eid.startswith("ST-"):
                        try:
                            num = int(eid.split("-")[1])
                            if num > max_num:
                                max_num = num
                        except (ValueError, IndexError):
                            pass
                except json.JSONDecodeError:
                    pass
            return max_num
        except (OSError, IOError):
            return 0

    def log(
        self,
        run_id: str,
        round_id: str,
        from_state: str,
        to_state: str,
        actor: str,
        trigger: str,
        duration_sec: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Log a state transition. Returns the assigned entry_id (e.g., "ST-001").

        Thread-safe. Appends a single JSON line to the log file atomically.
        """
        with self._lock:
            self._entry_counter += 1
            entry_id = f"ST-{self._entry_counter:03d}"
            entry: dict[str, Any] = {
                "entry_id": entry_id,
                "run_id": run_id,
                "round_id": round_id,
                "from_state": from_state,
                "to_state": to_state,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": actor,
                "trigger": trigger,
            }
            if duration_sec is not None:
                entry["duration_sec"] = round(duration_sec, 3)
            if extra:
                entry.update(extra)

            line = json.dumps(entry, ensure_ascii=False)

            # Append to log file atomically: write to temp then rename
            log_path = self._log_path
            fd, temp = tempfile.mkstemp(
                dir=str(log_path.parent), suffix=".tmp", prefix=".stlog_"
            )
            try:
                # Read existing content
                existing = b""
                if log_path.exists():
                    with open(log_path, "rb") as rf:
                        existing = rf.read()

                # Write existing + new line
                with os.fdopen(fd, "wb") as f:
                    if existing:
                        f.write(existing)
                        if not existing.endswith(b"\n"):
                            f.write(b"\n")
                    f.write(line.encode("utf-8"))
                    f.write(b"\n")

                # Atomic rename
                os.rename(temp, log_path)
            except Exception:
                try:
                    os.unlink(temp)
                except OSError:
                    pass
                raise

        logger.info(
            f"State logged: {entry_id} {from_state} → {to_state} "
            f"run={run_id} round={round_id} actor={actor}"
        )
        return entry_id

    # ── Query API ────────────────────────────────────────────────────────────

    def query(
        self,
        run_id: str | None = None,
        round_id: str | None = None,
        from_state: str | None = None,
        to_state: str | None = None,
        actor: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query the transition log with optional filters.

        Returns entries ordered by timestamp (ascending).
        """
        path = self._log_path
        if not path.exists():
            return []

        results = []
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if run_id and entry.get("run_id") != run_id:
                        continue
                    if round_id and entry.get("round_id") != round_id:
                        continue
                    if from_state and entry.get("from_state") != from_state:
                        continue
                    if to_state and entry.get("to_state") != to_state:
                        continue
                    if actor and entry.get("actor") != actor:
                        continue

                    results.append(entry)

                    if limit and len(results) >= limit:
                        break
        except (OSError, IOError):
            return []

        return results

    def get_run_transitions(self, run_id: str) -> list[dict[str, Any]]:
        """Get all transitions for a run, ordered by timestamp."""
        return self.query(run_id=run_id)

    def get_round_transitions(self, run_id: str, round_id: str) -> list[dict[str, Any]]:
        """Get all transitions for a specific round within a run."""
        return self.query(run_id=run_id, round_id=round_id)

    def get_latest_state(self, run_id: str) -> str | None:
        """Get the most recent to_state for a run."""
        entries = self.query(run_id=run_id)
        if entries:
            return entries[-1].get("to_state")
        return None

    def get_state_duration_total(
        self, run_id: str, state: str
    ) -> float:
        """Get total time spent in a state across all transitions in a run."""
        entries = self.get_run_transitions(run_id)
        total = 0.0
        for e in entries:
            if e.get("to_state") == state and e.get("duration_sec") is not None:
                total += e["duration_sec"]
        return round(total, 3)
