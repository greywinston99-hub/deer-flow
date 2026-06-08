# BIGDP2026.6V_2 — Engineer Feedback Defect Map

**Purpose:** Decompose 10 engineer-reported issues into system-level defect classes.
**Each class maps to:** CER stage → system capability gap → BIGDP2026.6 coverage → upgrade direction.

---

## Defect Class 1: Retrieval Recall Gap

| Field | Value |
|:---|:---|
| **原始反馈** | 人工 iTClamp 检索 18 篇，Humans 后 13 篇，AI 入选 3 篇，存在文献遗漏 |
| **CER 专家阶段** | Stage 3: 文献检索 |
| **系统能力缺口** | 检索策略生成无 recall benchmark；无 search strategy audit trail（检索词未记录）；无 recall measurement mechanism |
| **BIGDP2026.6 覆盖** | `NOT_COVERED` — search_run_registry 存在但只记录"是否执行"，不记录检索词、命中数、recall vs gold set |
| **本轮升级方向** | 新增 `RETRIEVAL_AUDIT_TRAIL` artifact；记录每轮检索的 query_string、database、date、total_hits、humans_filter；新增 G_RETRIEVAL_AUDIT gate；与 manual search gold 对比 recall |
| **所需素材** | Asset 08 Manual Search Gold Set；Asset 02 真实项目检索记录 |
| **所需标注** | 人工检索 gold set → 每篇文献的检索词来源 |
| **Runtime landing** | `graph.py` search nodes + `gates.py` G_RETRIEVAL_AUDIT |
| **Test/fixture** | `fixture_retrieval_recall_gap.json` → assert recall < 50% triggers REWORK |
| **Hard acceptance** | ✅ YES |

---

## Defect Class 2: Retrieval Irreproducibility

| Field | Value |
|:---|:---|
| **原始反馈** | 报告体现检索数量，但未体现检索词，无法溯源数量是否准确 |
| **CER 专家阶段** | Stage 3: 文献检索 |
| **系统能力缺口** | 检索过程不透明；无法从输出反推输入；NB 审核无法验证检索完整性 |
| **BIGDP2026.6 覆盖** | `NOT_COVERED` |
| **本轮升级方向** | `RETRIEVAL_AUDIT_TRAIL` 必须包含完整检索词；`CER_INPUT_PACKAGE` 必须包含 search_strategy section；Claude Code Writer 引用检索词时必须注明来源；新增 PRISMA reproducibility check |
| **所需素材** | Asset 01 法规（PRISMA 标准）；Asset 08 Manual Search |
| **所需标注** | 无（结构性问题，不需专家标注） |
| **Runtime landing** | `prisma_reproducibility.py` + search node output |
| **Test/fixture** | `fixture_missing_query_string.json` → assert G_RETRIEVAL_AUDIT BLOCKED |
| **Hard acceptance** | ✅ YES |

---

## Defect Class 3: Literature Screening Errors

| Field | Value |
|:---|:---|
| **原始反馈** | iTClamp 入选 2-case 样本文献，N<10 应排除；检索时间范围不清楚 |
| **CER 专家阶段** | Stage 4: 文献筛选与评价 |
| **系统能力缺口** | 无自动化 inclusion/exclusion 规则引擎；样本量阈值未强制执行；时间范围未记录 |
| **BIGDP2026.6 覆盖** | `NOT_COVERED` |
| **本轮升级方向** | 新增 `SCREENING_RULE_ENGINE`：N<10 → EXCLUDE（case_report_insufficient）；time_range 未指定 → REWORK；animal/cadaver/in-vitro → EXCLUDE。每个排除决策有 reason_code。新增 G_SCREENING gate |
| **所需素材** | Asset 01 法规（CER 文献纳入排除标准）；Asset 02 真实项目筛选记录；Asset 08 Manual Search Gold |
| **所需标注** | 人工筛选 gold set → inclusion/exclusion labels per PMID |
| **Runtime landing** | `pipeline.py` screening functions + `gates.py` G_SCREENING |
| **Test/fixture** | `fixture_screening_n_lt_10.json` → assert EXCLUDE with reason_code |
| **Hard acceptance** | ✅ YES |

---

## Defect Class 4: Data Untraceable to PMID

| Field | Value |
|:---|:---|
| **原始反馈** | PMID 31539432、PMID 32209132 类似文献中找不到报告描述的数据 |
| **CER 专家阶段** | Stage 5: 临床数据提取 |
| **系统能力缺口** | 数据提取无 PMID 锚定；无 abstract-verify 步骤；数据可凭空生成 |
| **BIGDP2026.6 覆盖** | `PARTIAL` — evidence_registry 有 evidence_id，但无 PMID-trace 验证；lineage 是 best-effort |
| **本轮升级方向** | 新增 `PMID_ANCHOR` rule：每个临床数据点必须有 source PMID + abstract_verified flag；新增 `DATA_TRACEABILITY_VALIDATOR`；G46 增加 data-traceability condition |
| **所需素材** | Asset 06 Full-text/Clinical data；Asset 03 工程师反馈（具体 PMID 和错误数据） |
| **所需标注** | Expert labels：每个 clinical data point 标记"abstract 可验证"或"仅 full-text 可验证" |
| **Runtime landing** | `gates.py` G46 new condition + `pipeline.py` traceability validator |
| **Test/fixture** | `fixture_orphan_data_no_pmid.json` → assert G46 BLOCKED |
| **Hard acceptance** | ✅ YES |

---

## Defect Class 5: Full-Text Unavailability — Data Fabrication Risk

| Field | Value |
|:---|:---|
| **原始反馈** | 文献人工无法下载全文，但系统仍生成具体数据 |
| **CER 专家阶段** | Stage 5: 临床数据提取 |
| **系统能力缺口** | 无 full-text availability check；abstract-only 文献可被用于生成"具体数据"；无"数据可信度"标记 |
| **BIGDP2026.6 覆盖** | `NOT_COVERED` |
| **本轮升级方向** | 新增 `FULLTEXT_STATUS` per evidence：obtained / abstract_only / unobtainable；abstract_only 文献标记为 `confidence: low`，不可用于生成具体数值型数据；新增 `G_FULLTEXT_BASIS` gate（已有框架，强化实现） |
| **所需素材** | Asset 06 Full-text availability mapping；Asset 03 工程师反馈（具体无全文的 PMID） |
| **所需标注** | Full-text availability status per PMID（可由系统自动检测 + 人工确认） |
| **Runtime landing** | `gates.py` G41 fulltext_basis_gate（已有，需强化）+ `pipeline.py` data extraction node |
| **Test/fixture** | `fixture_abstract_only_generates_data.json` → assert G46 BLOCKED or confidence=low |
| **Hard acceptance** | ✅ YES |

---

## Defect Class 6: Endpoint Semantic Misclassification

| Field | Value |
|:---|:---|
| **原始反馈** | iTClamp 安全性终点"装置弃用→直接压迫""装置弃用→止血带"不应直接算作不良事件，可能是止血不到位或换用其他器械 |
| **CER 专家阶段** | Stage 6: 终点与 Benchmark 建立 |
| **系统能力缺口** | 无 endpoint 语义分类器；AE vs treatment failure vs inadequate hemostasis 无区分规则 |
| **BIGDP2026.6 覆盖** | `PARTIAL` — endpoint_registry 存在但只有名称列表，无 classification rules |
| **本轮升级方向** | 新增 `ENDPOINT_SEMANTIC_CLASSIFIER`：AE（device-related untoward medical event）/ treatment_failure（clinical decision to abandon）/ inadequate_hemostasis（efficacy limitation）/ other。基于 ISO 14155 术语。新增 `G_ENDPOINT_SEMANTICS` gate |
| **所需素材** | Asset 01 法规（ISO 14155 AE 定义）；Asset 07 Expert labels（endpoint classification） |
| **所需标注** | Expert labels：每个 endpoint 标记 correct semantic class |
| **Runtime landing** | `gates.py` G_ENDPOINT_SEMANTICS + `pipeline.py` endpoint extraction |
| **Test/fixture** | `fixture_device_abandonment_as_ae.json` → assert reclassified as treatment_failure |
| **Hard acceptance** | ✅ YES |

---

## Defect Class 7: Comparator Benchmark Incompleteness

| Field | Value |
|:---|:---|
| **原始反馈** | 替代疗法如止血带、缝线、缝钉等，只要能体现具体数据，都应提供范围值，例如 81.3% (76.1%–85.6%) |
| **CER 专家阶段** | Stage 6: 终点与 Benchmark 建立 |
| **系统能力缺口** | Comparator benchmark 只覆盖了已知 domain 的主要 comparator；替代疗法数据被忽略；无 CI 计算要求 |
| **BIGDP2026.6 覆盖** | `PARTIAL` — BENCHMARK_DERIVATION_TRACE 存在，benchmark_domains.yaml 可扩展，但 CI 计算和 comparator 完整性未强制 |
| **本轮升级方向** | 新增 `COMPARATOR_BENCHMARK_COMPLETENESS` check：每个 endpoint 必须有 comparator data（如有）；每个 rate 必须有 Wilson 95% CI；无 comparator → limitation 声明 |
| **所需素材** | Asset 02 真实项目（comparator 数据）；Asset 07 Expert labels（acceptable benchmark range） |
| **所需标注** | Expert labels：每个 endpoint 的 acceptable comparator benchmark range |
| **Runtime landing** | `v3_1_gates.py` benchmark derivation + `gates.py` G46 benchmark condition |
| **Test/fixture** | `fixture_missing_comparator_benchmark.json` → assert G46 REWORK |
| **Hard acceptance** | ✅ YES |

---

## Defect Class 8: Cross-Chapter Context Inconsistency

| Field | Value |
|:---|:---|
| **原始反馈** | 前文定义 4 个安全性终点，后文综合对比章节又变成 1 个"1.7% 皮肤损伤" |
| **CER 专家阶段** | Stage 11: 专家推理整合 |
| **系统能力缺口** | 无跨章节 endpoint 一致性检查；Writer 可以前后矛盾 |
| **BIGDP2026.6 覆盖** | `PARTIAL` — alignment_gate 存在但只检查矩阵存在性，不检查值一致性 |
| **本轮升级方向** | 新增 `CROSS_CHAPTER_CONSISTENCY_CHECKER`：同一 endpoint 在多个章节出现时值必须一致；新增 Writer semantic QA gate（W7 or equivalent）；cite source section for each endpoint value |
| **所需素材** | Asset 03 工程师反馈（不一致具体案例）；Asset 05 Accepted outputs（一致的正确版本） |
| **所需标注** | Expert labels：跨章节 endpoint mapping（同一 endpoint 在不同章节的正确表达） |
| **Runtime landing** | `writer_remediation/writer_gates.py` 新 gate + `consistency_checker.py` |
| **Test/fixture** | `fixture_endpoint_count_mismatch.json` → assert W_CONSISTENCY BLOCKED |
| **Hard acceptance** | ✅ YES |

---

## Defect Class 9: SOTA Accounting Inconsistency

| Field | Value |
|:---|:---|
| **原始反馈** | 同一 SOTA 结果中出现"13 篇文章""14 个检索词组、1000 records、183 fulltext、219 evidence"等不一致数字 |
| **CER 专家阶段** | Stage 6: 终点与 Benchmark 建立 |
| **系统能力缺口** | SOTA 报告中的数字来自多个节点（search、screening、appraisal），各节点输出未交叉验证；无 accounting consistency check |
| **BIGDP2026.6 覆盖** | `NOT_COVERED` |
| **本轮升级方向** | 新增 `SOTA_ACCOUNTING_CONSISTENCY_CHECKER`：article_count 必须等于 screening 输出的 included_count；evidence_count 必须等于 appraisal 输出的 appraised_count；任何 mismatch → G_SOTA_ACCOUNTING BLOCKED |
| **所需素材** | Asset 10 SOTA Accounting Gold Ledger；Asset 03 工程师反馈（具体不一致数字） |
| **所需标注** | 无（结构性问题，rule-based checker） |
| **Runtime landing** | `gates.py` G_SOTA_ACCOUNTING + `v3_1_gates.py` |
| **Test/fixture** | `fixture_sota_accounting_mismatch.json` → assert G_SOTA_ACCOUNTING BLOCKED |
| **Hard acceptance** | ✅ YES |

---

## Defect Class 10: Denominator / Subgroup Conflation

| Field | Value |
|:---|:---|
| **原始反馈** | PMID 30635996 N=216, CMF 子集 n=80；报告写成 "CMF hemostasis adequate 87.5% (70/80), N=216"，总样本和子组分母混用 |
| **CER 专家阶段** | Stage 5: 临床数据提取 |
| **系统能力缺口** | 数据提取时未区分 total sample 和 subgroup；denominator 未经 subpopulation check |
| **BIGDP2026.6 覆盖** | `NOT_COVERED` |
| **本轮升级方向** | 新增 `DENOMINATOR_VALIDATOR`：每个 rate 必须标注 numerator、denominator、population（total/subgroup）；denominator 与 study reported N 不一致 → BLOCKED；新增 `G_DENOMINATOR` gate |
| **所需素材** | Asset 09 Denominator Gold Labels；Asset 03 工程师反馈（具体错误 PMID 和正确值） |
| **所需标注** | Expert labels：correct denominator assignment per data point |
| **Runtime landing** | `gates.py` G_DENOMINATOR + `pipeline.py` data extraction validator |
| **Test/fixture** | `fixture_denominator_subgroup_mixup.json` → assert G_DENOMINATOR BLOCKED |
| **Hard acceptance** | ✅ YES |

---

## 覆盖汇总

| # | Defect Class | CER Stage | BIGDP2026.6 Coverage | Hard Acceptance |
|:--:|:---|:---|:---|:--:|
| 1 | Retrieval Recall Gap | 3 | NOT_COVERED | ✅ |
| 2 | Retrieval Irreproducibility | 3 | NOT_COVERED | ✅ |
| 3 | Literature Screening Errors | 4 | NOT_COVERED | ✅ |
| 4 | Data Untraceable to PMID | 5 | PARTIAL | ✅ |
| 5 | Full-Text Unavailable → Data Fabrication | 5 | NOT_COVERED | ✅ |
| 6 | Endpoint Semantic Misclassification | 6 | PARTIAL | ✅ |
| 7 | Comparator Benchmark Incompleteness | 6 | PARTIAL | ✅ |
| 8 | Cross-Chapter Context Inconsistency | 11 | PARTIAL | ✅ |
| 9 | SOTA Accounting Inconsistency | 6 | NOT_COVERED | ✅ |
| 10 | Denominator / Subgroup Conflation | 5 | NOT_COVERED | ✅ |
