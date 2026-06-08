# BIGDP2026.6V_3 — Stage Gap Analysis

**Based on:** Latest DeerFlow CER 工作流阶段能力分析 (V3 update)
**Date:** 2026-06-08

---

## 12-Stage Assessment

| Stage | V2 后评分 | 专家审慎评分 | 差值 | 进入 V3? | 依赖 Patch A 资产 | 预期提升 |
|:---|:--:|:--:|:--:|:--:|:---|:--:|
| S1 产品身份确认 | 95 | 95 | 0 | ❌ | — | — |
| S2 声明分析与边界 | 85 | 85 | 0 | ❌ | — | — |
| S3 文献检索 | 85 | 85 | 0 | ❌ | B1 search audit | — |
| S4 文献筛选与评价 | 82 | 80 | −2 | ❌ | B2 screening | — |
| **S5 临床数据提取** | **65** | **60** | **−5** | ✅ U1 | B4 PMID trace, B5 denominator | 65→75 |
| **S6 endpoint/benchmark** | **80** | **78** | **−2** | ✅ U4 | C1 endpoint, C2 comparator | 80→85 |
| **S7 等效性评估** | **70** | **68** | **−2** | ✅ U3 | 等效性分析文件 | 70→80 |
| **S8 证据→声明映射** | **82** | **78** | **−4** | ✅ U2 | C3 claim-evidence | 82→88 |
| S9 Gap/PMCF | 88 | 85 | −3 | ❌ | — | — |
| **S10 BR/GSPR** | **78** | **72** | **−6** | ✅ U5 | B4/B5/C3 data | 78→85 |
| S11 专家推理整合 | 82 | 80 | −2 | ❌ | — | — |
| **S12 写入就绪与交付** | **97** | **92** | **−5** | ✅ U6 | D2/D3 Writer outputs | 97→95 |

---

## 重点阶段详解

### S5 — 临床数据提取（65/100）

**缺口：**
- 现有 clinical_fact_registry 主要靠正则提取 `X% (n/N)`, `mean ± SD`, `N=XXX`
- 不支持：HR/RR/OR/CI/p-value/median/IQR/Kaplan-Meier/subgroup/table figure/follow-up duration/AE severity
- denominator 和 population label 绑定仍弱

**V3 升级（U1）：**
- clinical_fact_registry_v2 with statistical fact parser, subgroup detector, table/figure extractor, source sentence anchor
- 验收：≥50 facts, ≥10 table-derived, ≥10 CI/statistical, ≥5 subgroup, 0 orphan numeric, denominator validator pass

**资产依赖：** B4 PMID trace (PARTIAL), B5 denominator labels (PARTIAL)

### S7 — 等效性评估（70/100）

**缺口：**
- EQV-01~03 已进入 Rulebook/YAML，但 runtime 强制执行不完整
- equivalent evidence 仍可能被误写成 direct evidence
- 三维比较检测不完整

**V3 升级（U3）：**
- equivalence_runtime_gate：technical/biological/clinical 三维比较 + differences impact analysis + data access check + no-equivalence path + equivalent evidence limitation propagation

**资产依赖：** 等效性分析文件（可从 Patch A 项目中提取）

### S8 — 证据→声明映射（82/100）

**缺口：**
- G43 消费 CER_REASONING_LEDGER 并验证 evidence_support_type
- 但主要验证链接存在，不验证语义支持
- irrelevant evidence linked to claim 不触发 FAIL

**V3 升级（U2）：**
- semantic_support_validator：endpoint_match + population_match + indication_match + device_match + directness + support_strength + limitation + contradiction
- 验收：irrelevant evidence→FAIL, weak→strong→FAIL, indirect as direct→FAIL

**资产依赖：** C3 claim-evidence support (PARTIAL)

### S10 — BR/GSPR（78/100）

**缺口：**
- G44/G45 已接入 G46，但 BR 账本可能空洞
- benefit-to-evidence、risk-to-mitigation 交叉验证不足
- Writer synthesis 可能由 LLM 生成，不够实质化

**V3 升级（U5）：**
- benefit_to_evidence_crosswalk + risk_to_mitigation_crosswalk + GSPR_clinical_clause_to_evidence_matrix + unresolved_uncertainty_register + BR conclusion strength validator

**资产依赖：** B4/B5/C3 data (PARTIAL)

### S12 — 写入交付（97/100）

**缺口：**
- G46 和 CER_INPUT_PACKAGE 包级约束很强
- 散文级自动审查缺失：conclusion overstatement / unsupported claim / no-source numeric / denominator misuse in prose / endpoint taxonomy contradiction in prose

**V3 升级（U6）：**
- post_write_CER_QA：conclusion strength overstatement detector + unsupported claim detector + no-source numeric detector + PMCF overclaim detector + SOTA prose consistency checker

**资产依赖：** D2 CER originals, D3 Writer outputs (PARTIAL)

---

## 不进入 V3 的阶段

| 阶段 | 原因 |
|:---|:---|
| S1–S4 | V2 已充分覆盖，评分 ≥80，无实质性缺口 |
| S9 PMCF | V2 PMCF 4-rule 逻辑强，剩余缺口是上游数据质量依赖 |
| S11 整合 | 整合层本身无独立缺口，质量取决于 S5–S10 输入 |

---

## 预期分数提升

| 维度 | 当前 | V3 目标 | 提升 |
|:---|:--:|:--:|:--:|
| S5 临床数据提取 | 65 | 75 | +10 |
| S6 endpoint/benchmark | 80 | 85 | +5 |
| S7 等效性 | 70 | 80 | +10 |
| S8 证据→声明 | 82 | 88 | +6 |
| S10 BR/GSPR | 78 | 85 | +7 |
| S12 写入交付 | 97 | 95 (质量) | — |
| **整体工程成熟度** | **~81** | **~88–90** | **+7–9** |
