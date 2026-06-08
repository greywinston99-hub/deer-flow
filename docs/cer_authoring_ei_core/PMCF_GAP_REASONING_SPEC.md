# PMCF GAP REASONING SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## ⚠️ 独立严重度

**PMCF 推理有独立的严重度 `pmcf_gap_severity`。** 不与 SOTA 或 BR 共享通用评分。

---

## 一、六种 PMCF Gap 类型

| Gap 类型 | 触发条件 | 判断逻辑 |
|---|---|---|
| **long_term_data** | 随访时长远小于预期植入物使用寿命 | max(follow_up) < expected_device_lifetime × 0.5 |
| **population_gap** | 样本不覆盖 target population 的亚组 | 如：成人数据无儿科 / 主要人群缺特定合并症 |
| **rare_event** | 样本量不足以检测预期罕见事件 | total_n < 1 / (expected_AE_rate × 0.1) |
| **comparator_gap** | 缺少对照数据 | 全部 evidence 为 single-arm |
| **real_world** | 仅有 RCT / controlled 数据，无真实世界数据 | source_type 不含 pms_pmcf / registry / psur |
| **design_evolution** | 设备设计变更后无对应临床数据 | device_version > 1 且无对应版本 clinical data |

---

## 二、Gap Severity 判定

| 等级 | 条件 |
|---|---|
| **critical** | 缺失安全关键端点（如无 AE 数据）；BR 结论 borderline 且缺失数据为关键因素；design_evolution 且变更涉及安全性 |
| **high** | 缺失有效性端点；样本量显著不足以检测预期 AE 率（total_n < threshold）；long_term_data 且设备为植入物 |
| **medium** | 缺失特定人群数据但主要人群已覆盖；随访偏短但不显著低于同类标准；comparator_gap 但单臂数据充分 |
| **low** | 缺失补充性数据但对主要结论影响小；real_world gap 但 RCT 数据充分 |

---

## 三、Gap 推理流程

```text
Step 1: 对每个 claim 检查 6 种 gap 的触发条件
  → triggered_gaps: [gap_type]

Step 2: 对每个 triggered gap 判定 severity
  → gap_severity: critical / high / medium / low

Step 3: 生成 PMCF objective
  → 基于 gap_type + affected_claims

Step 4: 建议 PMCF method
  → 基于 gap_type 的常用方法（不编造细节）

Step 5: 汇总 → pmcf_gap_register
```

---

## 四、PMCF Objective 生成

| Gap 类型 | PMCF Objective 模板 |
|---|---|
| long_term_data | 「通过 PMCF [study/registry] 收集 [设备] 的长期 [安全性/有效性] 数据，随访 ≥ [预期使用寿命]」 |
| population_gap | 「将临床数据收集扩展至 [缺失亚组]，以确认 [设备] 在该人群中的 [安全性/有效性]」 |
| rare_event | 「通过扩大样本量/上市后注册收集 [设备] 的罕见不良事件数据，目标 n ≥ [threshold]」 |
| comparator_gap | 「开展 [对照设计] 研究以提供 [设备] 的对照临床数据」 |
| real_world | 「通过 PMCF registry/survey 收集 [设备] 的真实世界使用数据」 |
| design_evolution | 「收集 [新版本] 的临床跟踪数据以确认设计变更后的 [安全性/有效性]」 |

**约束**：系统生成 objective 模板，不填充具体数字（如具体样本量、具体随访年限）——这些需人工确定。

---

## 五、输出

```text
pmcf_gap_register:
  per gap:
    gap_id: str
    gap_type: str                  # long_term_data / population_gap / rare_event / comparator_gap / real_world / design_evolution
    gap_severity: str              # critical / high / medium / low
    affected_claims: [str]         # CLAIM-###
    trigger_condition_detail: str  # 触发该 gap 的具体条件
    pmcf_objective: str            # 模板生成的 PMCF 目标
    pmcf_method_suggestion: str    # 建议的方法类型
    pmcf_timeline_note: str        # 时间框架备注（不填具体日期）
    human_review_triggered: bool   # gap_severity = critical → true
    human_review_tier: int|null
```

---

## 六、跨 Gap 聚合

同一 claim 可能触发多个 gap：

```text
示例: 随访 6 月 + 样本量 20 + 单臂
  → long_term_data (severity = high, if implantable)
  → rare_event (severity = high, if expected AE rate low)
  → comparator_gap (severity = medium)
  → real_world (severity = medium)
```

聚合规则：claim 的 overall_pmcf_priority = max(gap_severity) for that claim

---

## 七、禁止

| 禁止行为 | 原因 |
|---|---|
| 自动填充 PMCF 计划的具体细节（样本量、随访年限、研究中心数） | 这些需要人工临床判断 |
| 将 PMCF gap 视为设备缺陷 | Gap = 数据缺口，不是设备问题 |
| 忽略不触发 gap 的缺失数据 | 不触发的 gap 也应记录但不生成 objective |
| 在 gap_severity = low 时生成 urgent PMCF | 严重度与紧迫性不匹配 |
| 编造不存在的 PMCF method | 方法建议仅基于已知分类 |

---

*CCD 签发：2026-05-12*
