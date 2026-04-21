# CER Structure Compliance Agent Prompt

**Schema:** cer_prompt_contract_v1
**Step ID:** cer_l1_compliance
**Handler:** _run_l1_compliance
**Prompt Version:** stub_v1
**Status:** STUB — requires full prompt engineering

## Input Contract

What this agent receives:
- CERDocStruct (reference)
- CER main document

## Output Contract

What this agent produces:
- Artifact path: `artifacts/cer/{project_id}/cer_review/{cer_run_id}/02_l1_compliance/l1_report.json`
- Output type: L1 compliance report
- Schema ref: cer_l1.schema.json

## Clinical Logic Alignment

How this maps to D0A dimensions:
- D0A Review Dimension: STRUCTURE (dim_2)
- Regulatory anchor: MDR Annex XIV

## Known Limitations (Stub)

- Full Annex XIV checklist not implemented
- Section presence check only

## Prompt Template

You are the CER Structure Compliance Agent. Your task is to check if the CER document meets MDR Annex XIV structural requirements.

### Instructions

1. Load CERDocStruct
2. Check required sections present
3. Report missing sections
4. Produce L1 compliance report
