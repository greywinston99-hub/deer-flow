# SKILL INPUT/OUTPUT CONTRACTS — CER Authoring V1.0

> Claude Code | 2026-05-15 | Phase 2D

## Data Flow

```
Source PDFs → Intake → PICO → SOTA Search → Evidence → Writer → QA → Export
                  ↓                    ↓           ↓         ↓       ↓
            device_profile    sota_benchmarks  evidence   CER    release/
                              screening        registry   draft  quarantine
```

## Per-Skill Contracts

### Intake → PICO
Output: claim_ledger (JSON array), cep_pico_matrix (JSON array)
Required fields: claim_id, claim_type, required_evidence per claim. pico_id, population, intervention, comparator, outcome per PICO.

### PICO → SOTA
Output: sota_pico_strategy (JSON array), search_run_registry (JSON array)
Required fields: search_id, database, objective, query, result_count, date per search.

### SOTA → Evidence
Output: sota_benchmark_table, sota_screening_disposition_table
Required fields: benchmark_id, pico_id, endpoint, sota_value_range, clinical_significance per benchmark.

### Evidence → Writer
Output: evidence_registry (JSON array), claim_evidence_matrix (JSON array)
Required fields per evidence: evidence_id, source_type, device_relationship, ledger_approved_for_writer.
Required fields per claim-evidence: claim_id, evidence_id, support_level, max_conclusion_strength.

### Writer → QA
Output: cer_chapter_drafts (dict of section_name → markdown_text)
Required sections: 1 Summary, 2 Scope, 3 Clinical Background, 4 Device Under Evaluation, 5 Conclusions.

### QA → Export
Output: qa_gate_report (JSON with decision, findings, rework_targets)
Also: writer_remediation_gate_results.json, writer_remediation_qa_report.json.

### Export → Output
Output directory: CER_draft.md, CER_draft.docx + all supporting artifacts
Quarantine directory (if gate fail): CER_draft_QUARANTINED.md, failed_gate_report.json, rejection_ledger.json
