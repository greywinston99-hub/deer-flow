# ARTIFACT OUTPUT CONTRACT — CER Authoring V1.0

> Claude Code | 2026-05-15 | Phase 2D

## Output Categories

### Submission-Facing Body
Files intended for NB submission and human review:
- `CER_draft.md` — Full CER markdown (Sections 1-5 + Annexes)
- `CER_draft.docx` — Formatted CER document
- `device_profile.json` — Device identity and specifications
- `claim_support_matrix.json` — Claim-evidence support levels
- `benefit_risk_conclusion.json` — Benefit-risk analysis
- Supporting evidence tables (.xlsx): claim_evidence_matrix, sota_benchmark_table, risk_gspr_trace_matrix, etc.

### Audit-Only Artifacts
Internal execution traces — never in CER body, never in submission package:
- `reasoning_audit_ledger.xlsx` — Agent reasoning traces
- `authoring_workbook.json` — Complete workbook with all intermediate data
- `calibration_event_log.xlsx` — Calibration run events
- `gate_routing_trace.csv` — Gate execution traces
- `ei_gate_signals.json` — EI reasoning signals
- `human_review_queue.json` — Items flagged for human review
- `provisional_ei_reasoning_report.md` — Provisional EI outputs
- MCP call logs (in search_run_registry, pubmed_fetch_batch_lineage)

### Quarantine Artifacts
Gate-failed reports — never in release/final output:
- `quarantine/CER_draft_QUARANTINED.md` — Failed CER draft
- `quarantine/failed_gate_report_<timestamp>.json` — Detailed failure report
- `quarantine/rejection_ledger.json` — Accumulated rejection history

### Release Candidate Artifacts
Reports that pass all gates:
- All submission-facing body files
- `writer_remediation_gate_results.json` — Gate-by-gate results
- `writer_remediation_qa_report.json` — Composite QA report (Gate 5)
- `qa_gate_report.json` — Standard QA gate report
- `final_gate_closure_report.json` — Final gate closure decision

## Separation Rules

1. Audit artifacts MUST NOT appear in CER body text.
2. Internal system language (Claude, DeerFlow, MCP, not_allowed, score:100) MUST NOT appear in CER body.
3. Gate-failed reports MUST go to quarantine, never to release candidate directory.
4. Release candidate directory MUST only contain gate-passing reports.
5. Writer remediation gate results are included in both release and quarantine outputs for traceability.
