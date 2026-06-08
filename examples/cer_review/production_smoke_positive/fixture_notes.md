# Positive CER Production Smoke Fixture — Notes

## Purpose

This is a **synthetic smoke fixture** for system validation of the CER Review D1 workflow. It is NOT a real regulatory submission and must not be used for clinical or regulatory purposes.

## Design Rationale

The positive fixture is designed to satisfy the acceptance criteria of the `cer-clinical-evidence-panel-reviewer` agent by providing:
- Quantified clinical evidence (5 evidence items with population sizes, endpoints, results)
- Structured benefit claims (3 claims with quantitative results and source refs)
- Explicit residual risk assessment (4 risks with binary ACCEPTABLE/NOT ACCEPTABLE labels)
- Clear benefit-risk conclusion stating "benefits CLEARLY OUTWEIGH residual risks"
- Source traceability for all 23 claims via structured reference patterns (e.g., `CER_POSITIVE:Section4:Table3:R1`)
- Regulatory anchors (MDR Article 61, Annex XIV Part A, MEDDEV 2.7/1 Rev.4, MDCG 2020-5, ISO 14971, ISO 80601-2-56)

## Negative Control

The companion fixture at `examples/cer_review/production_smoke/CER_comprehensive_low_risk.txt` (narrative-style, no tables, no quantified claims) serves as a NEGATIVE CONTROL. It demonstrates that the system correctly identifies insufficient clinical evidence and triggers an appropriate HOLD at the clinical evidence panel step.

## Constraints

- Synthetic data only — all evidence IDs (SRC-001 through SRC-005) are illustrative
- Not for regulatory submission
- Designed to test the system, not to certify a real device
- All quantitative results are fabricated for testing purposes
- Seeded human gate decision is for test automation only

## Fixture Version

v1.0 — 2026-04-26
