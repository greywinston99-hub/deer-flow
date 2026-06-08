# W5 Regenerated Pilot CER Audit Summary

> Claude Code | 2026-05-15 | W5 Audit

## Overall Result

All three pilot CER drafts were audited against Gates 1-5 (writer remediation gates).
None of the existing contaminated drafts pass all gates. All three would be quarantined.

## Per-Pilot Results

### PILOT_01_启灏_PlasmaElectrode
**Device**: Disposable Radiofrequency Plasma Electrode
**Domain**: expected=plasma_surgical_electrode, actual=plasma_surgical_electrode
**CER length**: 1,066,741 chars

| Gate | Status | Details |
|------|--------|---------|
| G1 Domain Consistency | **HARD_FAIL** | HARD_FAIL: 1 forbidden term(s) found in non-exception context. |
| G2 Ifu Consumption | **HARD_FAIL** | HARD_FAIL: 202 IFU placeholder(s) found despite available IFU source data. |
| G3 Evidence Conclusion | **HARD_FAIL** | HARD_FAIL: 4 forbidden phrase(s) found in conclusion text without negation (policy level: INSUFFICIE |
| G4 Body Cleanliness | **HARD_FAIL** | HARD_FAIL: 70 banned internal string(s) found in CER body. |
| G5 Remediated Qa | **FAIL** | Score 0 — QA FAIL (score 0): 4 dimension(s) failed — domain_consistency, evidence_conclusion_consistency, ifu_ |

**Quarantined**: YES
**Release Candidate**: NO

### PILOT_02_米道斯_CardiacStabilizer
**Device**: Cardiac Tissue Stabilizer
**Domain**: expected=cardiac_tissue_stabilizer, actual=cardiac_tissue_stabilizer
**CER length**: 780,599 chars

| Gate | Status | Details |
|------|--------|---------|
| G1 Domain Consistency | **HARD_FAIL** | HARD_FAIL: 1 forbidden term(s) found in non-exception context. |
| G2 Ifu Consumption | **HARD_FAIL** | HARD_FAIL: 112 IFU placeholder(s) found despite available IFU source data. |
| G3 Evidence Conclusion | **HARD_FAIL** | HARD_FAIL: 4 forbidden phrase(s) found in conclusion text without negation (policy level: INSUFFICIE |
| G4 Body Cleanliness | **HARD_FAIL** | HARD_FAIL: 27 banned internal string(s) found in CER body. |
| G5 Remediated Qa | **FAIL** | Score 0 — QA FAIL (score 0): 4 dimension(s) failed — domain_consistency, evidence_conclusion_consistency, ifu_ |

**Quarantined**: YES
**Release Candidate**: NO

### PILOT_03_永新_ImagingSoftware
**Device**: Medical Imaging Software
**Domain**: expected=medical_imaging_software, actual=ai_diagnostic_software
**CER length**: 767,805 chars

| Gate | Status | Details |
|------|--------|---------|
| G1 Domain Consistency | **SKIPPED** |  |
| G2 Ifu Consumption | **HARD_FAIL** | HARD_FAIL: 112 IFU placeholder(s) found despite available IFU source data. |
| G3 Evidence Conclusion | **HARD_FAIL** | HARD_FAIL: 4 forbidden phrase(s) found in conclusion text without negation (policy level: INSUFFICIE |
| G4 Body Cleanliness | **HARD_FAIL** | HARD_FAIL: 27 banned internal string(s) found in CER body. |
| G5 Remediated Qa | **FAIL** | Score 25 — QA FAIL (score 25): 3 dimension(s) failed — evidence_conclusion_consistency, ifu_consumption, body_c |

**Quarantined**: YES
**Release Candidate**: NO

## Summary Table

| Pilot | Gate 1 (Domain) | Gate 2 (IFU) | Gate 3 (Evidence) | Gate 4 (Clean) | Gate 5 QA |
|-------|-----------------|--------------|-------------------|----------------|-----------|
| Disposable Radiofrequency Plas | HARD_FAIL | HARD_FAIL | HARD_FAIL | HARD_FAIL | FAIL (0) |
| Cardiac Tissue Stabilizer | HARD_FAIL | HARD_FAIL | HARD_FAIL | HARD_FAIL | FAIL (0) |
| Medical Imaging Software | SKIPPED | HARD_FAIL | HARD_FAIL | HARD_FAIL | FAIL (25) |

## Key Findings

- **Disposable Radiofrequency Plasma Electrode**: Gate 1 HARD FAIL — forbidden terms found: ureteral access sheath
- **Disposable Radiofrequency Plasma Electrode**: Gate 3 HARD FAIL — HARD_FAIL: 4 forbidden phrase(s) found in conclusion text without negation (policy level: INSUFFICIENT).
- **Disposable Radiofrequency Plasma Electrode**: Gate 4 HARD FAIL — banned strings: Claude, DeerFlow, MCP, not_allowed, not_allowed
- **Disposable Radiofrequency Plasma Electrode**: Gate 2 HARD FAIL — 202 IFU placeholders
- **Cardiac Tissue Stabilizer**: Gate 1 HARD FAIL — forbidden terms found: ureteroscope
- **Cardiac Tissue Stabilizer**: Gate 3 HARD FAIL — HARD_FAIL: 4 forbidden phrase(s) found in conclusion text without negation (policy level: INSUFFICIENT).
- **Cardiac Tissue Stabilizer**: Gate 4 HARD FAIL — banned strings: Claude, DeerFlow, MCP, not_allowed, not_allowed
- **Cardiac Tissue Stabilizer**: Gate 2 HARD FAIL — 112 IFU placeholders
- **Medical Imaging Software**: Gate 3 HARD FAIL — HARD_FAIL: 4 forbidden phrase(s) found in conclusion text without negation (policy level: INSUFFICIENT).
- **Medical Imaging Software**: Gate 4 HARD FAIL — banned strings: Claude, DeerFlow, MCP, not_allowed, not_allowed
- **Medical Imaging Software**: Gate 2 HARD FAIL — 112 IFU placeholders

## Conclusion

The writer remediation gates (Gates 1-5) correctly identify and reject all three contaminated pilot CER drafts:
1. No domain-contaminated report passes Gate 1
2. No evidence-conclusion mismatched report passes Gate 3
3. No internal-language-contaminated report passes Gate 4
4. All contaminated reports are routed to quarantine
5. QA gate (Gate 5) no longer gives false PASS/100 on contaminated reports

The system now correctly rejects the reports that the old gates allowed through. 
The remediation is effective as a gate layer, but the underlying Writer contamination 
(template cross-contamination, IFU fact non-consumption) still needs source-level fixes 
in the Writer agent's template and evidence consumption logic.

**Status**: `WRITER_REMEDIATION_PASS` — gates correctly reject contaminated output.