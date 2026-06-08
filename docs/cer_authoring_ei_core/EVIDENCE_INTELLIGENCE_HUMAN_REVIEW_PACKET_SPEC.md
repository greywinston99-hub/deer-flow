# EVIDENCE INTELLIGENCE HUMAN REVIEW PACKET SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## ⚠️ 分层触发

**仅高影响力不确定性触发人工审查。** 不是所有低置信度都扔给人工。
分三层：Tier 1 自动、Tier 2 标记、Tier 3 阻塞。

---

## 一、Tier 1 — Automatic（自动处理）

系统自动处理，不入人工审查包。仅记录在 reasoning_audit_ledger 和 human_review_queue。

| 触发条件 | 处理方式 | 记录位置 |
|---|---|---|
| 单个 low-confidence fact | 自动降级到 background | audit_ledger + HRQ |
| normalization_failure | 自动标记，入 HRQ（非阻塞） | HRQ |
| 非关键端点的 MEDIUM 冲突 | 自动标记 | audit_ledger + HRQ |
| TRANSLATION_NEEDED | 自动入 HRQ | HRQ |
| not_searched 缺失 | 标记限制 | audit_ledger |

---

## 二、Tier 2 — Flagged（标记审查，不阻塞）

系统继续推理但标记审查点。生成 human_review_packet entry，但 decision_required = false。

| 触发条件 | 处理方式 | 下游影响 |
|---|---|---|
| HIGH conflict（magnitude / statistical） | 标记 claim，降低结论强度至 CAUTIOUS | conclusion_strength 降级 |
| 缺失非关键端点 | 标记 gap，触发 PMCF | PMCF gap generated |
| 等效论证使用 indirect 证据 | 标记限制条件 | bridging_limitations 加注 |
| benchmark_confidence = low | 标记 NR 字段 | SOTA 标注 limited confidence |
| br_acceptability_confidence = low | 标记 BR 限制 | BR conclusion = borderline |
| pmcf_gap_severity = high | 标记高优先级 gap | PMCF objective generated |
| searched_not_found 缺失 | 标记限制 | claim 标注 evidence limitation |
| CER/RMF mismatch（MEDIUM） | 标记不一致 | crosswalk mismatch flag |

---

## 三、Tier 3 — Blocking（阻塞，需人工决策）

系统暂停推理链。生成 human_review_packet entry，decision_required = true。被阻塞的组件等待人工输入。

| 触发条件 | 阻塞范围 | 决策选项 |
|---|---|---|
| CRITICAL conflict（directional） | 阻塞相关 claim | [A] 采纳研究 A 证据 [B] 采纳研究 B 证据 [C] 两者皆不采纳 [D] 补充证据后重跑 |
| 缺失安全关键端点（如无 AE 数据） | 阻塞 BR conclusion | [A] 接受当前证据限制 [B] 补充安全性数据 [C] 限制适应症 [D] 放弃 |
| 等效论证完全失败 | 阻塞等效路径 | [A] 降级为 similar device [B] 补充 equivalence rationale [C] 移除等效路径 [D] 放弃 |
| conclusion_strength = INSUFFICIENT（对关键声明） | 阻塞 Writer（该 claim） | [A] 接受限制（生成 CAUTIOUS 声明）[B] 补充证据后重跑 [C] 标记为无法得出结论 [D] 放弃 |
| br_acceptability_confidence = insufficient_evidence | 阻塞 BR output | [A] 补充证据 [B] 接受限制 [C] 放弃 |
| pmcf_gap_severity = critical | 阻塞 PMCF output | [A] 确认 gap [B] 补充数据 [C] 调整 gap severity |
| CER/RMF mismatch（HIGH） | 阻塞 crosswalk 相关 claim | [A] 接受不一致 [B] 更新 RMF [C] 更新 CER |

---

## 四、Human Review Packet 结构

```text
review_packet:
  packet_id: str                # HRP-###
  tier: int                     # 2 | 3
  trigger: str                  # 触发条件代码
  trigger_detail: str           # 人类可读触发描述
  affected_claims: [str]        # CLAIM-###
  affected_evidence: [str]      # EVID-###
  evidence_summary:             # 受影响证据的摘要
    evidence_count: int
    quality_tiers: [str]
    conflict_summary: str|null
  current_state:                # 当前推理状态
    conclusion_strength: str
    br_judgment: str|null
    pmcf_gaps: [str]
  decision_options: [           # 决策选项
    {option_id: str, description: str, consequence: str}
  ]
  recommendation: str           # 系统推荐选项
  decision_required: bool       # Tier 2: false, Tier 3: true
  deadline_signal: str          # routine / urgent
  human_decision: str|null      # 待人工填写
  human_rationale: str|null     # 待人工填写
  resolved_at: str|null         # 待人工填写
```

---

## 五、审查包输出

```text
human_review_packet:
  packets: [review_packet]
  tier_summary:
    tier_1_auto_handled: int
    tier_2_flagged: int
    tier_3_blocked: int
  blocking_claims: [str]        # Tier 3 阻塞的声明列表
```

输出文件：`human_review_packet.json`

---

## 六、人工决策后的流转

| 决策 | 流转动作 |
|---|---|
| Accept with limitation | 系统以 CAUTIOUS 继续，记录限制 |
| Supplement evidence | 人工补充证据 → 重跑 Intelligence Core |
| Downgrade claim | 移除该声明或降为 INSUFFICIENT |
| Override（人工提升） | human_reviewed → score_calibration_status = human_reviewed |
| Abandon | Controlled Compromise |

---

## 七、禁止

- ❌ 将所有低置信度事实扔给人工
- ❌ 将 Tier 2 当 Tier 3 阻塞
- ❌ 自动决策后不记录审计
- ❌ 人工决策后不更新 downstream 推理
- ❌ Tier 3 未解决时继续 Writer

---

*CCD 签发：2026-05-12*
