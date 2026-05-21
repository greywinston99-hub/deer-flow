"""CER Raw Project Intake — File Operations

Deterministic file I/O, checksum computation, and inventory generation.
No LLM, no agent. All file operations are pure functions.

Frozen baseline: CER_RAW_PROJECT_INTAKE_AGENT_VS_PROGRAM_BOUNDARY.md
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Supported extractable file types
EXTRACTABLE_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".txt", ".md"}
UNSUPPORTED_EXTENSIONS = {".exe", ".dll", ".so", ".bin", ".dmg"}


# ── Core File Operations ────────────────────────────────────────────────────────


def enumerate_files(input_root: Path) -> list[Path]:
    """Recursively enumerate all files in input_root."""
    files = []
    for path in input_root.rglob("*"):
        if path.is_file() and not path.name.startswith("."):
            files.append(path)
    return sorted(files)


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 checksum of a file byte-for-byte."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_checksum_manifest(files: list[Path], base_dir: Path) -> dict[str, Any]:
    """Generate checksum manifest for all files."""
    checksums = []
    for f in files:
        rel_path = str(f.relative_to(base_dir))
        checksum = compute_sha256(f)
        checksums.append({
            "relative_path": rel_path,
            "filename": f.name,
            "sha256": checksum,
            "size_bytes": f.stat().st_size,
        })
    return {
        "schema_name": "cer_intake_checksum_manifest",
        "schema_version": "v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_files": len(checksums),
        "files": checksums,
    }


def build_file_inventory(
    input_root: Path,
    project_id: str,
    intake_session_id: str,
) -> dict[str, Any]:
    """Build complete file inventory with checksums.

    This is the deterministic enumeration — no LLM involved.
    """
    files = enumerate_files(input_root)
    checksums = {str(f.relative_to(input_root)): compute_sha256(f) for f in files}

    inventory_files = []
    zero_byte = []
    small_files = []
    unrecognized = []

    for i, f in enumerate(files):
        rel_path = str(f.relative_to(input_root))
        size = f.stat().st_size
        sha256 = checksums[rel_path]
        ext = f.suffix.lower()

        # Detect apparent EP from path
        apparent_ep = _detect_ep_from_path(rel_path)

        # Detect apparent type from filename
        apparent_type = _detect_type_from_filename(f.name)

        flagged = False
        flag_reason = None

        if size == 0:
            flagged = True
            flag_reason = "zero_byte_file"
            zero_byte.append(rel_path)
        elif size < 1024:
            flagged = True
            flag_reason = "suspiciously_small"
            small_files.append(rel_path)
        elif ext in UNSUPPORTED_EXTENSIONS:
            flagged = True
            flag_reason = "unsupported_format"
            unrecognized.append(rel_path)

        inventory_files.append({
            "file_id": f"F-{i+1:03d}",
            "relative_path": rel_path,
            "filename": f.name,
            "extension": ext,
            "size_bytes": size,
            "sha256": sha256,
            "apparent_ep": apparent_ep,
            "apparent_doc_type": apparent_type,
            "mime_type_estimated": _mime_from_ext(ext),
            "flagged": flagged,
            "flag_reason": flag_reason,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        })

    total_size = sum(f.stat().st_size for f in files)

    return {
        "schema_name": "cer_intake_file_inventory",
        "schema_version": "v1",
        "project_id": project_id,
        "intake_session_id": intake_session_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_files": len(files),
        "total_size_bytes": total_size,
        "files": inventory_files,
        "flags": {
            "zero_byte_files": zero_byte,
            "suspiciously_small_files": small_files,
            "unrecognized_formats": unrecognized,
        },
    }


def write_checksum_manifest(
    output_dir: Path,
    manifest: dict[str, Any],
) -> Path:
    """Write checksum manifest to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "checksum_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_file_inventory(
    output_dir: Path,
    inventory: dict[str, Any],
) -> Path:
    """Write file inventory to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "file_inventory.json"
    path.write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ── EP Detection ────────────────────────────────────────────────────────────────


def _detect_ep_from_path(rel_path: str) -> str | None:
    """Detect EP from path structure (e.g., EP-001_PRODUCT_DEFINITION)."""
    import re
    match = re.match(r"^(EP-\d+)", rel_path)
    if match:
        return match.group(1)
    return None


def _detect_type_from_filename(filename: str) -> str | None:
    """Detect document type from filename heuristics."""
    name_lower = filename.lower()
    if "cer" in name_lower:
        return "CER"
    if "ifu" in name_lower:
        return "IFU"
    if "cep" in name_lower:
        return "CEP"
    if "rmf" in name_lower or "risk" in name_lower:
        return "RMF"
    if "sscp" in name_lower:
        return "SSCP"
    if "pmcf" in name_lower:
        return "PMCF"
    if "equivalence" in name_lower or "equiv" in name_lower:
        return "equivalence_doc"
    if "literature" in name_lower or "sota" in name_lower:
        return "literature_search"
    if "clinical" in name_lower:
        return "clinical_evidence"
    return None


def _mime_from_ext(ext: str) -> str:
    """Map file extension to MIME type."""
    mime_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tiff": "image/tiff",
    }
    return mime_map.get(ext, "application/octet-stream")


# ── Locked Pack Verification ───────────────────────────────────────────────────


def verify_locked_pack_checksums(
    locked_dir: Path,
    expected_manifest: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Verify all files in locked directory match expected checksums.

    Returns (all_match, list_of_mismatches).
    """
    mismatches = []
    expected = {f["relative_path"]: f["sha256"] for f in expected_manifest["files"]}

    for rel_path, expected_sha in expected.items():
        locked_file = locked_dir / rel_path
        if not locked_file.exists():
            mismatches.append(f"MISSING: {rel_path}")
            continue
        actual_sha = compute_sha256(locked_file)
        if actual_sha != expected_sha:
            mismatches.append(f"MISMATCH: {rel_path} (expected {expected_sha[:8]}, got {actual_sha[:8]})")

    # Check for unexpected files
    all_expected_paths = set(expected.keys())
    for locked_file in locked_dir.rglob("*"):
        if locked_file.is_file():
            rel = str(locked_file.relative_to(locked_dir))
            if rel not in all_expected_paths:
                mismatches.append(f"UNEXPECTED: {rel}")

    return len(mismatches) == 0, mismatches
