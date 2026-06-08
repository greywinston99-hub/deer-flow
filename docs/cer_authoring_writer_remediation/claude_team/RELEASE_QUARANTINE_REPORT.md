# RELEASE QUARANTINE REPORT (W4)

## Test Coverage

| Test | Description | Expected | Result |
|------|-------------|----------|--------|
| test_gate_fail_to_quarantine | Gate fail → quarantine | quarantine/ created | PASS |
| test_clean_not_quarantined | Clean report → no quarantine | no quarantine | PASS |

## Quarantine Mechanism

When any writer gate (1-4) returns HARD_FAIL:
1. `CER_draft.md` and `CER_draft.docx` are NOT written to main output directory
2. Instead: `quarantine/CER_draft_QUARANTINED.md` is created
3. `quarantine/failed_gate_report_<timestamp>.json` records all failures
4. `quarantine/rejection_ledger.json` accumulates all rejections

## Rejection Ledger Format

```json
{
  "entries": [
    {
      "report_id": "...",
      "device": "...",
      "timestamp": "...",
      "failed_gates": ["gate_1_domain_consistency", ...],
      "offending_sections": [...],
      "reason": "..."
    }
  ],
  "total_rejections": N,
  "last_updated": "..."
}
```

## Clean Report Path

When all writer gates (1-4) return PASS:
- `CER_draft.md` and `CER_draft.docx` are written normally to main output directory
- `writer_remediation_gate_results.json` and `writer_remediation_qa_report.json` are included in output
- No quarantine artifacts are created

**Verdict**: Quarantine routing correctly separates gate-failed from gate-passing reports. Release candidate directory only contains clean reports.
