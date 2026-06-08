# BENEFIT-RISK REASONING SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## ⚠️ 独立置信度

**BR 推理有独立的置信度 `br_acceptability_confidence`。** 不与 SOTA 或 PMCF 共享通用评分。

---

## 一、基础框架

基于 ISO 14971:2019 + MDR Annex I 的结构化受益-风险框架。

### 输入
- claim_support_matrix（来自 Device Claim Reasoning）
- clinical_evidence_fact_table 中的安全性和有效性端点
- evidence_registry 中与受益/风险相关的 evidence
- risk_management_file 中的风险控制措施（如可用）

---

## 二、推理步骤

```text
Step 1: Benefit Identification（受益识别）
  每个 performance / safety claim:
    benefit_type: clinical_outcome / technical_performance / safety_profile
    benefit_description: 人类可读描述
    benefit_quantified: 量化值（如成功率 87.3%）或 qualitative
    benefit_confidence: high / medium / low（基于 evidence_quality_tier）

Step 2: Risk Identification（风险识别）
  每个 safety endpoint / adverse event:
    risk_type: known_complication / potential_adverse_event / device_failure
    risk_description: 人类可读描述
    risk_quantified: 量化值（如 SAE rate 2.1%）或 qualitative
    risk_severity: critical / serious / minor
    risk_confidence: high / medium / low

Step 3: Benefit-Risk Comparison（受益-风险权衡）
  受益是否大于风险？
    benefit > risk (clear margin) → favorable
    benefit ≈ risk (marginal) → balanced
    benefit < risk (unfavorable) → unfavorable

Step 4: Uncertainty Discount（不确定性折价）
  如 claim_support_level = WEAK or INSUFFICIENT:
    benefit_quantified 向下折价（如标注不确定性范围）
    可能降低 BR 判断一级

Step 5: Overall BR Conclusion
  favorable / acceptable / borderline / unfavorable
  附带 br_acceptability_confidence
```

---

## 三、Br_Acceptability_Confidence 判定

| 等级 | 条件 |
|---|---|
| **high** | Benefit 和 risk 均有 ≥2 subject device high-quality 证据，方向一致，无 CRITICAL 冲突 |
| **medium** | ≥1 subject device acceptable+ 证据，受益方向清晰，风险数据可接受 |
| **low** | 仅 indirect/equivalence 证据，或 benefit 或 risk 一侧证据薄弱 |
| **insufficient_evidence** | 缺少 benefit 或 risk 的关键端点数据 |

---

## 四、BR 结论

### 4.1 Favorable（有利）

受益明显大于风险，且 br_acceptability_confidence ≥ medium。

输出措辞约束：
- 可声称「受益大于风险」
- 必须同时引用受益和风险数据
- 必须注明 br_acceptability_confidence

### 4.2 Acceptable（可接受）

受益大于风险但 margin 较小，或 br_acceptability_confidence = medium，或有 HIGH 冲突。

输出措辞约束：
- 可声称「受益大于风险，在 [条件] 下可接受」
- 必须详细列出风险
- 可能需要限制适应症

### 4.3 Borderline（临界）

受益 ≈ 风险，或 benefit 数据不充分但有合理的风险控制，或 br_acceptability_confidence = low。

输出措辞约束：
- 不可声称受益明显大于风险
- 需要额外论证或限制适应症
- 触发 Tier 2 human review

### 4.4 Unfavorable（不利）

受益 < 风险，或 br_acceptability_confidence = insufficient_evidence。

输出措辞约束：
- 必须明确声明「当前证据不支持受益大于风险的结论」
- 触发 Tier 3 human review（如 insufficient_evidence）
- 不可声称受益大于风险

---

## 五、输出

```text
benefit_risk_conclusion:
  overall_judgment: str            # favorable / acceptable / borderline / unfavorable
  br_acceptability_confidence: str # high / medium / low / insufficient_evidence
  per_claim_benefit:
    - claim_id: str
      benefit_type: str
      benefit_description: str
      benefit_quantified: str      # 量化值 + 单位，或 "qualitative"
      benefit_confidence: str
      supporting_evidence_ids: [str]
  per_claim_risk:
    - claim_id: str
      risk_type: str
      risk_description: str
      risk_quantified: str
      risk_severity: str
      risk_confidence: str
      supporting_evidence_ids: [str]
  uncertainty_discounts: [str]     # 不确定性折价说明
  risk_controls_considered: [str]  # 已考虑的风险控制措施
  human_review_triggered: bool
  human_review_tier: int|null
```

---

## 六、禁止

| 禁止行为 | 原因 |
|---|---|
| 在证据不充分时声称「受益大于风险」 | 未满足基本证据要求 |
| 仅引用受益数据而不提及风险数据 | 不完整的 BR 分析 |
| 对受益和风险使用不同的证据标准 | 方法论不一致 |
| br_acceptability_confidence = insufficient_evidence 时输出 favorable/acceptable | 结论超过证据支撑 |
| 在 BR borderline 时声称 clearly positive | 误导性结论 |
| 忽略 risk_management_file 中的已知风险 | 不完整的风险考量 |

---

*CCD 签发：2026-05-12*
