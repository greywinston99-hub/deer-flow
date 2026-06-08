# Phase 5A P5-2 Benefit-Risk Quantitative Depth Report

## Decision

`IMPLEMENTED_ACCEPTED / EFFECTIVENESS_PENDING`

## Scope

This patch hardens the writer-synthesis benefit-risk layer. It does not change gate criteria, identity arbitration, agent roles, prompts, or graph structure.

## Implemented Changes

The Benefit-Risk Ledger now includes:

- `magnitude_of_benefit`
- `severity_of_risk`
- `benefit_evidence_basis`
- `risk_evidence_basis`
- `evidence_strength`
- `uncertainty_level`
- `benefit_risk_balance`
- `balance_rationale`

The ledger supports two modes:

- Quantitative/source-reported comparison when endpoint, benchmark, sample-size, timepoint, or statistical-result data are present.
- Semi-quantitative ordinal comparison when only evidence strength, risk severity, RMF/IFU coverage, gaps, and uncertainty justify controlled wording.

The code deliberately avoids false precision. Missing numeric data are recorded as non-quantified or semi-quantitative instead of inventing a value.

## Writer Consumption

Chapter 5 now consumes the enhanced Benefit-Risk Ledger. Conclusions include:

- Benefit-risk balance.
- Magnitude of benefit.
- Risk severity.
- Residual uncertainty.
- Evidence/SOTA/BR basis.
- Limitations driven by balance rationale.

The writer control text in section 4.7 also displays the enhanced ledger fields before final conclusion wording is produced.

## Traceability

Each benefit-risk judgment traces to:

- Evidence IDs.
- SOTA benchmark IDs.
- Endpoint/derivation rows.
- Risk IDs and IFU/RMF coverage.
- Vigilance event statistics where available.
- Alignment matrix status.
- PMCF boundary decisions.

## Boundaries Preserved

- No G30/G33/G38 or other gate criteria changed.
- No device identity changes.
- No 1+6 agent changes.
- No graph structure changes.
- No PMCF engine expansion; PMCF boundary is consumed only as an existing control signal.
- No baseline rerun or production run executed.

## Files Changed

- `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/phase0_contracts.py`
- `backend/tests/test_cer_authoring_runtime.py`

## Verification

Command:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
```

Result:

```text
62 passed in 6.22s
```

## Effectiveness Pending

Effectiveness remains pending until Phase 5B reruns CAL-001/CAL-002/CAL-003 and semantic delta re-evaluation confirms whether COG-005 benefit-risk reasoning deltas are reduced.
