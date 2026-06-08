# SCORING CALIBRATION AND THRESHOLD POLICY

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## ⚠️ 关键约束

**Evidence scoring 是内部推理辅助，不是外部监管认证。** 评分不得被声称或理解为监管级别的证据质量认证。阈值和权重是不可由 LLM 调整的确定性计算。

⚠️ **所有权重和阈值均为确定性启发式基线（deterministic heuristic baselines）。** 用于内部推理辅助。在通过 calibration 项目数据校准之前，不得视为稳定。**Calibration before pilot is MANDATORY.**

---

## 一、评分状态（score_calibration_status）

| 状态 | 含义 | 设定时机 |
|---|---|---|
| **provisional** | 初始阈值，基于理论映射，未校准 | 系统初次运行时自动设定 |
| **internally_calibrated** | 经过 calibration 项目验证，阈值已调整 | 校准完成后由 CCD 确认 |
| **human_reviewed** | 人工确认评分合理 | Tier 2/3 human review 中设定 |

---

## 二、初始阈值设定依据

### 2.1 Quality Tier 阈值

| Tier | Score Range | 理论依据 |
|---|---|---|
| excellent | 85-100 | 对应 MEDDEV 2.7/1 的 "high quality clinical investigation" |
| good | 70-84 | 对应 "adequate clinical investigation" |
| acceptable | 55-69 | 对应 "clinical data from other sources sufficient" |
| marginal | 40-54 | 对应 "limited clinical data" |
| insufficient | 0-39 | 对应 "insufficient clinical evidence" |

### 2.2 因子权重理论依据

| 因子 | 权重 | 依据 |
|---|---|---|
| Study Design (F1) | 25% | MEDDEV 2.7/1 Section 6.4: study design hierarchy |
| Device Relationship (F2) | 25% | MDR Annex X 1.1(a): subject device data primacy |
| Data Quality (F3) | 20% | MEDDEV 2.7/1 Section 6.3: data quality requirements |
| Fact Confidence (F4) | 15% | V3 toolchain: data extraction reliability |
| Conflict Status (F5) | 10% | MEDDEV 2.7/1 Section 6.6: conflicting evidence handling |
| Regulatory Admissibility (F6) | 5% | MDR Annex X: formal admissibility check |

F1 + F2 = 50%。这两项是监管审查的核心关注点——study design 和 device relationship 决定了证据在监管框架中的基本地位。

### 2.3 因子评分的理论映射

| 评分 | 含义 | 来源 |
|---|---|---|
| 4 | Optimal / Ideal | 满足 gold standard |
| 3 | Good / Adequate | 满足基本要求 |
| 2 | Marginal / Limited | 部分满足，有显著限制 |
| 1 | Poor / Minimal | 严重不足 |
| 0 | Absent / Cannot evaluate | 无数据或不可评估 |

---

## 三、校准方法

### 3.1 Calibration 数据源

| 数据源 | 项目 | 样本量 |
|---|---|---|
| CAL-001 | 第一个 calibration 项目 | ~10-15 evidence items |
| CAL-002 | 第二个 calibration 项目 | ~10-15 evidence items |
| CAL-003 | 第三个 calibration 项目 | ~10-15 evidence items |
| 合计 | — | ~30-45 evidence items |

### 3.2 校准流程

```text
Step 1: 系统评分
  对 calibration 项目的每条 evidence 运行 evidence_scoring_model
  → system_scores

Step 2: 人工独立评分
  Human reviewer 对同批 evidence 独立评分（同 0-100 scale）
  → human_scores

Step 3: 偏差分析
  计算 |system_score - human_score| per evidence
  计算 aggregate: mean_absolute_error, Pearson correlation, tier_match_rate

Step 4: 偏差 >20 分 → 阈值调整
  如果 MAE > 10 或 tier_match_rate < 80%:
    分析偏差方向（系统偏高还是偏低）
    调整 quality tier 阈值或因子权重
    重新评分 → 重新比较

Step 5: 校准完成
  score_calibration_status → internally_calibrated
  记录校准过程到 DECISION_LOG
```

### 3.3 校准验收标准

| 指标 | 门槛 |
|---|---|
| Mean Absolute Error (MAE) | ≤ 10 分（0-100 scale） |
| Tier Match Rate | ≥ 80%（系统与人工 tier 一致） |
| Pearson Correlation | ≥ 0.7 |

不满足 → 阈值需调整并重新校准。

---

## 四、阈值变更规则

1. **阈值变更需 CCD 审批**，记录在 DECISION_LOG
2. **变更必须基于校准数据**，不可基于直觉或单一案例
3. **变更不可由 LLM 建议或执行**——必须是确定性规则调整
4. **质量 tier 阈值不可偏离 MEDDEV 理论映射 >10 分**（如 excellent 下限不可 <75）
5. **因子权重变动不可 >10 个百分点**（如 F1 不可从 25% 变为 >35% 或 <15%）
6. **校准仅在 pilot 恢复前做一次**，pilot 中系统不自行校准

---

## 五、禁止

- ❌ 将评分视为绝对质量指标（它是 ordinal 参考，不是 cardinal 精度）
- ❌ 用评分替代 G42 的 claim-specific evidence sufficiency 判断
- ❌ 对不同 regulatory context 使用同一套阈值（如 Class I 和 Class III 应不同，但初始版本统一使用最严格标准）
- ❌ 在 pilot 中自行调整阈值
- ❌ 将 score_calibration_status = provisional 的评分用于自动阻塞决策

---

## 六、初始部署后的预期路径

```text
provisional (初始)
  → 3 calibration 项目人工评分对比
  → internally_calibrated（如达标）
  → 后续 high-impact human review 中可能获得 human_reviewed
```

---

*CCD 签发：2026-05-12*
