# Phase 0.4 Device Identity / Device Classification Repair Report

Date: 2026-05-09

## Executive Summary

Phase 0.4 repairs the CAL-003 v1.1 device identity failure. The repair is
limited to device identity, device classification and clinical-domain inference.

This patch does not modify:

- SOTA Benchmark Engine;
- Evidence Appraisal;
- Writer Contract;
- Benefit-Risk logic;
- PMCF Boundary logic;
- Alignment Engine;
- G0-G38 gate criteria.

## Problem Addressed

CAL-003 v1.1 proved Phase 0.3 IFU detection works, but exposed a downstream
identity error:

- IFU intended use was correctly extracted as `ligating of tubular structures or vessels`;
- `device_type` was incorrectly inferred as `stent`;
- `anatomical_site` was polluted as `urinary tract`;
- SOTA / evidence / benchmark generation moved into an unrelated urology/stent
  domain;
- resulting content quality was not meaningful for calibration scoring.

## Implemented Repair

The deterministic identity layer now recognizes:

- ligating clips / hemostatic clips / vascular clips;
- `ligating of tubular structures or vessels`;
- RF / PADN ablation catheters;
- pulsed-field ablation systems/catheters;
- hemoperfusion / adsorber / cartridge devices;
- urology nephroscope and ureteral access sheath devices;
- explicit stent devices only when stent is the strongest source-supported
  candidate.

If no supported type is found, the system returns:

`UNKNOWN_WITH_CANDIDATES`

and records the uncertainty reason instead of falling back to `stent`.

## Device Identity Lock Fields

The identity lock now carries:

- `device_type`
- `device_family`
- `intended_purpose`
- `anatomical_site`
- `clinical_domain`
- `classification_confidence`
- `supporting_source_ids`
- `evidence_spans`
- `alternative_candidates`
- `uncertainty_reason`

## Domain Mismatch Guard

The identity layer now emits:

`DOMAIN_MISMATCH_FLAG`

when device identity and downstream profile/SOTA/evidence/search text appear to
belong to clearly unrelated domains. For CAL-003 ligating clips, mismatch terms
include stent/urology/pyeloplasty/ureteroscope/renal pelvis and unrelated
cardiac PFA terms.

This flag is only a blocker/warning signal. It does not automatically repair
SOTA or evidence.

## Before / After CAL-003 Example

Before:

```json
{
  "intended_purpose": "ligating of tubular structures or vessels",
  "device_type": "stent",
  "anatomical_site": "urinary tract",
  "clinical_domain": "urology/stent-contaminated"
}
```

After:

```json
{
  "device_type": "ligating clip",
  "device_family": "surgical ligating clip",
  "clinical_domain": "surgical_ligating_clip",
  "classification_confidence": "high",
  "supporting_source_ids": ["SRC-IFU-001"],
  "anatomical_site": "tubular structures or vessels as defined in the IFU",
  "mode_of_action": "Mechanical ligation or occlusion of tubular structures or vessels using a clip.",
  "evidence_span": "TF-TLC-0301_IFU-Ligating clips(Ti) ... ligating of tubular structures or vessels ..."
}
```

## Changed Files

- `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py`
- `backend/tests/test_cer_authoring_runtime.py`
- `docs/cer_authoring_phase0/PHASE0_4_DEVICE_IDENTITY_REPAIR_REPORT.md`

## Regression Coverage

Added tests for:

- CAL-003 ligating clip fixture is not classified as stent;
- CAL-002-style hemoperfusion / adsorber cartridge fixture does not fall into
  unrelated stent type;
- CAL-001 PADN / RF ablation catheter remains a reasonable ablation-catheter
  classification;
- unclear input returns `UNKNOWN_WITH_CANDIDATES` and not stent;
- locked final package sources do not participate in writer device identity;
- ligating-clip domain mismatch guard flags stent/urology/pyeloplasty evidence
  contamination.

## Verification

Commands run:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
backend/.venv/bin/python -m compileall -q backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py
```

Observed result:

```text
25 passed
compileall passed
```

## Boundary Statement

This is a Phase 0 intake/identity blocker repair. It is not Phase 2. It does
not run Project 2/3, does not consume holdout data, and does not read locked
`02_/03_` project content.

## Conclusion

`PHASE0_4_DEVICE_IDENTITY_REPAIR_READY_FOR_CCD_ACCEPTANCE`

CAL-003 should only be rerun after CCD accepts this repair.
