# CDE90 — Clinical Data Extraction 90+ Sprint

**Project:** CDE90 — Stage 5 Clinical Data Extraction专项升级
**Predecessor:** BIGDP2026.6V_4 (ACCEPTED, ~90/100 overall, Stage 5: 78)
**Controller:** DeerFlow CER System Controller
**Date:** 2026-06-08
**Status:** CDE90_PLAN_ACCEPTED_WITH_REFINEMENT — ready for Work Buddy asset preparation

---

## 1. 项目定位

BIGDP2026.6V_4 完成了法规策略路由、文献智能分类、CER 蓝图和 NB 可解释性。系统整体工程分约 90/100，615/615 tests pass。但阶段 5「临床数据提取」仍为 78，没有从 V4 提升。

本轮不是继续做策略层升级，不是继续补外围 Gate，不是增加 parser 数量。**核心判断：78→90+ 不能靠继续加几个 regex。必须从"格式识别 + 基础 eligibility"升级为"全文/表格/研究结构理解 + 统计验证 + 分母/子组解析 + gold-verified validation"。**

---

## 2. 为什么阶段 5 仍停在 78

- clinical_fact_registry 结构对简单格式有效，对复杂临床数据模型不足
- statistical parser 覆盖了常见格式，但 HR/RR/OR/CI/Kaplan-Meier/subgroup/incidence density 等仍弱
- table/figure 提取仍基本缺失
- denominator/subgroup/study arm 解析不完整
- E0 eligibility 存在但 data-use enforcement 不充分
- 无 source-verified gold validation set

---

## 3. 五个批次

| Batch | 内容 | 核心问题 |
|:---|:---|:---|
| M | Clinical Study Data Model V3 | 每个 fact 从出生就带上下文 |
| N | Table / Figure / Fulltext Extraction | 从表格和图表中提取数据 |
| O | Statistical Fact Parser V3 | 覆盖 CER/SOTA 真实统计表达 |
| P | Denominator / Subgroup / Arm Resolver | 分母/子组/研究臂不能混用 |
| Q | Clinical Fact Verification & Gold Dataset | 用 gold set 证明 90+ |

**执行顺序：** M→N→O→P→Q。M 定义数据模型 → N 和 O 按模型提取和解析 → P 在模型上做一致性验证 → Q 用 gold set 验证。

---

## 4. 与 V4/V5 的关系

| 能力 | 当前状态 | 本轮 |
|:---|:---|:---|
| clinical_fact_registry_v2 | 已有 | 升级为 v3 |
| E0 eligibility | 已有 | 继承 |
| statistical parsers | 已有 (proportion, mean, HR, RR, OR, CI) | 扩展到 KM, EFS, incidence, between-group等 |
| table extraction | 基本缺失 | 新增 born-digital PDF + DOCX |
| denominator resolver | 部分 | 升级为 arm + subgroup + analysis set |
| gold validation | 无 | 新增 ≥150 source-verified facts |

---

## 5. 90+ 评分模型

| 能力 | 分值 | 封顶 |
|:---|---:|:---|
| Clinical fact registry v3 schema | 10 | — |
| Source eligibility + source anchor | 10 | 无 source anchors → max 80 |
| Statistical parser breadth | 15 | — |
| Table / figure extraction | 15 | 无 table extraction → max 84 |
| Denominator / subgroup / arm resolver | 15 | 无 denominator resolver → max 85 |
| Endpoint / population binding | 10 | — |
| AE severity / follow-up extraction | 10 | — |
| Data-use eligibility enforcement | 10 | — |
| Gold validation / real project validation | 15 | 无 gold set → max 86 |
| Regression stability | 10 | — |

**总分 110，折算 100。** 无 gold/source-verified validation → 阶段 5 评分不得超过 86。
