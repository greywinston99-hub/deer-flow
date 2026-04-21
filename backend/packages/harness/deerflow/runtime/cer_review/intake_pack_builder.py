"""CER Raw Project Intake — Evidence Pack Builder

Deterministic module for immutable locking of approved evidence packs.
NO LLM, NO AGENT. Pure Python.

Frozen baseline: CER_RAW_PROJECT_INTAKE_AGENT_VS_PROGRAM_BOUNDARY.md
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Exceptions ──────────────────────────────────────────────────────────────────


class PackBuilderError(Exception):
    """Base exception for pack builder errors."""
    pass


class LockedPackVerificationError(PackBuilderError):
    """Raised when locked pack verification fails."""
    pass


# ── Evidence Pack Builder ───────────────────────────────────────────────────────


def build_locked_pack(
    project_id: str,
    intake_session_id: str,
    input_root: Path,
    output_root: Path,
    approved_decision: dict,
    checksum_manifest: dict,
) -> dict[str, Any]:
    """Build immutable locked evidence pack from approved decision.

    This is a DETERMINISTIC module — NO LLM, NO AGENT.

    Steps:
    1. Read approved classifications from human_intake_gate_decision.json
    2. Copy approved files to artifacts/cer/{project_id}/intake/locked/
    3. Generate locked_evidence_pack_manifest.json with SHA-256 checksums
    4. Verify all checksums match checksum_manifest.json
    5. Set immutable flag (write-protect) on locked directory
    6. Write intake_approval_record.json
    """
    approved_files = _get_approved_files(approved_decision)

    # Avoid double artifacts/cer/ prefix when output_root is already artifacts/cer/
    # The caller passes output_root as the parent of artifacts/cer/{project_id}.
    # If output_root already ends with "artifacts/cer/", treat it as the artifacts root
    # and construct locked_dir directly under project_id.
    output_root_str = str(output_root)
    if output_root_str.rstrip("/").endswith("artifacts/cer") or output_root_str.rstrip("/").endswith("cer"):
        # output_root is artifacts/cer/ or X/artifacts/cer/
        locked_dir = output_root / project_id / "intake" / "locked"
    else:
        locked_dir = output_root / "artifacts" / "cer" / project_id / "intake" / "locked"
    locked_dir.mkdir(parents=True, exist_ok=True)

    # Track what we copy for the manifest
    copied_files = []
    verification_errors = []

    for file_info in approved_files:
        src_path = input_root / file_info["relative_path"]
        if not src_path.exists():
            verification_errors.append(f"Source file not found: {file_info['relative_path']}")
            continue

        # Determine destination within locked dir, preserving EP structure
        ep = file_info.get("ep", "EP-UNKNOWN")
        dest_subdir = locked_dir / ep
        dest_subdir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_subdir / src_path.name

        # Copy file
        shutil.copy2(src_path, dest_path)

        # Verify checksum matches original
        original_sha = file_info.get("sha256")
        if original_sha:
            copied_sha = _sha256(dest_path)
            if copied_sha != original_sha:
                verification_errors.append(
                    f"Checksum mismatch after copy: {file_info['relative_path']}"
                )
            copied_files.append({
                "relative_path": str(dest_path.relative_to(locked_dir)),
                "original_relative_path": file_info["relative_path"],
                "sha256": copied_sha,
                "size_bytes": dest_path.stat().st_size,
                "ep": ep,
            })

    if verification_errors:
        raise LockedPackVerificationError(
            f"Verification errors during pack build: {verification_errors}"
        )

    # Write locked manifest
    manifest = {
        "schema_name": "cer_intake_locked_evidence_pack_manifest",
        "schema_version": "v1",
        "project_id": project_id,
        "intake_session_id": intake_session_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_files": len(copied_files),
        "files": copied_files,
        "approved_decision_ref": "human_intake_gate_decision.json",
        "checksum_original_ref": "checksum_manifest.json",
    }
    manifest_path = locked_dir / "locked_evidence_pack_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write approval record
    reviewer = approved_decision.get("reviewer", {})
    approval_record = {
        "schema_name": "cer_intake_approval_record",
        "schema_version": "v1",
        "project_id": project_id,
        "intake_session_id": intake_session_id,
        "verdict": approved_decision.get("verdict"),
        "reviewer": reviewer,
        "reviewed_at": approved_decision.get("reviewed_at"),
        "conditions": approved_decision.get("conditions", []),
        "classification_overrides": approved_decision.get("classification_overrides", []),
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "locked_manifest_path": str(manifest_path.relative_to(output_root)),
        "total_files_locked": len(copied_files),
    }
    approval_record_path = locked_dir / "intake_approval_record.json"
    approval_record_path.write_text(
        json.dumps(approval_record, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Set immutable flag on locked directory (write-protect)
    _set_immutable(locked_dir)

    logger.info(
        f"[{intake_session_id}] Locked pack built: {len(copied_files)} files "
        f"in {locked_dir}"
    )

    return manifest


def verify_locked_pack(
    locked_dir: Path,
    locked_manifest: dict,
    original_checksum_manifest: dict,
) -> tuple[bool, list[str]]:
    """Verify locked pack integrity.

    Returns (all_valid, list_of_errors).
    """
    errors = []

    # Verify all files in manifest exist and match checksums
    for file_entry in locked_manifest.get("files", []):
        locked_path = locked_dir / file_entry["relative_path"]
        if not locked_path.exists():
            errors.append(f"Missing file: {file_entry['relative_path']}")
            continue
        actual_sha = _sha256(locked_path)
        if actual_sha != file_entry["sha256"]:
            errors.append(
                f"Checksum mismatch: {file_entry['relative_path']} "
                f"(manifest: {file_entry['sha256'][:8]}, actual: {actual_sha[:8]})"
            )

    # Verify no unexpected files
    manifest_paths = {f["relative_path"] for f in locked_manifest.get("files", [])}
    for file_path in locked_dir.rglob("*"):
        if file_path.is_file():
            rel = str(file_path.relative_to(locked_dir))
            if rel not in manifest_paths and rel not in (
                "locked_evidence_pack_manifest.json",
                "intake_approval_record.json",
            ):
                errors.append(f"Unexpected file: {rel}")

    return len(errors) == 0, errors


# ── Internal Helpers ────────────────────────────────────────────────────────────


def _get_approved_files(approved_decision: dict) -> list[dict]:
    """Extract list of approved files from human gate decision.

    The decision may include classification_overrides that change EP assignments.
    """
    return approved_decision.get("approved_files", [])


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _set_immutable(path: Path) -> None:
    """Set write-protect flag on directory to make it immutable.

    On POSIX: chmod -R a-w
    """
    import os
    import stat
    try:
        # Remove write permission recursively
        for root, dirs, files in os.walk(path):
            for d in dirs:
                os.chmod(os.path.join(root, d), stat.S_IRWXU & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
            for f in files:
                os.chmod(os.path.join(root, f), stat.S_IRWXU & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
        logger.info(f"Set immutable flag on {path}")
    except Exception as e:
        logger.warning(f"Could not set immutable flag on {path}: {e}")
