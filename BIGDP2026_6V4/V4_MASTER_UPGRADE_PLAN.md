# BIGDP2026.6V_4 — Master Upgrade Plan

**Project:** V4 — Regulatory Strategy & Literature Intelligence
**Predecessor:** BIGDP2026.6V_3 (ACCEPTED, ~87/100 engineering maturity, 598/598 tests)
**Controller:** DeerFlow CER System Controller
**Date:** 2026-06-08
**Status:** PLANNING

---

## 1. V4 定位

V3 完成了 6 大能力的工程吸收：Clinical Fact Extraction V2、Semantic Claim-Evidence Validator、Equivalence Runtime Gate、Endpoint Domain Library、BR/GSPR Substantive Crosswalk、Post-Write CER Prose QA。系统从流程自动化升级为专家推理执行系统。

但从顶级医疗器械法规工程师视角看，系统仍缺**更上游的法规策略判断**和**深层文献理解能力**。当前系统能"提取数据、验证语义、检查等效性、审计 BR/GSPR、约束 Writer"，但不能"根据产品情形选择正确的 CER 策略、判断证据充分性水平、理解每篇文献的角色和适用边界"。

V4 的核心目标：**让系统能像顶级法规工程师一样，根据 MDR、MEDDEV 2.7/1 Rev.4、MDCG 2020-5/6 和具体产品情形，选择正确的 CER 路径、证据重点、文献角色、等效性策略、PMCF 策略、BR/GSPR 论证重点和 Writer 表达边界。**

V4 不做的事：
- 不增加外围 Gate
- 不做普通 parser 增强
- 不扩大 Review v5 / frontend
- 不以无人工复核提交为目标

---

## 2. 与 V3 的关系

| 维度 | V3 产出 | V4 定位 |
|:---|:---|:---|
| 证据质量 | E0 eligibility, clinical_fact_registry_v2 | 升级为 evidence burden & sufficiency engine |
| 语义验证 | U2 semantic validator | 升级为 article role classifier + literature intelligence |
| 等效性 | U3 equivalence runtime gate | 升级为 strategy router 中的一个 route 分支 |
| Writer 约束 | U6 post-write QA | 升级为 route-specific CER blueprint + NB explainability |

V4 不是替代 V3，而是**在 V3 的基础上增加上游策略层**。V3 管"这个数据对不对"，V4 管"这个策略对不对"。

---

## 3. 当前状态：87/100 的真实含义

- 工程吸收：U1–U6 全部实现，598/598 tests pass
- 专家验证：0 FULLY_CLOSED，主要 HEURISTIC/DERIVED
- 法规交付可靠性：约 82/100（结构正确，策略判断仍缺）

V4 目标：从 87 工程成熟度推进到 90+ submission reliability，使系统能回答"这条 CER 应该走什么路径、证据是否足够、每篇文献起什么角色、NB 如何理解这些判断"。

---

## 4. V4 五个 P0 能力

| # | 能力 | 核心问题 |
|:--:|:---|:---|
| P0-1 | Clinical Evaluation Strategy Router | 本产品走哪条 CER 路径？ |
| P0-2 | Evidence Burden & Sufficiency Engine | 需要多强的证据？当前够不够？ |
| P0-3 | Literature Intelligence V2 | 每篇文献在 CER 中起什么角色？ |
| P0-4 | Strategy-Specific CER Blueprint | 不同路径下 CER 怎么写？ |
| P0-5 | NB Explainability Packet | 如何向 NB 解释每个判断？ |

---

## 5. 核心法规原则

V4 必须内化以下原则：

1. MDR Article 61 / Annex XIV 优先于 MEDDEV 2.7/1 Rev.4
2. Legacy device ≠ MDR sufficient clinical evidence
3. WET 可考虑较低证据水平，但必须满足 6 条件
4. 等效路径必须三维比较 + data access
5. PMCF 不补 unsupported core claim
6. Writer conclusion strength 服从 evidence strategy

---

## 6. 四批次

| Batch | 覆盖 | 核心产出 |
|:---|:---|:---|
| I | P0-1 + P0-2 | Strategy router + evidence burden engine + route decision matrix |
| J | P0-3 | Literature role classifier + article appraisal + eligibility rules |
| K | P0-4 | Route-specific CER blueprints + Writer constraints + human gates |
| L | P0-5 + Validation | NB explainability packet + real project validation + submission review |

**执行顺序：** I→J→K→L 严格顺序。I 决定路线 → J 按路线评文献 → K 按路线写 CER → L 按路线解释给 NB。

---

## 7. 目标与限制

- **工程成熟度目标：** 87 → 90–92
- **不以 100 为目标**：V4 不改变 V3 的 gold asset 缺失现状
- **不以无人工复核提交为目标**：V4 提升策略判断可靠性，最终 CER 仍需人工法规专家复核
- **停止条件：** 法规策略判断依赖的资产缺失且无 heuristic 替代 → STOP；WET/legacy 判断涉及临界风险且无 expert judgement → STOP

---

## 8. 法规参考文件

| 文件 | 用途 |
|:---|:---|
| MDR 2017/745 Article 61 + Annex XIV | Clinical evaluation requirements |
| MEDDEV 2.7/1 Rev.4 | Clinical evaluation methodology (supplementary) |
| MDCG 2020-5 | Equivalence guidance |
| MDCG 2020-6 | Clinical evidence requirements |
| MDCG 2020-13 | CEAR template |
| ISO 14155:2020 | Clinical investigation |
| ISO 14971:2019 | Risk management |
