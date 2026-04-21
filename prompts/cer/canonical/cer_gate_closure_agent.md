# CER Gate Closure Agent Prompt

**Schema:** cer_prompt_contract_v1
**Step ID:** cer_gate_closure
**Handler:** _run_gate_closure
**Prompt Version:** stub_v1
**Status:** STUB — requires full prompt engineering

## Input Contract

What this agent receives:
- Human gate decision
- All preceding artifacts
- Review package components

## Output Contract

What this agent produces:
- Artifact path: `artifacts/cer/{project_id}/cer_review/{cer_run_id}/09_gate_closure/review_package.json`
- Output type: Review package
- Schema ref: cer_review_package.schema.json

## Clinical Logic Alignment

How this maps to D0A dimensions:
- D0A Review Dimension: CONCLUSION (dim_11)
- Regulatory anchor: MDR Article 83, Annex XIV

## Known Limitations (Stub)

- Gate closure logic not implemented
- Review package assembly not implemented

## Prompt Template

You are the CER Gate Closure Agent. Your task is to assemble the final review package after human gate decision.
