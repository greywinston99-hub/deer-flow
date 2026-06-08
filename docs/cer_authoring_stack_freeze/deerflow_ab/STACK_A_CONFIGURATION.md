# STACK A CONFIGURATION

> CCD | 2026-05-15 | Initial Candidate for DeerFlow Runtime Validation

## Project

PILOT_02 Cardiac Tissue Stabilizer / 米道斯心脏固定器

**Input**: `/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/01_AUTHORING_INPUT_ALLOWED`

**Artifact Output**: `.../CER_PILOT_STANDARD_02米道斯/02_AI_BASELINE_OUTPUT_FREEZE/stack_a/`

## Model Assignment

| Agent | Model | Reason |
|-------|-------|--------|
| intake-profile-claim | kimi-k2.6-code | Structured extraction. Current model validated through pipeline. |
| methodology-sota | deepseek-v4-pro | Reasoning + clinical knowledge. PICO construction, search strategy. |
| evidence | deepseek-v4-pro | Evidence appraisal. Quantitative + domain precision. |
| cer-writer | deepseek-v4-pro | Best candidate for professional medical writing. |
| qa-review | deepseek-v4-pro | Detection sensitivity. |
| risk-equivalence-gspr | kimi-k2.6-code | Structured mapping. Not writing-intensive. |

## Fixed Assets (All Runs)

- Frozen prompts: PROMPT_PACK_V1
- Domain template: cardiac_tissue_stabilizer (from Phase 2A)
- Gate 1-5 active
- Gate 1 Domain Matrix: DOMAIN_TERM_MATRIX_V1.md
- Gate 3 Phrase Policy: EVIDENCE_CONCLUSION_PHRASE_POLICY.md

## Model Boundaries

- kimi-k2.6-code: NOT used for Writer, QA, Evidence Reasoning
- MiniMax: disabled entirely for this run
- Kimi API: reserved as Writer B candidate (Stack B only)
- DeepSeek V4 Pro: allowed for all agents

## Run Command

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow

CER_AUTHORING_MODEL_CER_WRITER=deepseek-v4-pro \
CER_AUTHORING_MODEL_QA_REVIEW=deepseek-v4-pro \
CER_AUTHORING_MODEL_METHODOLOGY_SOTA=deepseek-v4-pro \
CER_AUTHORING_MODEL_EVIDENCE=deepseek-v4-pro \
backend/.venv/bin/python backend/scripts/run_cer_authoring.py \
  --project-id PILOT_02_MIDOS_STACK_A \
  --input-root "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/01_AUTHORING_INPUT_ALLOWED" \
  --artifact-root "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/02_AI_BASELINE_OUTPUT_FREEZE/stack_a/" \
  --strict-v7 --agent-team-mode stable-1plus6
```

## Required Outputs per Run

- MODEL_RESOLUTION_TRACE.json: all 7 agents, actual resolved model, route source, provider status
- CER draft
- Gate results (qa_gate_report.json)
- Quarantine/release status
- Human reviewability rubric applied
- Section-level audit (see STACK_A_SECTION_LEVEL_AUDIT template)

## Stack B Trigger

Stack B only created if Stack A audit identifies a specific, model-attributable defect. Stack B changes exactly 1-2 variables. Not a new full matrix.

---

*CCD 签发：2026-05-15*
