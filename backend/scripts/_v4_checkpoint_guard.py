"""V4 Checkpoint/Resume Guard — prevents common checkpoint corruption issues.

Adds to the launcher pipeline:
1. Artifact root conflict detection (no two pipelines writing same root)
2. response.json overwrite protection (gate state preservation)
3. Active run ledger (tracks running pipelines)

Usage:
    from _v4_checkpoint_guard import guard_artifact_root, guard_gate_state
    guard_artifact_root("/path/to/artifact_root")
"""
from __future__ import annotations

import json, os, signal, sys, time
from pathlib import Path


def guard_artifact_root(artifact_root: str) -> dict:
    """Check for conflicts before writing to artifact root.
    
    Returns dict with warnings or raises SystemExit on critical conflict.
    """
    root = Path(artifact_root)
    lock_file = root / ".v4_run_lock"
    active_ledger = root / ".v4_active_runs.json"

    result = {"conflict": False, "active_run": None, "warnings": []}

    # Check for active lock
    if lock_file.exists():
        try:
            lock_data = json.loads(lock_file.read_text())
            pid = lock_data.get("pid")
            if pid:
                # Check if PID is still alive
                try:
                    os.kill(pid, 0)  # Signal 0 = check exists
                    result["conflict"] = True
                    result["active_run"] = lock_data
                    result["warnings"].append(
                        f"ACTIVE PIPELINE at PID {pid} already writing to {artifact_root}. "
                        f"Started at {lock_data.get('started')}. "
                        f"Do not start another pipeline to the same artifact root."
                    )
                except (OSError, ProcessLookupError):
                    # PID not alive — stale lock
                    lock_file.unlink()
                    result["warnings"].append(f"Removed stale lock from PID {pid}")
        except (json.JSONDecodeError, KeyError):
            lock_file.unlink()

    return result


def acquire_artifact_root_lock(artifact_root: str, project_id: str) -> str:
    """Acquire exclusive lock on artifact root. Returns lock path."""
    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    lock_file = root / ".v4_run_lock"

    # Check first
    guard_result = guard_artifact_root(artifact_root)
    if guard_result["conflict"]:
        raise SystemExit(
            f"[V4] FATAL: {guard_result['warnings'][0]}"
        )

    lock_data = {
        "pid": os.getpid(),
        "project_id": project_id,
        "artifact_root": str(root),
        "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    lock_file.write_text(json.dumps(lock_data, indent=2))

    # Register cleanup on exit
    import atexit
    def _release_lock():
        if lock_file.exists():
            lock_file.unlink()
    atexit.register(_release_lock)

    return str(lock_file)


def guard_gate_state(artifact_root: str, gate_node: str) -> bool:
    """Check if gate response.json is in a safe state to overwrite.
    
    Returns True if safe to write, False if existing response should be preserved.
    """
    resp_path = Path(artifact_root) / ".human_gate" / "response.json"
    if not resp_path.exists():
        return True

    try:
        data = json.loads(resp_path.read_text())
        action = data.get("action", "").strip()
        stored_gate = data.get("gate_node", "").strip()

        # If a previous gate's response exists with a confirm action,
        # archive it rather than overwrite
        if action == "confirm" and stored_gate and stored_gate != gate_node:
            archive_dir = Path(artifact_root) / ".human_gate" / ".responses"
            archive_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
            archive_path = archive_dir / f"{stored_gate}_{timestamp}.json"
            resp_path.rename(archive_path)
            print(f"[V4-GATE] Archived stale response: {stored_gate} → {archive_path.name}",
                  file=sys.stderr)
            return True

        # If action is empty, it's safe to write
        if not action:
            return True

        # Existing confirm for same gate — preserve it
        if action == "confirm" and stored_gate == gate_node:
            return False

    except (json.JSONDecodeError, KeyError):
        return True

    return True
