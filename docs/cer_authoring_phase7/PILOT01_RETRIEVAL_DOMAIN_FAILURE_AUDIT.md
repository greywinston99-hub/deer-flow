# PILOT-01 Retrieval Domain Failure Audit

## Observed Failure
PILOT-01 recorded the IFU intended use as joint surgery / soft-tissue resection / ablation / coagulation / hemostasis, but downstream PICO/retrieval/SOTA/evidence drifted into cardiac electrophysiology because generic `RF ablation` terms were not sufficiently constrained by clinical domain and intended use.

## Root Cause
Before Phase 7, the retrieval layer had no mandatory query construction trace, no query-to-PMID provenance, no per-record domain screening rationale, and no writer consumption guard requiring externally retrieved evidence.

## Phase 7 Control
The retrieval profile now builds orthopedic/arthroscopic soft-tissue RF queries when the IFU/intended use contains joint surgery + soft tissue/RF ablation/coagulation/hemostasis terms. The query includes wrong-domain exclusions for atrial fibrillation, pulmonary vein, cardiac electrophysiology, catheter ablation, ventricular tachycardia and cardiac mapping.

## Expected Behavior
Cardiac EP literature can be excluded or retained as technical/background context only when justified. It cannot become pivotal/supportive evidence for joint surgery clinical conclusions without explicit domain justification and ledger approval.

## Regression Evidence
Runtime tests verify:

- orthopedic RF query construction includes orthopedic/arthroscopy/radiofrequency terms and cardiac EP exclusion terms;
- cardiac EP records under an orthopedic retrieval domain are marked `RETRIEVAL_DOMAIN_MISMATCH_REWORK_REQUIRED`;
- Writer consumption trace blocks non-ledger-approved evidence.
