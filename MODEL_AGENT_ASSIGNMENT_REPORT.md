# MODEL_AGENT_ASSIGNMENT_REPORT

Status: MODEL_AGENT_ASSIGNMENT_CONFIGURED

Scope: DeerFlow CER Authoring `stable-1plus6` Agent Team.

Configuration mechanism: centralized routing policy in `backend/packages/harness/deerflow/runtime/cer_authoring/writer_remediation/model_routing.py`.

No prompt, template, gate, graph, agent definition, Pilot, A/B, or runtime entry refactor was changed.

## Actual Mapping

| agent_name | role | configured_model |
|---|---|---|
| `cer-authoring-lead-agent` | lead / controller agent | `kimi-k2.6-code` |
| `authoring-intake-profile-claim-agent` | intake / device profile / IFU structured extraction / structured claim-fact intake | `kimi-k2.6-code` |
| `authoring-methodology-sota-agent` | SOTA reasoning / methodology / endpoint benchmark reasoning | `deepseek-v4-pro` |
| `authoring-evidence-agent` | evidence appraisal / endpoint extraction / claim support reasoning | `deepseek-v4-pro` |
| `authoring-risk-equivalence-gspr-agent` | risk / equivalence / GSPR / benefit-risk / PMCF reasoning | `deepseek-v4-pro` |
| `authoring-cer-writer-agent` | CER writer agent | `deepseek-v4-pro` |
| `authoring-qa-review-agent` | QA / reviewer agent | `deepseek-v4-pro` |

## Risk / Equivalence Note

`authoring-risk-equivalence-gspr-agent` is a mixed stable-1plus6 physical agent. It covers structured comparability, clinical equivalence, vigilance, risk/GSPR, benefit-risk, and PMCF-style reasoning in one agent. Because clinical equivalence reasoning and admissibility judgment are in scope, the stable physical agent is configured as `deepseek-v4-pro`.

The routing policy records `structured_comparability_model = kimi-k2.6-code` for a future finer split, but no new split or complex routing logic was added in this change.

## Model Boundary Check

| requirement | result |
|---|---|
| stable-1plus6 no longer all inherit one `kimi-k2.6-code` model | PASS |
| Writer configured as `deepseek-v4-pro` | PASS |
| QA configured as `deepseek-v4-pro` | PASS |
| SOTA / evidence / claim / BR / PMCF reasoning configured as `deepseek-v4-pro` | PASS |
| extraction / intake / structured fact configured as `kimi-k2.6-code` | PASS |
| MiniMax not enabled in key chain | PASS |
| Kimi API not a default model | PASS |
| `graph.py`, `gates.py`, `agents.py` unchanged by this task | PASS |

## Runtime Provider Check

`deepseek-v4-pro` is configured in `config.yaml` with `deerflow.models.patched_deepseek:PatchedChatDeepSeek`, `api_base = https://api.deepseek.com/v1`, and `api_key = $DEEPSEEK_API_KEY`.

Provider instantiation check: PASS.

Minimal live provider smoke: PASS (`deepseek-v4-pro` returned `OK`).
