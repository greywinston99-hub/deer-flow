# STACK A CONFIGURATION USED

> VS Code Claude Code | 2026-05-15 | PILOT_02 MIDOS Stack A

## Project

**PILOT_02** Cardiac Tissue Stabilizer / 米道斯心脏固定器

## Input

```
/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/01_AUTHORING_INPUT_ALLOWED/
├── 01_IFU_REQUIRED/
├── 02_RMF_RISK_MANAGEMENT_REQUIRED/
├── 03_GSPR_REQUIRED/
├── 04_DOMESTIC_CLINICAL_DATA_OPTIONAL/
├── 05_CLIENT_PROVIDED_CLINICAL_REFERENCES_REFERENCE_ONLY/
├── 06_TEST_VALIDATION_REPORTS_OPTIONAL_RELEVANT_ONLY/
├── 07_SIMILAR_COMPETITOR_DEVICES_OPTIONAL/
└── 08_OTHER_PRODUCT_MATERIALS_OPTIONAL/
```

## Artifact Output

**Supervisor-computed** (not STACK_A_CONFIGURATION.md specified):
```
artifacts/cer_cowork/PILOT_02_MIDOS_STACK_A/authoring/stack_a_v1/deerflow_authoring/
```

STACK_A_CONFIGURATION.md specified: `.../02_AI_BASELINE_OUTPUT_FREEZE/stack_a/`
Supervisor cannot accept --artifact-root CLI param; uses computed path instead.

## Model Assignment (Stack A)

| Agent | Model | Route Source |
|-------|-------|-------------|
| intake-profile-claim | kimi-k2.6-code | env_var |
| methodology-sota | deepseek-v4-pro | env_var |
| evidence | deepseek-v4-pro | env_var |
| cer-writer | deepseek-v4-pro | env_var |
| qa-review | deepseek-v4-pro | env_var |
| risk-equivalence-gspr | kimi-k2.6-code | env_var |
| cer-authoring-lead-agent | kimi-k2.6-code | routing_policy_v1 |

## Fixed Assets

- Frozen prompts: PROMPT_PACK_V1
- Domain template: cardiac_tissue_stabilizer
- Gate 1-5 active
- Gate 1 Domain Matrix: DOMAIN_TERM_MATRIX_V1.md
- Gate 3 Phrase Policy: EVIDENCE_CONCLUSION_PHRASE_POLICY.md

## Model Boundaries Enforced

- kimi-k2.6-code: NOT used for Writer, QA, Evidence Reasoning
- MiniMax: disabled entirely for this run
- Kimi API: reserved as Writer B candidate (Stack B only)
- DeepSeek V4 Pro: allowed for all agents

## Preflight

MODEL_RESOLUTION_TRACE_STACK_A_PREFLIGHT.json: ALL CHECKS PASS

---
*VS Code Claude Code | 2026-05-15*
