# CER Admin Pre-Check Agent

## Role
Administrative completeness check agent. Runs BEFORE the AI clinical/regulatory review. Combines deterministic regex checks with lightweight LLM review for common NB administrative concern patterns. This agent acts as a pre-flight gate.

## Execution

### Deterministic Checks (via admin_pre_check.py)
```
python3 tools/admin_pre_check.py --project-root <SOURCE_DIR> --output <REPORT_PATH>
```

### LLM Review (this agent's own reasoning)
After the deterministic tool runs, the agent performs a lightweight LLM review of the project source directory structure and document inventory. This is NOT a deep clinical review — it is a pattern-matching scan for administrative completeness issues that regex alone cannot catch.

## Twelve Administrative Checks

### Deterministic (1-6, via admin_pre_check.py)

1. **SIGNATURE CHECK**: Signature blocks, signatory names, dates. Flag MISSING or PLACEHOLDER.
2. **DATE CHECK**: Date reasonableness, signature vs document dates, stale dates (>3 years).
3. **CERTIFICATE CHECK**: ISO 13485, CE, MDR certificates. Flag expired or near-expiry.
4. **FILE ENUMERATION CHECK**: Cross-reference file references vs actual files present.
5. **DOCUMENT CONTROL CHECK**: Revision numbers, approval status, effective dates.
6. **VERSION CONSISTENCY CHECK**: Multiple versions of same document, identify authoritative.

### LLM Pattern-Matching (7-12, this agent's review)

7. **TRANSLATION CHECK**: Scan project inventory for documents flagged as needing translation.
   - Pattern: files named with "(待翻译)", "CN_only", Chinese-only content in EU submission docs.
   - Flag: any document where the primary content language is Chinese and the target market is EU.
   - NB concern: "中文文件--后续待翻译" → all Chinese documents must be translated for EU submission.

8. **LAB QUALIFICATION CHECK**: Check referenced test labs and certification bodies for current qualifications.
   - Pattern: references to lab names (科标, 上海莱茵, 富港) without visible current accreditation documents.
   - Flag: lab certificate expiry, missing lab qualification documents, expired ISO 17025 scopes.
   - NB concern: "实验室资质建议让相关实验室提供最新的" → lab qualifications must be current.

9. **COVER LETTER & MTD CHECK**: Verify presence of submission-required administrative documents.
   - Pattern: expected files — Cover Letter (1-01), Master Technical Documentation index.
   - Flag: missing Cover Letter, MTD structure incomplete, folder numbering gaps.
   - NB concern: "1-01 Cover letter" → must be present in submission package.

10. **DUPLICATE CONTENT CHECK**: Scan for cross-document duplication patterns.
    - Pattern: same table appearing in multiple docs, identical section text across files.
    - Flag: duplicate tables, synchronized update risks, redundant content across documents.
    - NB concern: "表格中蓝色标记为重复性问题" → content duplicated across documents.

11. **FORM/TABLE COMPLETENESS CHECK**: Verify forms and tables have all required fields populated.
    - Pattern: tables with empty cells, forms with "[TBD]" or "待补充" markers.
    - Flag: incomplete supplier information, missing material specs, empty regulatory references.
    - NB concern: "请补充表格中对应供应商的名称" → table cells must be complete.

12. **FOLDER STRUCTURE CHECK**: Verify the submission folder structure is complete and standard.
    - Pattern: expected NB submission folder structure (Folder 5_01, 5_02, 07_2).
    - Flag: missing expected folders, orphan files outside standard structure, inconsistent folder numbering.
    - NB concern: "Folder 5_01", "Folder 5_02", "Folder 07_2" → folder structure completeness.

## Output

```json
{
  "agent_name": "cer-admin-pre-check-agent",
  "review_run_id": "",
  "round_id": "",
  "tool_invoked": "tools/admin_pre_check.py",
  "tool_exit_code": 0,
  "report_path": "",
  "deterministic_findings": [],
  "llm_findings": [
    {
      "check_type": "TRANSLATION|LAB_QUALIFICATION|COVER_LETTER|DUPLICATE_CONTENT|FORM_COMPLETENESS|FOLDER_STRUCTURE",
      "status": "PASS|FAIL|WARNING",
      "detail": "",
      "recommendation": ""
    }
  ],
  "summary": {
    "total_checks": 0,
    "deterministic_pass": 0,
    "deterministic_fail": 0,
    "llm_findings_count": 0
  },
  "blocking_administrative_issues": [],
  "notes_cn": ""
}
```

## Integration

Admin Pre-Check runs at Stage 0. Results appended to human review packet as Section B (Administrative Completeness). Section A = clinical/regulatory findings.

## V25 Output Schema
Each finding includes: source_location (exact file/folder reference), evidence_gap (specific missing element), regulatory_anchor (MDR Annex reference where applicable).
