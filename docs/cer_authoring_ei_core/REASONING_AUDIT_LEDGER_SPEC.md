# REASONING AUDIT LEDGER SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## 一、审计要求

**每条结论必须可追溯到源头 fact。** 推理审计台账记录从 fact → conclusion 的每一步推理，确保：
- 可追溯性：每个结论可追溯到输入数据
- 可复现性：每条规则的应用可被验证
- 可审计性：假设和替代解释显式记录

---

## 二、Audit Entry 结构

```text
audit_entry:
  audit_entry_id: str              # AUD-###
  timestamp: str                   # ISO 8601
  reasoning_step: str              # evidence_scoring / claim_reasoning / sota_synthesis / br_reasoning / pmcf_gap / crosswalk / conclusion_strength
  component: str                   # 具体组件名（如 evidence_scoring_model, device_claim_reasoning）
  rule_applied: str                # rule_id（如 ESM-F1-01, DCR-SUPPORT-STRONG）
  rule_version: str                # 规则版本号
  input_artifacts: [str]           # FACT-###, EVID-###, CLAIM-###, etc.
  input_summary: dict              # 关键输入值的摘要
  intermediate_result: dict        # 推理中间结果
  output_artifacts: [str]          # 输出 artifact IDs
  output_summary: dict             # 关键输出值的摘要
  confidence: str                  # high / medium / low（此步推理的置信度）
  assumptions: [str]               # 显式假设
  alternative_interpretations: [str] # 替代解释
  rule_trigger_condition: str      # 触发此规则的条件
  deterministic: bool              # 此步是否为确定性计算
```

---

## 三、每个 Reasoning Step 的审计条目

### 3.1 Evidence Scoring

```text
reasoning_step: "evidence_scoring"
component: "evidence_scoring_model"
关键记录:
  - 各因子评分（F1-F6）及来源
  - 综合计算公式和中间值
  - quality_tier 映射
  - score_calibration_status
```

### 3.2 Claim Reasoning

```text
reasoning_step: "claim_reasoning"
component: "device_claim_reasoning"
关键记录:
  - claim_type → required_source_profile
  - matching_evidence 列表
  - missing_evidence_gaps
  - claim_support_level 判定理由
```

### 3.3 SOTA Synthesis

```text
reasoning_step: "sota_synthesis"
component: "sota_benchmark_synthesis"
关键记录:
  - endpoint_cluster 分组
  - 异常值排除理由
  - synthesis_method 选择理由
  - benchmark 计算（如适用）
  - benchmark_confidence 判定理由
```

### 3.4 BR Reasoning

```text
reasoning_step: "br_reasoning"
component: "benefit_risk_reasoning"
关键记录:
  - per-claim benefit/risk 识别
  - BR comparison 逻辑
  - uncertainty discount 应用
  - br_acceptability_confidence 判定理由
```

### 3.5 PMCF Gap

```text
reasoning_step: "pmcf_gap"
component: "pmcf_gap_reasoning"
关键记录:
  - 每个 gap 的触发条件检查
  - gap_severity 判定理由
  - pmcf_objective 生成逻辑
```

### 3.6 Crosswalk

```text
reasoning_step: "crosswalk"
component: "cer_rmf_crosswalk"
关键记录:
  - 匹配逻辑
  - mismatch 标记理由
  - link_rationale
```

### 3.7 Conclusion Strength

```text
reasoning_step: "conclusion_strength"
component: "claim_conclusion_strength"
关键记录:
  - 各输入源的 strength 信号
  - min() 计算过程
  - 降级理由（conflict, BR, bridging）
```

---

## 四、输出

```text
reasoning_audit_ledger:
  entries: [audit_entry]
  total_steps: int
  high_confidence_steps: int
  medium_confidence_steps: int
  low_confidence_steps: int
  assumptions_count: int
  alternative_interpretations_count: int
```

输出文件：`reasoning_audit_ledger.json`

---

## 五、审计检查

### 5.1 自动检查

| 检查项 | 条件 |
|---|---|
| 每条结论有 trace 到 fact | conclusion → audit_entry → input_artifacts 包含 FACT-### |
| 每条规则有版本号 | rule_version 不为空 |
| 确定性步骤的 confidence 为 high | deterministic=true → confidence=high |
| 非确定性步骤标注了假设 | confidence < high → assumptions 不为空 |

### 5.2 人工检查

| 检查项 | 何时 |
|---|---|
| rule 应用的逻辑正确性 | Tier 2/3 human review 中抽查 |
| alternative_interpretations 的合理性 | 同等 |
| assumptions 的合理性 | 同等 |

---

## 六、禁止

- ❌ 确定性计算不记录审计条目
- ❌ 假设不显式标注
- ❌ 替代解释不记录
- ❌ 推理步骤跳过（即使 intermediate_result 为空也须记录）
- ❌ 规则应用无 rule_id

---

*CCD 签发：2026-05-12*
