# Phase 4 Priority 2 Claim Coverage Prompt Report

## Decision

`PHASE4_PRIORITY2_READY_FOR_CCD_ACCEPTANCE`

## Scope

This patch addresses COG-001 by strengthening the CER writer prompt layer with a mandatory pre-write IFU full-text claim coverage check.

It does not change:

- `cer_authoring_v1` graph topology
- G0-G38 gate criteria
- 1+6 agent team membership or responsibilities
- device identity arbitration
- baseline structural pipeline

## Implemented Changes

1. Added a writer role contract requiring the CER writer to compare the Claim Ledger against subject IFU claim-bearing sections before drafting CER prose.
2. Required the writer to return `missing_claim_candidates` and `rework_targets` when the subject IFU contains clinically material claims absent from the Claim Ledger.
3. Added writer-only SharedAuthoringState summary context containing subject IFU claim-bearing excerpts from approved writer input sources.
4. Excluded locked/final package IFU sources from the writer claim audit context.
5. Increased writer state-summary budget to preserve the IFU claim audit context.

## Claim-Bearing IFU Scope

The writer prompt now explicitly checks IFU sections covering:

- intended use / intended purpose
- indications
- clinical benefits
- performance
- safety
- contraindications
- warnings
- precautions
- adverse events / side-effects
- residual risks
- PMS / PMCF
- accessories and compatibility

## Expected Effect

The CER writer should no longer accept a sparse Claim Ledger at face value when the subject IFU contains additional clinically material claims. Instead, it should surface a controlled rework target before drafting or before strengthening conclusions.

This is designed to reduce the semantic delta between AI claims and gold claims without changing upstream claim extraction logic during this phase.

## Verification

Added regression tests:

- writer prompts contain the mandatory pre-write IFU claim coverage rule
- writer summary includes subject IFU claim-bearing excerpts
- locked final IFU content is not exposed to the writer prompt context

