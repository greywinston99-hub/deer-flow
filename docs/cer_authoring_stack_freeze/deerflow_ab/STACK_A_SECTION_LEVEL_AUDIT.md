# STACK A SECTION-LEVEL AUDIT — Template

> To be completed after Stack A DeerFlow run

## Audit Sections

For each CER section, check the following and classify every finding by root cause.

### 1. Summary

| Finding | Root Cause | Severity |
|---------|-----------|----------|
| | | |

### 2.1 Device Description

| Field | Content | Source Anchor | Root Cause if Missing/Wrong |
|-------|---------|--------------|---------------------------|
| composition | | | |
| working principle | | | |
| performance | | | |
| variants | | | |
| sterility | | | |

### 2.2 Intended Purpose

| Finding | Root Cause | Severity |
|---------|-----------|----------|
| | | |

### 3.x SOTA / Clinical Background

| Sub-section | Domain Correct? | Finding | Root Cause |
|-------------|----------------|---------|-----------|
| 3.1 Clinical context | | | |
| 3.2 Disease/condition | | | |
| 3.3 Population | | | |
| 3.4 Alternative treatments | | | |
| 3.5 Guidelines | | | |
| 3.6 Benchmark devices | | | |
| 3.7 Hazards | | | |
| 3.8 SOTA PICO/search | | | |

### 4.x Clinical Evidence

| Sub-section | Finding | Root Cause |
|-------------|---------|-----------|
| 4.1 Evidence pathway | | |
| 4.2 Manufacturer data | | |
| 4.3 Preclinical | | |
| 4.4 Clinical data | | |
| 4.5 PMS/PMCF | | |
| 4.6 Vigilance | | |
| 4.7 By GSPR | | |

### 5. Conclusion

| Finding | Root Cause | Severity |
|---------|-----------|----------|
| | | |

### Annex / Submission Body

| Finding | Root Cause | Severity |
|---------|-----------|----------|
| | | |

## Root Cause Classification

Every finding must be classified as one of:
- `model_issue`: Writer/QA model quality problem
- `prompt_issue`: Agent prompt missing or wrong instruction
- `template_issue`: Template structure or content problem
- `ifu_source_issue`: IFU text not consumed or not extracted
- `evidence_reasoning_issue`: EI Core or SOTA reasoning defect
- `gate_issue`: Gate rule too strict/loose
- `external_access_issue`: MCP/API/database unavailable
- `owner_methodology_issue`: PICO scope, search strategy, domain definition

## Stack B Decision

Based on audit findings, determine:
- Top 1-2 root causes
- Whether any can be addressed by model switch (Writer → Kimi API) or prompt/template fix
- Exact Stack B change with expected improvement

---

*CCD 签发：2026-05-15*
