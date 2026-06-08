# KNOWN GOOD COMMAND USED — Stack A

> VS Code Claude Code | 2026-05-15 | PILOT_02 MIDOS Stack A

## Runtime Path

1. **Supervisor**: `scripts/cer_cowork_supervisor.py authoring-start`
2. **Underlying**: `backend/scripts/run_cer_authoring.py --strict-v7 --agent-team-mode stable-1plus6`
3. **Agent Team**: `stable-1plus6` (7 agents)

## Exact Command

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow

CER_AUTHORING_MODEL_CER_WRITER=deepseek-v4-pro \
CER_AUTHORING_MODEL_QA_REVIEW=deepseek-v4-pro \
CER_AUTHORING_MODEL_METHODOLOGY_SOTA=deepseek-v4-pro \
CER_AUTHORING_MODEL_EVIDENCE=deepseek-v4-pro \
CER_AUTHORING_MODEL_INTAKE_PROFILE_CLAIM=kimi-k2.6-code \
CER_AUTHORING_MODEL_RISK_EQUIVALENCE_GSPR=kimi-k2.6-code \
backend/.venv/bin/python scripts/cer_cowork_supervisor.py authoring-start \
  --project-id PILOT_02_MIDOS_STACK_A \
  --input-root "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/01_AUTHORING_INPUT_ALLOWED" \
  --run-id stack_a_v1 \
  --background
```

## Supervisor Hardcoded Flags

The supervisor at line 403-405 always passes:
- `--strict-v7`
- `--agent-team-mode stable-1plus6`
- `--json`

## Model Env Vars (Per-Agent Overrides)

| Env Var | Value | Agent |
|---------|-------|-------|
| CER_AUTHORING_MODEL_CER_WRITER | deepseek-v4-pro | cer-writer |
| CER_AUTHORING_MODEL_QA_REVIEW | deepseek-v4-pro | qa-review |
| CER_AUTHORING_MODEL_METHODOLOGY_SOTA | deepseek-v4-pro | methodology-sota |
| CER_AUTHORING_MODEL_EVIDENCE | deepseek-v4-pro | evidence |
| CER_AUTHORING_MODEL_INTAKE_PROFILE_CLAIM | kimi-k2.6-code | intake-profile-claim |
| CER_AUTHORING_MODEL_RISK_EQUIVALENCE_GSPR | kimi-k2.6-code | risk-equivalence-gspr |

## Run Directory

```
artifacts/cer_cowork/PILOT_02_MIDOS_STACK_A/authoring/stack_a_v1/
├── deerflow_authoring/     ← artifact_root
├── status.json
├── stdout.log
├── stderr.log
├── command.sh
├── run_config.json
└── supervisor_questions.md
```

## Verified At Launch

- Supervisor help: OK
- run_cer_authoring.py help: OK (--strict-v7, --agent-team-mode stable-1plus6)
- Input root exists: OK (IFU found by supervisor)
- Model resolution preflight: ALL 7 AGENTS PASS
- No MiniMax in critical path: CONFIRMED

---
*VS Code Claude Code | 2026-05-15*
