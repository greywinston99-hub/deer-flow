# MODEL TO AGENT MATCHING — V1

> CCD | 2026-05-15 | Based on available model pool

## Available Models

| 模型 | 类型 | 优势 | 已知限制 |
|------|------|------|---------|
| kimi-k2.6-code | 代码模型 | 结构化输出、指令遵循 | 非写作模型。CER 文本有模板复用、语言泄漏 |
| kimi API | 通用模型 | 平衡性能 | 需评估医学写作质量 |
| deepseek V4 pro | 通用+推理 | 中英文临床文本、强推理、长文本 | 当前父路由模型 |
| minimax M2.7 highspeed | 快速模型 | 速度 | 医学写作质量未知，不适合精度要求高的任务 |

## Per-Agent Matching

| Agent | 首选 | 理由 |
|-------|------|------|
| intake-profile-claim | kimi-k2.6-code | 结构化提取，不需要写作。当前模型已验证。 |
| methodology-sota | deepseek V4 pro | 搜索策略构建、领域推理。需要强推理和临床知识。 |
| evidence | deepseek V4 pro | 证据评价、声明推理。需要定量和领域精度。 |
| cer-writer | **deepseek V4 pro 或 kimi API** | 最关键选择。需要专业医学写作。kimi-code 已确认不合适。DeepSeek 是中英文临床文本的最强候选。kimi API 作为备选需评估。 |
| risk-equivalence-gspr | kimi-k2.6-code | 结构化映射，不需要写作。 |
| qa-review | deepseek V4 pro | 检测敏感性。DeepSeek 推理能力对此任务适用。 |

## Current Blocker

所有 agent 当前使用 `model="inherit"` —— 全部从父模型继承。要实施 per-agent routing 需要代码变更（`agents.py` 每 subagent 加 `model` 字段）。在此之前，只能全局切换单一模型。

## Practical Recommendation

**如果只能全局单一模型**：切换到 `deepseek V4 pro`。它在所有 6 个 agent 任务中是最平衡的选择——足够强的推理、足够好的写作、已知的中英文临床文本能力。kimi-code 保留用于 extraction 类的确定性任务。

**如果能实施 per-agent routing**：Writer → deepseek V4 pro 或 kimi API（需 A/B 确定）；QA → deepseek V4 pro；Extraction → kimi-k2.6-code；Reasoning → deepseek V4 pro。

**minimax M2.7 highspeed**：速度优势。适合高吞吐但非精度关键的任务。不推荐用于 Writer（医学写作精度要求高）或 QA（假阳性风险）。可考虑用于批量 retrieval 阶段。

## Phase 3 Approach

用 deepseek V4 pro 作为全局模型进入 Phase 3 pilot 再生。如果 per-agent routing 就绪，按上述匹配表格分配。再生后用 Gate 1-5 + human reviewability rubric 评估输出质量。

---

*CCD 签发：2026-05-15*
