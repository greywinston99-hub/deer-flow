# AGENT HANDOFF CONTRACTS — CER Authoring V1.0

> Claude Code | 2026-05-15 | Phase 2D

## Intake → SOTA Handoff

- **From**: authoring-intake-profile-claim-agent
- **To**: authoring-methodology-sota-agent
- **Artifact**: cep_pico_matrix, search_run_registry, clinical_domain
- **Gate**: PICO derivation complete, domain locked

## SOTA → Evidence Handoff

- **From**: authoring-methodology-sota-agent
- **To**: authoring-evidence-agent
- **Artifact**: sota_benchmark_table, sota_screening_disposition_table, search_run_registry
- **Gate**: SOTA benchmarks grounded in clinical domain, no cross-domain benchmarks

## Evidence → Writer Handoff

- **From**: authoring-evidence-agent
- **To**: authoring-cer-writer-agent
- **Artifact**: evidence_registry, claim_evidence_matrix, evidence_appraisal_table
- **Gate**: G42 (evidence sufficiency), G46 (pre-writer readiness)

## Risk/GSPR → Writer Handoff

- **From**: authoring-risk-equivalence-gspr-agent
- **To**: authoring-cer-writer-agent
- **Artifact**: benefit_risk_conclusion, risk_gspr_trace_matrix, equivalence_comparison_matrix
- **Gate**: BR justified gate (benefit-risk conclusion consistent with evidence)

## Writer → QA Handoff

- **From**: authoring-cer-writer-agent
- **To**: authoring-qa-review-agent
- **Artifact**: cer_chapter_drafts (all sections + annexes)
- **Gate**: Gates 1-5 (writer remediation content gates) + writer gate results

## QA → Lead Handoff

- **From**: authoring-qa-review-agent
- **To**: cer-authoring-lead-agent
- **Artifact**: qa_gate_report (decision, findings, rework_targets)
- **Gate**: QA must not false PASS on contaminated reports

## Artifact Output Contract

- **Release candidate**: only gate-passing CER_draft.md + CER_draft.docx in output root
- **Quarantine**: gate-failed reports + failed_gate_report + rejection_ledger
- **Audit-only**: reasoning_audit_ledger, authoring_workbook, calibration_event_log, gate traces, MCP call logs
