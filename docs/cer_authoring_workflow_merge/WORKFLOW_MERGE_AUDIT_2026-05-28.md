# DeerFlow CER Authoring Workflow Merge Audit

Date: 2026-05-28

## Scope

This audit records the merged global CER authoring workflow. The original DeerFlow authoring chain is preserved, while the latest manufacturer-intake, source-preflight, evidence, risk, writer and review controls are integrated as hard gates or controlled-gap contracts.

## Merged Workflow

```text
initialize
  -> source inventory + manufacturer intake + source preflight
input_gate
  -> source_preflight_blocked ? controlled_compromise : device_profile
device_profile
claim_decomposition
pico_derivation
methodology_review / CEP
sota_search
literature_screening
evidence_appraisal
endpoint_extraction
claim_evidence_matrix
gap_pmcf
sota_clinical_context
claim_sota_alignment
risk_gspr_mapping
evidence_review_gates
writer_synthesis
benefit_risk_ledger
br_justified_gate
alignment_matrix
alignment_gate
pre_writer_readiness_gate
  -> PASS ? cer_writing : controlled_compromise/rework route
cer_writing
human_style_review
nb_precheck
workbook
gates
self_inspection
export
CER Review formal-review
final_synthesis
```

## Fixed Advantages

- The original authoring graph remains intact and testable.
- Bad inputs stop before writer invocation.
- Controlled compromise exports source blockers, controlled gaps and routing artifacts.
- Authoring artifacts are reviewable by CER Review, including closure-only blocked-context handling.
- `final_synthesis.json` is the final quality decision, while process exit code only reports runner completion.

## Global Front Gates

- `manufacturer_intake_report.json`
- `source_lock_report.json`
- `ifu_fact_table.json`
- `source_preflight_gate_report.json`
- `classification_consistency_report.json`
- `device_classification_lock.json`

Hard blockers remain:

- unresolved primary IFU ambiguity
- mixed device-domain signals without a manufacturer lock
- IFU P0 placeholders or missing P0 facts
- MDR class conflict without a manufacturer lock

Controlled gaps remain visible but do not falsely close:

- incomplete document control metadata
- draft PMS/PMCF plan
- source classification conflicts resolved by a manufacturer lock

## Evidence And Writer Gates

- CEP must exist with PICO, search protocol, inclusion/exclusion criteria, appraisal, claim-support, benefit-risk and PMS/PMCF update methods.
- Claim/evidence rows must expose support status, allowed wording, evidence ceiling and final-body eligibility.
- Benefit-risk closure cannot exceed evidence, RMF and PMS/PMCF support.
- Writer input packet is limited to approved facts, approved claims, approved evidence and controlled gaps.
- Writer is blocked if source preflight, classification, CEP or benefit-risk closure is not acceptable.

## Domain Merge Update

The `contrast_imaging_bubble_study_system` domain is now globally defined for the A01 WYTD project class:

- Source preflight domain signals
- Authoring domain defaults
- Clinical-domain inference
- Phase 7 SOTA retrieval profile
- SOTA query pack
- Writer remediation term matrix
- Domain template known-domain registry

This prevents Bubble Study System projects from falling back to generic or cardiac-ablation domains.

## Acceptance Checks

For high-quality CER generation, a complete project should reach:

- `source_preflight_gate_report.json`: `PASS`
- `device_classification_lock.json`: clean primary class lock
- `claim_support_matrix.json`: no final-body `to_be_verified`
- `benefit_risk_closure_matrix.json`: concludable or controlled uncertainty
- `FINAL_DRAFT_QA_REPORT.json`: `PASS`
- `final_gate_closure_report.json`: `PASS` or `PASS_WITH_CONTROLLED_GAPS`, critical failures = 0
- `cer_review/final_synthesis.json`: critical = 0, major <= 3

## Regression Commands

```bash
.venv/bin/python -m pytest \
  backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_source_preflight.py \
  backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_pre_writer_hard_gates.py \
  backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_export_routing.py \
  backend/tests/test_cer_review_final_synthesis.py \
  backend/tests/test_writer_remediation_gates.py
```
