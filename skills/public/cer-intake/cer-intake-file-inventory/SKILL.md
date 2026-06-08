---
name: cer-intake-file-inventory
description: Enumerate all submitted raw files with metadata and cryptographic identity for CER intake.
license: proprietary
allowed-tools: ls, bash
---

# CER Raw Project Intake — File Inventory Agent

## Role
Enumerate all submitted raw files with metadata and cryptographic identity.

## Workflow Context
This agent runs inside the CER Raw Project Intake workflow. It is invoked after the intake session is initialized and BEFORE any semantic analysis occurs. Its output feeds into Dedupe Agent, Document Parsing Agent, and the Orchestrator.

## Responsibilities
- Recursively enumerate all files in `artifacts/cer/{project_id}/input/`
- Generate SHA-256 checksum for every file (byte-for-byte)
- Record: filename, path, size_bytes, created_at, extension, mime_type (estimated from extension)
- Identify directory structure and apparent EP classification from path
- Flag: zero-byte files, suspiciously small files, unrecognized binary formats
- Produce structured `file_inventory.json`

## Input Contract
- `artifacts/cer/{project_id}/input/` — raw uploaded files (read-only, never modified)

## Output Schema
```json
{
  "schema_name": "cer_intake_file_inventory",
  "schema_version": "v1",
  "project_id": "CER-PJT-XXXX",
  "intake_session_id": "intake-XXXXXXXX",
  "generated_at": "ISO8601 timestamp",
  "total_files": 0,
  "total_size_bytes": 0,
  "files": [
    {
      "file_id": "F-001",
      "relative_path": "EP-001_PRODUCT_DEFINITION/IFU_ABC_v2.pdf",
      "absolute_path": "artifacts/cer/{project_id}/input/EP-001_PRODUCT_DEFINITION/IFU_ABC_v2.pdf",
      "filename": "IFU_ABC_v2.pdf",
      "extension": ".pdf",
      "size_bytes": 0,
      "sha256": "abc123...",
      "apparent_ep": "EP-001",
      "apparent_doc_type": "IFU",
      "mime_type_estimated": "application/pdf",
      "flagged": false,
      "flag_reason": null,
      "detected_at": "ISO8601 timestamp"
    }
  ],
  "flags": {
    "zero_byte_files": [],
    "suspiciously_small_files": [],
    "unrecognized_formats": []
  }
}
```

## Quality Gates
- Every file in `input/` MUST appear in the inventory
- Every file MUST have a valid SHA-256 checksum
- Zero-byte files MUST be flagged
- Files < 1KB SHOULD be flagged as suspiciously small

## Forbidden Actions
- Do NOT read file content beyond header bytes for type detection
- Do NOT modify any submitted files
- Do NOT delete files
- Do NOT make semantic judgments about document content

## Implementation Note
This skill is implemented as DETERMINISTIC CODE (`intake_file_ops.build_file_inventory`).
It is listed as an "agent" for workflow consistency but runs without LLM.
The Orchestrator calls this code directly, not via task() subagent delegation.

## Handoff Targets
- Dedupe Agent receives `file_inventory.json` and `checksum_manifest.json`
- Document Parsing Agent receives `file_inventory.json`
- Orchestrator receives aggregated inventory for state tracking
