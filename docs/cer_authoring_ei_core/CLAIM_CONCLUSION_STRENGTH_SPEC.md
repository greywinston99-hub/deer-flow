# CLAIM CONCLUSION STRENGTH SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## 一、四级结论强度

| 强度 | 中文标签 | 英文标签 | 含义 |
|---|---|---|---|
| **STRONG** | 「证实」「已确认」 | "demonstrated", "confirmed" | 证据充分且一致地支撑声明 |
| **MODERATE** | 「支持」「表明」 | "supported", "indicated" | 证据支撑声明但非最优 |
| **CAUTIOUS** | 「提示」「有限证据表明」 | "suggested", "limited evidence suggests" | 证据薄弱或间接 |
| **INSUFFICIENT** | 「当前证据无法得出结论」 | "current evidence is insufficient to conclude" | 证据不足以做任何肯定性声明 |

---

## 二、判定条件

### 2.1 STRONG

| 条件 | 检查来源 |
|---|---|
| ≥2 subject device evidence items | Claim Reasoning: matching_evidence_count |
| 全部 evidence quality_tier ≥ good | Evidence Scoring: evidence_quality_tier |
| 方向一致（无 DIRECTIONAL 冲突） | Evidence Conflict Report |
| 无 CRITICAL 冲突 | Evidence Conflict Report |
| G42 PASS | Gates: G42 per-claim sufficiency |
| claim_support_level = STRONG | Claim Reasoning |

### 2.2 MODERATE

| 条件 | 检查来源 |
|---|---|
| ≥1 subject device evidence | Claim Reasoning |
| quality_tier ≥ acceptable | Evidence Scoring |
| 方向一致 | Evidence Conflict Report |
| 无 CRITICAL 冲突 | Evidence Conflict Report |
| claim_support_level ≥ MODERATE | Claim Reasoning |

### 2.3 CAUTIOUS

| 条件（任一触发） |
|---|
| 仅有 indirect / equivalent evidence（无 subject device direct evidence） |
| evidence quality_tier = marginal |
| 存在 HIGH 冲突 |
| claim_support_level = WEAK |
| br_acceptability_confidence ≤ low |

### 2.4 INSUFFICIENT

| 条件（任一触发） |
|---|
| 无 subject device 证据 |
| 全部 evidence quality_tier ≤ marginal |
| 全部 low-confidence facts |
| 存在未解决的 CRITICAL 冲突 |
| claim_support_level = INSUFFICIENT |
| br_acceptability_confidence = insufficient_evidence |

---

## 三、结论强度上限推导

结论强度取所有下游推理的 min：

```text
max_conclusion_strength = min(
  claim_support_level → strength,
  evidence_quality → contribution,
  conflict_severity → downgrade,
  bridging_assessment → max_strength (for indirect evidence),
  br_acceptability_confidence → strength_equivalent
)
```

### 3.1 冲突降级映射

| 冲突 | 降级 |
|---|---|
| CRITICAL conflict | → INSUFFICIENT |
| HIGH conflict | → CAUTIOUS（降一级 from base） |
| MEDIUM conflict | → 不降级（但标记） |

### 3.2 BR 置信度映射

| br_acceptability_confidence | 对结论强度的影响 |
|---|---|
| high | 不限制 |
| medium | → 上限 MODERATE |
| low | → 上限 CAUTIOUS |
| insufficient_evidence | → INSUFFICIENT |

---

## 四、Writer 硬约束

### 4.1 Allowed Language per Strength

| 强度 | 允许的措辞 | 禁止的措辞 |
|---|---|---|
| STRONG | demonstrated, confirmed, established, 证实、已确认 | — |
| MODERATE | supported, indicated, shown, 支持、表明、显示 | demonstrated, confirmed, 证实、已确认 |
| CAUTIOUS | suggested, limited evidence suggests, may, 提示、有限证据表明、可能 | supported, demonstrated, 支持、证实 |
| INSUFFICIENT | current evidence is insufficient to conclude, 当前证据无法得出结论 | 任何肯定性措辞 |

### 4.2 Quantitative Allowed Flag

| 条件 | quantitative_allowed |
|---|---|
| 至少 1 个 high-confidence fact 支撑该声明 | true |
| 仅有 medium/low-confidence facts | false（仅可定性描述） |
| conclusion_strength = INSUFFICIENT | false |
| conflict = CRITICAL | false |

### 4.3 Required Caveats

每个声明必须附带：
- 结论强度标签
- 证据质量信号
- 如有冲突或限制，必须说明

---

## 五、输出

```text
writer_conclusion_constraints (per claim):
  claim_id: str
  max_conclusion_strength: str        # STRONG / MODERATE / CAUTIOUS / INSUFFICIENT
  allowed_language_strength: str      # 同 max
  forbidden_phrases: [str]            # 禁止的措辞
  quantitative_allowed: bool
  required_caveats: [str]             # 必须附加的限制声明
  evidence_summary_for_writer: str    # Writer 可用的证据摘要
```

---

## 六、禁止

- ❌ Writer 使用超出 allowed_language_strength 的措辞
- ❌ 在 quantitative_allowed = false 时引用具体数值
- ❌ 在 conclusion_strength = INSUFFICIENT 时写肯定性声明
- ❌ 省略 required_caveats
- ❌ 让 LLM 自由选择 conclusion_strength——必须是确定性规则

---

*CCD 签发：2026-05-12*
