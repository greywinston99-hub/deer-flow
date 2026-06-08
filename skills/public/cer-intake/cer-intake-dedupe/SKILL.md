---
name: cer-intake-dedupe
description: Deduplicate evidence pack files by SHA-256 checksum for CER intake.
license: proprietary
allowed-tools: bash, read_file
---

# CER Raw Project Intake — Dedupe Agent

## Role
Identify exact and near-duplicate files to prevent redundant processing.

## Workflow Context
This stage runs in parallel with Document Parsing Agent after File Inventory Agent completes.
- EXACT duplicates (identical SHA-256): handled by deterministic code (no LLM)
- NEAR-DUPLICATES (same document, different version): LLM agent semantic analysis
- VERSION CONFLICTS: LLM agent semantic analysis with human escalation

## Responsibilities
- Compare files by SHA-256 for exact duplicates (deterministic, no LLM)
- Compare extracted text for near-duplicates (LLM agent)
- Group duplicates and select canonical (LLM agent: latest date OR complete OR readable)
- Report version conflicts with explanation (LLM agent)
- For each duplicate group: recommend which file to retain as canonical

## Input Contract

## Input Contract
- `file_inventory.json` — from File Inventory Agent
- `checksum_manifest.json` — from File Inventory Agent
- `intake/text_extracted/*.txt` — extracted text (if available)

## Output Schema
```json
{
  "schema_name": "cer_intake_dedupe_report",
  "schema_version": "v1",
  "project_id": "CER-PJT-XXXX",
  "intake_session_id": "intake-XXXXXXXX",
  "generated_at": "ISO8601 timestamp",
  "total_files_processed": 0,
  "duplicate_groups": [
    {
      "group_id": "DUP-001",
      "duplicate_type": "exact | near_duplicate | version_conflict",
      "canonical_file_id": "F-001",
      "canonical_path": "EP-001/IFU_ABC_v3.pdf",
      "canonical_reason": "Latest version, complete, readable",
      "duplicate_file_ids": ["F-002", "F-003"],
      "duplicate_paths": [
        "EP-001/IFU_ABC_v1.pdf",
        "EP-001/IFU_ABC_v2.pdf"
      ],
      "version_conflict_detail": null
    }
  ],
  "version_conflicts": [],
  "canonical_summary": {
    "total_groups": 0,
    "exact_duplicates": 0,
    "near_duplicates": 0,
    "version_conflicts": 0
  }
}
```

## Quality Gates
- All files with identical SHA-256 MUST be in the same duplicate group
- Canonical selection MUST be justified (latest date OR complete OR readable)
- Version conflicts MUST include explanation of what differs

## Forbidden Actions
- Do NOT delete files
- Do NOT modify files
- Do NOT decide which version is clinically superior (that's human judgment)
- Do NOT hallucinate content differences between versions

## Handoff Targets
- Evidence Classification Agent receives `dedupe_report.json` to avoid double-classifying duplicates
- Orchestrator receives dedupe report for state tracking
