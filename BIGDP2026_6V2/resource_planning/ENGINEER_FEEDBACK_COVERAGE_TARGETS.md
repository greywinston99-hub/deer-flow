# BIGDP2026.6V_2 — Engineer Feedback Coverage Targets

**Purpose:** Map 10 engineer feedback items to resource requirements. NOT a code solution document.

---

## DC-1: 检索召回不足

| Dimension | Answer |
|:---|:---|
| **需要什么资料验证** | 同一项目的 AI 检索结果 + 工程师手动检索结果，对比 recall（AI 命中数 / 人工命中数） |
| **最适合什么项目** | 工程师已执行手动检索并有完整记录的项目（CAND-001 南驰/iTClamp 为最高优先级） |
| **无该资料时能否用人工 gold label 代替** | 可以。工程师提供"应检索到但未检索到的 PMID 列表" + 对应检索词即可 |
| **Hard acceptance** | ✅ YES |
| **Calibration / Stress / Holdout** | Calibration：用 gold set 校准检索 recall threshold |
| **最小可用素材** | 1 份 manual search record（检索词 + 命中 PMID + 筛选过程） |

## DC-2: 检索不可复现

| Dimension | Answer |
|:---|:---|
| **需要什么资料验证** | 系统输出的检索报告 / search_run_registry，检查是否包含 query_string |
| **最适合什么项目** | 已运行 DeerFlow pipeline 且有 search artifacts 的项目（CAND-003 CER-PJT-0502） |
| **无该资料时能否用人工 gold label 代替** | 不需要 gold label。这是结构性检查（query_string 存在/不存在），无需人类判断 |
| **Hard acceptance** | ✅ YES |
| **Calibration / Stress / Holdout** | Stress：确认 query_string 为空时 gate BLOCKED |
| **最小可用素材** | search_run_registry artifact 或等效输出 |

## DC-3: 小样本文献误纳入

| Dimension | Answer |
|:---|:---|
| **需要什么资料验证** | 系统筛选记录 + 原文 PMID 列表 + 每篇文献的 sample size |
| **最适合什么项目** | 文献池中包含 N<10 或 N=2 case report 的项目（CAND-001 iTClamp） |
| **无该资料时能否用人工 gold label 代替** | 可以。工程师提供 inclusion/exclusion gold labels per PMID |
| **Hard acceptance** | ✅ YES |
| **Calibration / Stress / Holdout** | Calibration：用 gold screening labels 校准筛选规则 |
| **最小可用素材** | 5 个 PMID 的 screening gold labels（含至少 3 个应排除的 N<10 文献） |

## DC-4: 数据不可溯源

| Dimension | Answer |
|:---|:---|
| **需要什么资料验证** | 系统生成的数据点 + 声称的 source PMID + PubMed abstract 原文 |
| **最适合什么项目** | 有具体 PMID 被工程师指出"数据找不到"的项目（CAND-001 — PMID 31539432, PMID 32209132） |
| **无该资料时能否用人工 gold label 代替** | 可以。工程师标注"该 PMID 的 abstract 中是否存在此数据" |
| **Hard acceptance** | ✅ YES |
| **Calibration / Stress / Holdout** | Calibration：用 abstract-verified gold labels 校准 PMID-trace validator |
| **最小可用素材** | 10 个 data point → PMID → abstract_verified gold labels |

## DC-5: 全文不可得仍生成数据

| Dimension | Answer |
|:---|:---|
| **需要什么资料验证** | Fulltext availability mapping per PMID + 系统生成的数据点 |
| **最适合什么项目** | 文献池中有 abstract-only 且系统仍生成了数值的项目 |
| **无该资料时能否用人工 gold label 代替** | 可以。标记每个 PMID 的 fulltext_status (obtained/abstract_only/unobtainable) |
| **Hard acceptance** | ✅ YES |
| **Calibration / Stress / Holdout** | Stress：abstract-only 文献 → 确认系统不生成具体数值或标记 confidence=low |
| **最小可用素材** | 10 个 PMID 的 fulltext_status mapping |

## DC-6: Endpoint 语义错误

| Dimension | Answer |
|:---|:---|
| **需要什么资料验证** | 系统提取的 endpoint 列表 + endpoint class labels（AE / treatment_failure / inadequate_hemostasis / other） |
| **最适合什么项目** | 设备有"装置弃用→替代疗法"场景的止血/闭合器类项目（CAND-001） |
| **无该资料时能否用人工 gold label 代替** | **必须专家标注。** AE vs treatment_failure 区分需要临床判断，不能纯规则推导 |
| **Hard acceptance** | ✅ YES |
| **Calibration / Stress / Holdout** | Calibration：专家标注用于训练 endpoint 语义分类器 |
| **最小可用素材** | 8–10 个 endpoint 的 semantic class expert labels（至少 3 个 treatment_failure） |

## DC-7: Comparator Benchmark 缺失

| Dimension | Answer |
|:---|:---|
| **需要什么资料验证** | 系统生成的 SOTA benchmark table + comparator 数据来源文献 |
| **最适合什么项目** | 有明确替代疗法且文献中有数据的项目（CAND-001 iTClamp — 止血带、缝线、缝钉） |
| **无该资料时能否用人工 gold label 代替** | 可以。工程师提供每个 endpoint 的 acceptable benchmark range（含 CI） |
| **Hard acceptance** | ✅ YES |
| **Calibration / Stress / Holdout** | Calibration：用 gold benchmark ranges 校准 completeness checker |
| **最小可用素材** | 3 个 endpoint 的 comparator benchmark gold ranges |

## DC-8: 上下文 / SOTA Accounting 不一致

| Dimension | Answer |
|:---|:---|
| **需要什么资料验证** | 系统输出的多章节 CER + SOTA 报告（含 endpoint 定义 + 数字） |
| **最适合什么项目** | 已生成完整 CER + SOTA 报告且有工程师反馈的项目 |
| **无该资料时能否用人工 gold label 代替** | 不需要 gold label。结构性 cross-check（同一 endpoint 值是否一致？SOTA article_count 是否等于 screening output？） |
| **Hard acceptance** | ✅ YES |
| **Calibration / Stress / Holdout** | Calibration + Stress：用实际输出测 consistency checker；人为注入不一致测 detection |
| **最小可用素材** | 1 份完整 CER 输出 + 1 份 SOTA 报告（来自同一项目） |

## DC-9: SOTA Accounting 不一致

| Dimension | Answer |
|:---|:---|
| **需要什么资料验证** | SOTA 报告中的数字 + SOTA gold ledger（正确数字） |
| **最适合什么项目** | 工程师已核实 SOTA 数字的项目（CAND-001） |
| **无该资料时能否用人工 gold label 代替** | 可以。工程师提供 gold accounting ledger |
| **Hard acceptance** | ✅ YES |
| **Calibration / Stress / Holdout** | Calibration：用 SOTA gold ledger 校准 accounting checker |
| **最小可用素材** | 1 份 SOTA gold ledger（article_count, search_groups, records, fulltext, evidence 的正确值） |

## DC-10: Denominator / Subgroup 混用

| Dimension | Answer |
|:---|:---|
| **需要什么资料验证** | 系统提取的 data points + denominator 值 + 原始文献的 sample size |
| **最适合什么项目** | 文献中有 subgroup analysis 的项目（CAND-001 — PMID 30635996 N=216, CMF n=80） |
| **无该资料时能否用人工 gold label 代替** | 可以。工程师提供每个 data point 的正确 denominator（total vs subgroup） |
| **Hard acceptance** | ✅ YES |
| **Calibration / Stress / Holdout** | Calibration：用 denominator gold labels 校准 validator |
| **最小可用素材** | 5 个 data point 的 denominator gold labels（含至少 2 个 subgroup） |

---

## Coverage Summary

| Defect Class | Needs Expert Labels? | Best Candidate | Min Viable Material |
|:---|:---:|:---|:---|
| DC-1 Recall | ❌ | CAND-001 | Manual search record |
| DC-2 Reproducibility | ❌ | CAND-003 | Search registry artifact |
| DC-3 Screening | ✅ | CAND-001 | 5 screening gold labels |
| DC-4 PMID trace | ✅ | CAND-001 | 10 abstract-verified labels |
| DC-5 Fulltext | ❌ | CAND-001 | 10 fulltext_status mappings |
| DC-6 Endpoint | ✅✅ | CAND-001 | 8–10 endpoint class labels |
| DC-7 Comparator | ✅ | CAND-001 | 3 benchmark gold ranges |
| DC-8 Consistency | ❌ | CAND-003 | 1 CER + 1 SOTA output |
| DC-9 SOTA accounting | ✅ | CAND-001 | 1 SOTA gold ledger |
| DC-10 Denominator | ✅ | CAND-001 | 5 denominator gold labels |

**CAND-001（南驰/iTClamp）is the strongest Golden Feedback Pack candidate; may cover all 10 defect classes if Owner confirms source and deep scan verifies artifacts. Actual coverage pending A2 authorization + A1 deep scan.**
