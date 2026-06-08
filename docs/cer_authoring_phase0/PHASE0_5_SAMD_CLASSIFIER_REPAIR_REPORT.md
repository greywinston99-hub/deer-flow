# Phase 0.5 SaMD Classifier Repair Report

## Scope

Phase 0.5 was limited to source intake / device identity / device classification hardening. It did not modify SOTA, Evidence Appraisal, Writer, Benefit-Risk, PMCF, Alignment Engine, authoring agent prompts, or G0-G38 gate criteria.

## Changes Implemented

1. Added SaMD device-domain defaults:
   - `ai_diagnostic_software`
   - `software_medical_device`

2. Added SaMD classifier patterns:
   - English: software, software as a medical device, SaMD, medical device software, diagnostic software, software algorithm, artificial intelligence, machine learning, algorithm, diagnosis, diagnostic, clinical decision support.
   - Chinese: 软件, 医疗器械软件, 医用软件, 人工智能, 算法, 诊断, 辅助诊断, 筛查, 检测, 判读.

3. Added multi-source identity basis support:
   - IFU remains the primary source.
   - GSPR, RMF, CEP, metadata, primary authoring sources, and identity-relevant source names/metadata may contribute to device identity.
   - Locked delta-only and excluded similar-device sources remain prohibited from device-profile identity.

4. Added identity lock fields:
   - `supporting_source_types`
   - `identity_source_scope`

5. Added domain mismatch guard patterns for SaMD:
   - SaMD domains now flag obvious contamination such as stent, urinary tract, renal pelvis, nephroscope, ligating clip, ablation catheter, and hemoperfusion.

6. Added CAL-002 regression coverage:
   - AI diagnostic software is not classified as stent.
   - IFU + GSPR + metadata jointly support identity lock.
   - locked final package sources do not participate.
   - general SaMD classification does not fall back to stent.

## Changed Files

- `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py`
- `backend/tests/test_cer_authoring_runtime.py`
- `docs/cer_authoring_phase0/PHASE0_5_SAMD_CLASSIFIER_REPAIR_REPORT.md`

## Test Results

```text
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
37 passed in 5.82s

backend/.venv/bin/python -m pytest backend/tests/test_calibration_delta_analyzer.py backend/tests/test_cer_cowork_supervisor.py -q
12 passed in 0.76s

backend/.venv/bin/python -m compileall -q backend/packages/harness/deerflow/runtime/cer_authoring
PASS
```

## Before / After Example

Before Phase 0.5, software-only or AI diagnostic devices could pass through generic `software` handling and still lacked an explicit SaMD device-family/domain lock.

After Phase 0.5, a CAL-002 source set containing:

- IFU: "software algorithm analyses medical images to assist diagnosis"
- GSPR: "software as a medical device ... artificial intelligence ... diagnostic support"
- Metadata: "SaMD ... AI diagnostic software"

is classified as:

```json
{
  "device_type": "AI diagnostic software",
  "device_family": "software as a medical device",
  "clinical_domain": "ai_diagnostic_software",
  "classification_confidence": "high"
}
```

Locked final-package text such as `stent urinary tract renal pelvis pyeloplasty` is excluded from the identity basis and cannot define the subject device profile.

## Conclusion

`PHASE0_5_ACCEPTED_FOR_CAL002_SAMD_REGRESSION`
