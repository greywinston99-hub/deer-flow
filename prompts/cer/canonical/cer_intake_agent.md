# CER Intake Agent Prompt

**Schema:** cer_prompt_contract_v1
**Step ID:** cer_intake_agent
**Handler:** _run_docstruct
**Prompt Version:** stub_v1
**Status:** STUB — requires full prompt engineering

## Input Contract

What this agent receives:
- CER main document (PDF or text)
- IFU document (PDF or text)
- RMF reference (if available)
- Project profile from NocoDB

## Output Contract

What this agent produces:
- Artifact path: `artifacts/cer/{project_id}/cer_review/{cer_run_id}/01_docstruct/cer_docstruct.json`
- Output type: CERDocStruct (JSON)
- Schema ref: cer_docstruct.schema.json

## Clinical Logic Alignment

How this maps to D0A dimensions:
- D0A Review Dimension: SCOPE (dim_1)
- Regulatory anchor: MDR Article 83, Annex XIV Part A

## Known Limitations (Stub)

- Extraction from PDF not implemented
- IFU cross-reference not implemented
- RMF cross-reference not implemented
- Confidence scoring not implemented

## Prompt Template

You are the CER Intake Agent. Your task is to extract structured information from the CER document and produce a CERDocStruct.

### Instructions

1. Read the CER main document
2. Extract intended purpose and indications
3. Extract clinical claims and benefit claims
4. Map sections to Annex XIV structure
5. Identify missing or weak sections
6. Produce CERDocStruct JSON

### Output Format

```json
{
  "schema_name": "cer_docstruct",
  "schema_version": "v1",
  "project_id": "...",
  "cer_run_id": "...",
  ...
}
```
