# Phase 2.1 SOTA Benchmark Engine Hardening Report

Date: 2026-05-09

## Conclusion

`PHASE2_1_ACCEPTED_FOR_CCD_READ_ONLY_VALIDATION`

AGG-002 / G30 recurrence was addressed at the deterministic authoring pipeline layer. The patch does not change G30 pass/fail criteria, does not change the 1+6 agent responsibilities or prompts, and does not modify other G0-G38 gate criteria.

## Scope

This patch hardens the SOTA benchmark derivation path so that endpoint extraction is not treated as a terminal artifact. When `endpoint_extraction` already exists, the pipeline now still derives and writes:

- `endpoint_registry`
- `sota_endpoint_derivation_table`
- `sota_quantitative_benchmark_table`
- `sota_evidence_synthesis_matrix`
- `sota_claim_reverse_correction_table`

## Root Cause Addressed

Before the patch, `extract_endpoints()` returned early when `endpoint_extraction` existed. In that state, downstream SOTA derivation artifacts could remain absent or incomplete even though endpoint rows were available, leaving G30 to fail with a missing/incomplete `sota_endpoint_derivation_table`.

## Implemented Changes

### 1. SOTA Benchmark Derivation Pipeline

`extract_endpoints()` now normalizes endpoint IDs and deterministically derives benchmark artifacts from:

- `endpoint_extraction`
- `sota_benchmark_matrix`
- `evidence_registry`
- `cep_pico_matrix`
- `search_run_registry`
- `device_profile`

Every generated SOTA endpoint derivation row includes the required benchmark substance fields:

- `benchmark_value`
- `source`
- `population`
- `sample_size`
- `CI_or_range`

The existing G30-required fields remain populated:

- `pico_id`
- `search_id`
- `article_id`
- `evidence_id`
- `endpoint_id`
- `benchmark_id`
- `endpoint_definition`
- `sample_size`
- `statistical_result`
- `use_in_section_4_7`

### 2. Endpoint Registry

A unified `END-###` endpoint numbering layer was added through `endpoint_registry`. It preserves the original endpoint ID as `source_endpoint_id`, then maps each endpoint to:

- benchmark
- claim
- PICO
- endpoint type
- clinical meaning
- acceptance criterion
- source evidence
- section 4.7 use

### 3. Benchmark Source Hierarchy

Each endpoint/benchmark row now records `source_hierarchy_level` and `source_hierarchy_rank`.

Hierarchy implemented:

1. `aggregate`
2. `guideline`
3. `registry`
4. `cohort`
5. `case series`

This hierarchy is used in endpoint registry, SOTA derivation, quantitative benchmark, and evidence synthesis outputs.

### 4. SOTA-to-Claim Reverse Correction

The pipeline now emits `sota_claim_reverse_correction_table` and merges claim-level SOTA correction fields back into `claim_ledger`:

- `sota_reverse_correction`
- `sota_corrected_claim_text`
- `sota_support_status`
- `sota_correction_basis`
- `allowed_wording_strength`

This does not rewrite CER prose directly. It constrains downstream writer logic by recording whether each claim should be kept within SOTA limits or qualified/downgraded because benchmark evidence is partial or gap-controlled.

### 5. Artifact Contract

The artifact writer and workbook now export:

- `endpoint_registry.xlsx`
- `sota_claim_reverse_correction_table.xlsx`

Both are included in `authoring_workbook.json`.

## Files Changed

- `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/state.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/artifacts.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/phase0_contracts.py`
- `backend/tests/test_cer_authoring_runtime.py`
- `docs/cer_authoring_phase0/PHASE2_1_SOTA_BENCHMARK_ENGINE_HARDENING_REPORT.md`

## Constraints Confirmed

- G30 gate criteria: unchanged.
- G0-G38 other gate criteria: unchanged.
- 1+6 agent responsibilities/prompts: unchanged.
- SOTA Agent, Evidence Agent, Writer Agent prompts: unchanged.
- No calibration project rerun was executed.
- No locked 02/03 calibration content was read.

## Test Evidence

Commands executed:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
backend/.venv/bin/python -m pytest backend/tests/test_calibration_delta_analyzer.py backend/tests/test_cer_cowork_supervisor.py -q
backend/.venv/bin/python -m compileall -q backend/packages/harness/deerflow/runtime/cer_authoring backend/tests/test_cer_authoring_runtime.py
```

Results:

- `28 passed`
- `12 passed`
- compileall completed without errors

## CCD Read-Only Validation Focus

CCD should verify:

1. A state with `endpoint_extraction` but no `sota_endpoint_derivation_table` now produces G30-ready derivation rows.
2. Each generated benchmark row includes value/source/population/sample size/CI-or-range fields.
3. Endpoint IDs are normalized to `END-###` while preserving source endpoint IDs.
4. Claim ledger receives SOTA reverse correction fields.
5. No gate criteria or authoring agent prompt was modified.
