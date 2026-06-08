# BIGDP2026.6V_3 — Asset Dependency Plan

**Current Asset State:** Patch A extraction — 18 projects, Tier 1 PASS (structure), Tier 2 PARTIAL (TO_BE_EXTRACTED placeholders).
**Path:** Path B (Capped Expert Validation).

---

## 1. Per-Upgrade Asset Dependency

| Upgrade | Required Assets | Asset Status | If Missing | Max Closure Level |
|:---|:---|:---|:---|:---|
| U1 Clinical Fact V2 | B4 PMID trace, B5 denominator | PARTIAL | heuristic rules + synthetic fixtures for regex-based extraction; table/figure extraction limited to structural | CLOSED_WITH_HEURISTIC_VALIDATION |
| U2 Semantic Validator | C3 claim-evidence support | PARTIAL | derived validation from accepted CER reverse-labeling | CLOSED_WITH_DERIVED_VALIDATION |
| U3 Equivalence Gate | 等效性分析文件 + EQV Rulebook | EQV Rulebook READY, 分析文件 PARTIAL | Rulebook rules sufficient for structural checks; impact analysis needs project data | CLOSED_WITH_DERIVED_VALIDATION |
| U4 Domain Library | C1 endpoint labels, C2 comparator benchmark | PARTIAL | endpoint classifier (已有) + domain inference from project metadata + heuristic template generation | CLOSED_WITH_HEURISTIC_VALIDATION |
| U5 BR Crosswalk | B4/B5/C3 data | PARTIAL | derived from existing ledgers (CER_REASONING_LEDGER, benefit_risk_ledger); structural crosswalk possible without gold labels | CLOSED_WITH_DERIVED_VALIDATION |
| U6 Writer QA | D2 CER originals, D3 Writer outputs | PARTIAL | historical CER text (Level 2) + synthetic prose (Level 3) | CLOSED_WITH_DERIVED_VALIDATION |

---

## 2. Path A vs Path B

**V3 无法走 Path A。** 理由：
- 12 个 Core Validation Assets 中 7 个仍为 NOT_FOUND
- 关键 gold labels（manual search gold、screening gold、PMID verification、denominator gold、comparator gold、SOTA gold、claim-evidence labels）不存在
- Endpoint expert labels 为 PARTIAL（CLAUDE.md derived，非 Domain Expert verified）

V3 走 Path B：实现可实现的，mark 不可实现的，按 SCORE_CAP_RULES 扣分。

---

## 3. 资产状态明细

| Asset | Status | U1 | U2 | U3 | U4 | U5 | U6 |
|:---|:---|:--:|:--:|:--:|:--:|:--:|:--:|
| B4 PMID trace | PARTIAL | ✅ | — | — | — | ✅ | — |
| B5 denominator labels | PARTIAL | ✅ | — | — | — | ✅ | — |
| C1 endpoint semantics | PARTIAL | — | — | — | ✅ | — | — |
| C2 comparator benchmark | PARTIAL | — | — | — | ✅ | — | — |
| C3 claim-evidence support | PARTIAL | — | ✅ | — | — | ✅ | — |
| D2 CER originals | PARTIAL | — | — | — | — | — | ✅ |
| D3 Writer outputs | PARTIAL | — | — | — | — | — | ✅ |
| EQV Rulebook | READY | — | — | ✅ | — | — | — |
| 等效性分析文件 | PARTIAL | — | — | ✅ | — | — | — |

---

## 4. 哪些可以现在做（不依赖 Tier 2）

| 工作 | 依赖 | 状态 |
|:---|:---|:---|
| clinical_fact_registry_v2 结构设计 | 无 | ✅ 可立即开始 |
| statistical fact parser 框架 | 无 | ✅ 可立即开始 |
| 正则表达式扩展（HR/RR/OR/CI） | 无 | ✅ 可立即开始 |
| semantic_support_validator 框架 | 无 | ✅ 可立即开始 |
| equivalence_runtime_gate 框架 | EQV Rulebook (READY) | ✅ 可立即开始 |
| endpoint_domain_template 结构 | 无 | ✅ 可立即开始 |
| BR crosswalk 结构设计 | 无 | ✅ 可立即开始 |
| post_write_QA detector 框架 | 无 | ✅ 可立即开始 |

---

## 5. 哪些需要 Tier 2 资产 READY

| 工作 | 依赖资产 | 需要什么 |
|:---|:---|:---|
| table/figure data extraction | B4 PMID trace | 真实 PMID 的 table 数据验证 |
| subgroup detector 校准 | B5 denominator | 真实 subgroup 标注 |
| semantic validator 校准 | C3 claim-evidence | claim-evidence 配对 gold labels |
| equivalence impact analysis | 等效性分析文件 | 三维比较的实际数据 |
| domain template 填充 | C1/C2 | endpoint 分类 + comparator 数据 |
| BR crosswalk 校准 | B4/B5/C3 | 数据质量验证 |
| Writer QA 校准 | D2/D3 | CER before/after 文本 |

---

## 6. 需要 Domain Expert 的

| 工作 | 为什么需要专家 |
|:---|:---|
| endpoint taxonomy 扩展 | 新设备类型的 endpoint 分类需要临床判断 |
| AE vs treatment_failure 边界案例 | 规则无法覆盖的模糊场景 |
| equivalence 三维比较的边界案例 | 技术/生物/临床相似性判断 |
| BR conclusion strength 的边界案例 | risk acceptability 判断 |

这些在 V3 范围内只能标记为 DOMAIN_DECISION_BLOCKED 或 HEURISTIC_ONLY。不阻塞整体进度，但在 scorecard 中如实扣分。
