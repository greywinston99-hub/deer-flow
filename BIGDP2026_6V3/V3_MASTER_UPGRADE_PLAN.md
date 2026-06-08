# BIGDP2026.6V_3 — Master Upgrade Plan

**Project:** V3 — DeerFlow CER Expert Reliability Hardening
**Predecessor:** BIGDP2026.6V_2 (ACCEPTED, ~81/100)
**Controller:** DeerFlow CER System Controller
**Date:** 2026-06-08
**Status:** PLANNING

---

## 1. V3 定位

V3 是在 BIGDP2026.6V_2 基础上的**专家可靠性硬化升级**，不是重新设计，不是继续补外围 Gate，不是追求更多文档。

BIGDP2026.6V_2 完成了：
- 证据完整性基础设施（检索审计、筛选规则、全文策略、PMID 溯源、分母验证）
- 专家语义分类器（endpoint taxonomy、comparator benchmark completeness）
- SOTA accounting 和跨章节一致性
- Writer pre-write 包级约束
- 15–20 项目资产提取（18 项目实际完成，Tier 1 PASS，Tier 2 PARTIAL）

V2 将工程成熟度从 BIGDP2026.6 的 ~60 提升到 ~81/100。但最新阶段评估显示，**5 个关键阶段仍有实质性缺口**，这些缺口直接影响提交级 CER 的法规可靠性。

V3 不做的事：
- 不重新做资产提取（依赖 Patch A 已有资产）
- 不继续补外围 Gate（G42/G43/G46 已硬化）
- 不扩大 Review v5 / frontend 范围
- 不追求 100/100

V3 要做的事：
- 补临床数据提取的精度和广度
- 补 claim-evidence 语义验证
- 补等效性 runtime 强制执行
- 补 endpoint/benchmark domain 知识库
- 补 BR/GSPR 实质交叉验证
- 补 Writer 散文级 QA

---

## 2. 当前状态：最新阶段评估摘要

| 阶段 | V2 后评分 | 法规专家审慎评分 | 主要缺口 |
|:---|:--:|:--:|:---|
| S1 产品身份 | 95 | 95 | 基本完善 |
| S2 声明分析 | 85 | 85 | 边界判断仍需专家 |
| S3 文献检索 | 85 | 85 | 审计机制已有，recall 无 gold 验证 |
| S4 文献筛选 | 82 | 80 | 筛选规则已有，边界案例未覆盖 |
| **S5 临床数据提取** | **65** | **60** | 正则提取覆盖有限；table/figure/HR/RR/subgroup 仍弱 |
| S6 endpoint/benchmark | 80 | 78 | 分类器有但 domain template 少 |
| **S7 等效性评估** | **70** | **68** | EQV 规则在 Rulebook 但 runtime 不完整 |
| **S8 证据→声明** | **82** | **78** | G43 验证链接存在，不验证语义支持 |
| S9 PMCF | 88 | 85 | 规则强，但依赖上游数据质量 |
| **S10 BR/GSPR** | **78** | **72** | 账本可能空洞，交叉验证不足 |
| S11 专家推理 | 82 | 80 | 整合层，依赖上游 |
| **S12 写入交付** | **97** | **92** | 包级约束强，散文 QA 缺失 |

**整体工程成熟度：~81/100。法规交付可靠性：~78/100。**

---

## 3. 为什么 V3 不继续补外围 Gate

BIGDP2026.6V_2 已将 G42（证据充分性）、G43（claim-evidence link）、G46（Writer 释放）硬化到可靠水平。继续增加 gate 的边际收益递减。

当前系统的瓶颈不在 gate 数量，而在 gate 消费的数据质量：
- G43 验证"claim 有 evidence_id"，但不验证"evidence 语义上支持 claim"——这是 S8 评分 82 但专家评分 78 的原因
- BR 账本"存在"，但内容可能空洞——这是 S10 评分 78 但专家评分 72 的原因
- Writer 包级约束强，但散文级 overstatement 无法检测——这是 S12 评分 97 但专家评分 92 的原因

V3 的策略：**不做新 gate，做内容质量硬化。**

---

## 4. 六大升级方向

| # | 方向 | 目标阶段 | 当前评分 → 目标评分 |
|:--:|:---|:---|:--:|
| U1 | Clinical Fact Extraction V2 | S5, S6, S10 | 65 → 75 |
| U2 | Semantic Claim-Evidence Validator | S8, G43, G46 | 82 → 88 |
| U3 | Equivalence Runtime Gate | S7, S8 | 70 → 80 |
| U4 | Endpoint / Benchmark Domain Library | S6, S10, S12 | 80 → 85 |
| U5 | BR/GSPR Substantive Crosswalk | S10, S11, S12 | 78 → 85 |
| U6 | Post-Write CER Prose QA | S12, Final | 97 → 95 (质量提升) |

**预期整体工程成熟度：81 → 88–90。法规交付可靠性：78 → 85+。**

---

## 5. 四批次执行路线（严格顺序 E→F→G→H）

**执行约束：** 不可并行。E 是数据地基 → F 是专家判断核心 → G 是综合论证 → H 是交付安全网。不能先做 H（Writer QA 依赖前面所有 ledger 和 validator）。

### Batch E — Clinical Fact Extraction V2（U1）

覆盖 S5（临床数据提取）+ 部分 S6/S10。核心：升级 clinical_fact_registry 以支持 table/figure/statistical fact/subgroup/follow-up/severity 提取。输出：`V3_BATCH_E_*.md`。

### Batch F — Semantic Support + Equivalence（U2 + U3）

覆盖 S7（等效性）+ S8（证据→声明）。核心：语义 claim-evidence validator + 等效性 runtime gate。输出：`V3_BATCH_F_*.md`。

### Batch G — Endpoint Benchmark + BR/GSPR（U4 + U5）

覆盖 S6（endpoint/benchmark）+ S10（BR/GSPR）。核心：domain template library + BR/GSPR 实质交叉验证。输出：`V3_BATCH_G_*.md`。

### Batch H — Writer Prose QA + E2E Validation（U6）

覆盖 S12（写入交付）+ Final。核心：post-write CER prose QA + holdout 验证。输出：`V3_BATCH_H_*.md`。

---

## 6. 与 BIGDP2026.6V_2 的关系

| 维度 | V2 产出 | V3 沿用/升级 |
|:---|:---|:---|
| 检索审计 | RETRIEVAL_AUDIT_TRAIL | 沿用 |
| 筛选规则 | SCREENING_RULE_ENGINE | 沿用 |
| 全文策略 | FULLTEXT_STATUS | 沿用 |
| PMID 溯源 | DATA_TRACEABILITY_VALIDATOR | 沿用 |
| 分母验证 | DENOMINATOR_VALIDATOR | 沿用 |
| 数据提取 | clinical_fact_registry (基础版) | **升级为 V2**（U1） |
| Endpoint 分类 | ENDPOINT_SEMANTIC_CLASSIFIER | 沿用，增加 domain template（U4） |
| Comparator | COMPARATOR_BENCHMARK_CHECKER | 沿用 |
| SOTA | SOTA_ACCOUNTING_CONSISTENCY_CHECKER | 沿用 |
| Claim-Evidence | G43（链接存在验证） | **升级为语义验证**（U2） |
| 等效性 | Rulebook EQV-01~03 | **升级为 runtime gate**（U3） |
| BR/GSPR | G44/G45（接入 G46） | **升级为实质交叉验证**（U5） |
| Writer | 包级 pre-write 约束 | **新增散文级 post-write QA**（U6） |
| Gate 硬化 | G42/G43/G46 | 沿用，内容填充升级 |

---

## 7. 资产依赖策略

V3 依赖 Patch A 提取的 18 项目资产。当前资产状态：Tier 1 PASS（结构），Tier 2 PARTIAL（内容 TO_BE_EXTRACTED）。

| 升级 | 需要资产 | 资产缺失时降级 |
|:---|:---|:---|
| U1 数据提取 | B4 PMID trace, B5 denominator | heuristic rules + synthetic fixtures |
| U2 语义验证 | C3 claim-evidence support | derived validation from accepted CER |
| U3 等效性 gate | 等效性分析文件 | Rulebook rules（已有） |
| U4 Domain 库 | C1 endpoint labels, C2 comparator | endpoint classifier（已有） + domain inference |
| U5 BR crosswalk | B4/B5/C3 data | derived from existing ledgers |
| U6 Writer QA | D2 CER originals, D3 Writer outputs | historical CER text (Level 2) |

---

## 8. 法规专家级新增层（6 项）

V3 从"工程升级"推向"法规判断闭环"的 6 个关键新增：

| # | 新增层 | 所属 Batch | 法规问题 |
|:--:|:---|:--:|:---|
| 1 | Clinical Data Eligibility Layer (E0) | E | 这篇文献能不能作为数据来源？ |
| 2 | Atomic Claim Decomposition (F0) | F | 复合 claim 拆开才能做语义验证 |
| 3 | Equivalence Route Decision (F1) | F | 是否允许主张等效性？ |
| 4 | Dual-Axis Domain Template (G0) | G | domain × claim_type 双轴 |
| 5 | Unfavourable Evidence Register | G | 不利证据怎么处理？ |
| 6 | Regulatory Language Tone Checker | H | 语气是否与 evidence strength 匹配？ |

**法规验收标准：** `V3_REGULATORY_ENGINEER_REVIEW_GATE.md` — 每 Batch 完成后 Controller 逐条回答 7–10 个法规专家级审查问题。

## 9. 不以 100 为目标的原因

- 12 个 Core Validation Assets 中 7 个仍为 NOT_FOUND（manual search gold、screening gold、PMID verification、denominator gold、comparator gold、SOTA gold、claim-evidence labels）
- Path B 确认，无法冲击 FULLY_CLOSED
- 关键 gold labels（endpoint expert labels、denominator expert labels）依赖 Domain Expert，不在本次范围
- 88–90 是在当前资产约束下的务实上限

---

## 9. 停止条件

- 任何 Batch 连续 3 次修复循环无进展 → STOP
- Tier 2 资产未从 PARTIAL→READY 但 Batch 强行声称 FULLY_CLOSED → STOP
- 代码改动触发 baseline 退化 → STOP，修复回归
- 需要架构重写（>300 行触及 graph 核心路由）→ STOP
- Writer output 完全不可得（无 Level 1/2）→ U6 降级为 SYNTHETIC_ONLY
