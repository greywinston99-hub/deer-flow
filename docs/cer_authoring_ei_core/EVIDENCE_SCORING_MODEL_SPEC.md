# EVIDENCE SCORING MODEL SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## ⚠️ 关键约束

**Evidence scoring 是内部推理辅助工具，不是外部监管认证。** 评分不得被声称或理解为监管级别的证据质量认证。评分为下游模块（Claim Reasoning、SOTA、BR、PMCF）提供统一的证据质量信号，但每个下游模块保留独立的置信度评估。

⚠️ **所有权重和阈值均为确定性启发式基线（deterministic heuristic baselines）。** 用于内部推理辅助。在通过 calibration 项目数据校准之前，不得视为稳定。

---

## 一、多因子评分模型

六因子加权评分。每个因子评分 0-4，加权后映射到 0-100。

### 1.1 因子权重

| # | 因子 | 权重 | 说明 |
|---|---|---|---|
| F1 | Study Design | 25% | RCT > 前瞻性观察 > 回顾性 > 病例系列 > 个案 |
| F2 | Device Relationship | 25% | subject > equivalent > similar > previous_gen > competitor > unrelated |
| F3 | Data Quality | 20% | 样本量、随访时长、统计报告完整性 |
| F4 | Fact Confidence | 15% | 来自 V3 的 extraction_confidence |
| F5 | Conflict Status | 10% | 来自 V3 的 evidence_conflict_report |
| F6 | Regulatory Admissibility | 5% | 来自 Admissibility Spec |

### 1.2 F1: Study Design 评分

| 研究设计 | 分数 |
|---|---|
| RCT（随机对照试验） | 4 |
| Prospective controlled study | 3 |
| Prospective single-arm / Observational cohort | 3 |
| Retrospective controlled study | 2 |
| Retrospective single-arm / Case series (≥30) | 2 |
| Case series (<30) | 1 |
| Case report / Expert opinion | 0 |
| Not reported / Cannot determine | 0 |

### 1.3 F2: Device Relationship 评分

| 关系 | 分数 | 条件 |
|---|---|---|
| subject_device | 4 | 直接研究 subject device |
| previous_generation | 3 | 有改进对比数据 |
| equivalent_device | 3 | equivalence rationale 成立 |
| similar_device | 2 | 可比但不等效 |
| competitor_device | 1 | 仅 SOTA 背景 |
| unrelated_device | 0 | 不可比 |

### 1.4 F3: Data Quality 评分

| 维度 | 条件 |
|---|---|
| 样本量 (0-2) | n≥100 → 2; n≥30 → 1; n<30 → 0 |
| 随访 (0-1) | 随访明确且充分 → 1; 缺失或不足 → 0 |
| 统计完整性 (0-1) | CI + p-value 齐全 → 1; 缺失 → 0 |

F3 = sum(样本量, 随访, 统计完整性)

### 1.5 F4: Fact Confidence 评分

映射 V3 extraction_confidence → 评分：

| extraction_confidence | 分数 |
|---|---|
| high | 4 |
| medium | 3 |
| low | 1 |
| OCR_uncertain | 0 |

### 1.6 F5: Conflict Status 评分

| 冲突状态 | 分数 |
|---|---|
| 无冲突 | 4 |
| MEDIUM 冲突（非关键端点） | 2 |
| HIGH 冲突 | 1 |
| CRITICAL 冲突 | 0 |

### 1.7 F6: Regulatory Admissibility 评分

| admissibility | 分数 |
|---|---|
| ADMISSIBLE | 4 |
| CONDITIONAL（满足条件） | 3 |
| CONDITIONAL（条件未验证） | 1 |
| CONTEXT_ONLY | 1 |
| NOT_ADMISSIBLE | 0 |

---

## 二、综合评分计算

```text
raw_score = (F1 × 0.25 + F2 × 0.25 + F3 × 0.20 + F4 × 0.15 + F5 × 0.10 + F6 × 0.05) × 25

evidence_strength_score = max(0, min(100, raw_score))
```

### 2.1 Quality Tier 映射

| Score Range | Quality Tier | 含义 |
|---|---|---|
| 85-100 | excellent | 高质量 subject device 证据，可独立支撑声明 |
| 70-84 | good | 良好证据，可支撑声明 |
| 55-69 | acceptable | 可接受，可与其他证据共同支撑 |
| 40-54 | marginal | 边缘质量，仅可为辅助证据 |
| 0-39 | insufficient | 质量不足，不可用于支撑声明 |

---

## 三、评分输出

```text
每个 evidence 的评分输出:
  evidence_id: str
  evidence_strength_score: float        # 0-100
  evidence_quality_tier: str            # excellent / good / acceptable / marginal / insufficient
  score_calibration_status: str         # provisional / internally_calibrated / human_reviewed
  calibration_required: bool            # true — must be calibrated before treated as stable
  score_confidence: str                 # high / medium / low（评分本身的可靠性）
  score_limitations: [str]              # 评分限制说明
  factor_scores: {F1: x, F2: x, ...}   # 各因子得分（可审计）
```

---

## 四、评分置信度（Meta-Confidence）

评分本身的可靠性受输入数据质量影响：

| 条件 | score_confidence |
|---|---|
| F1-F6 全部有明确值 | high |
| F3（数据质量）或 F5（冲突）有不确定性 | medium |
| F1（研究设计）或 F2（设备关系）不确定 | low |

---

## 五、阈值校准

评分阈值和校准策略见 `SCORING_CALIBRATION_AND_THRESHOLD_POLICY.md`。

要点：
- 初始阈值基于 MEDDEV 2.7/1 Rev.4 + Oxford LoE 理论映射
- 权重基于 regulatory relevance（F1 + F2 = 50%，反映监管审查核心关注）
- 阈值不可由 LLM 调整
- 校准仅通过 calibration 项目数据 + 人工评分对比

---

## 六、禁止

- ❌ 将 `evidence_strength_score` 声称或理解为监管级认证
- ❌ 用评分替代 G42 的 claim-specific evidence sufficiency 判断
- ❌ 在不同 regulatory context 间比较评分
- ❌ 基于单一因子（如 study design 单独）做结论
- ❌ 在评分 confidence = low 时基于评分做自动决策

---

*CCD 签发：2026-05-12*
