# MODEL TASK INTELLIGENCE MATRIX

> CCD | 2026-05-15 | Updated for 4-model pool

## Available Pool

| 模型 | 类型 | 适用 |
|------|------|------|
| kimi-k2.6-code | 代码 | 结构化提取、确定性任务 |
| kimi API | 通用 | 中等复杂度推理、备选 Writer/QA |
| deepseek V4 pro | 通用+推理 | 强推理、医学写作、QA 检测 |
| minimax M2.7 highspeed | 快速 | 高吞吐非精度关键任务 |

## Task Categories and Model Matching

### Extraction / Structuring

| 维度 | 内容 |
|------|------|
| **Agents** | intake-profile-claim |
| **任务** | IFU 文本 → 设备画像。结构化字段提取。 |
| **所需智能** | 指令遵循、结构化输出、无幻觉 |
| **首选** | kimi-k2.6-code — 已验证，结构化输出可靠 |
| **备选** | kimi API |
| **不建议** | minimax — 幻觉风险未知 |
| **风险** | 字段级幻觉（编造不存在的设备属性） |
| **Fallback** | 确定性规则（不用 LLM） |

### Retrieval / Screening

| 维度 | 内容 |
|------|------|
| **Agents** | MCP adapters（非 agent） |
| **任务** | PubMed/PMC/CT.gov API 调用 |
| **所需智能** | 非模型依赖。API 可靠性。 |
| **首选** | N/A — 确定性 API 调用 |
| **风险** | 网络/API 不可达、静默失败 |

### Evidence Reasoning

| 维度 | 内容 |
|------|------|
| **Agents** | methodology-sota, evidence |
| **任务** | 搜索策略、证据评价、声明推理 |
| **所需智能** | 领域精度、定量推理、结构化判断 |
| **首选** | deepseek V4 pro — 强推理 + 临床知识 |
| **备选** | kimi API |
| **不建议** | minimax — 精度不足；kimi-code — 非推理模型 |
| **风险** | 跨领域漂移、证据不足时声称支持 |

### BR / PMCF Reasoning

| 维度 | 内容 |
|------|------|
| **Agents** | risk-equivalence-gspr |
| **任务** | 受益风险分析、PMCF 差距识别 |
| **所需智能** | 结构化映射、定量权衡 |
| **首选** | deepseek V4 pro 或 kimi-k2.6-code |
| **不建议** | minimax |
| **风险** | 不对等对待受益和风险 |

### CER Writer

| 维度 | 内容 |
|------|------|
| **Agents** | cer-writer |
| **任务** | CER 正文生成 |
| **所需智能** | 专业医学写作、领域一致性、证据忠实、约束遵循 |
| **首选** | deepseek V4 pro — 最强医学写作候选 |
| **备选** | kimi API — 需 A/B 评估 |
| **禁止** | kimi-k2.6-code — 已知模板复用、语言泄漏。minimax — 精度不足。 |
| **风险** | 领域串线、内部语言泄漏、证据矛盾、IFU 不消费 |

### QA Reviewer

| 维度 | 内容 |
|------|------|
| **Agents** | qa-review |
| **任务** | Gate 1-5 检查、人工可审查性验证 |
| **所需智能** | 检测敏感性、系统评估、无假 PASS |
| **首选** | deepseek V4 pro — 强推理检测 |
| **备选** | kimi API |
| **禁止** | minimax — 假阳性/假阴性风险 |
| **风险** | 假 PASS（污染报告给高分） |

### Controller / Triage

| 维度 | 内容 |
|------|------|
| **Agents** | Gate evaluation functions（非 agent） |
| **任务** | Gate 判定、quarantine 路由 |
| **所需智能** | 非模型依赖。确定性规则。 |
| **首选** | N/A — 确定性代码 |
| **风险** | 规则过于脆弱（关键词扫描过严/过松） |

---

*CCD 签发：2026-05-15*
