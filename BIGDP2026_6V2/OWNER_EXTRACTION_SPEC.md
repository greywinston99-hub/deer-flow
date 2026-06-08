# BIGDP2026.6V_2 — Owner 资料提取规范

**用途：** Owner 从 44 个项目 + 法规文件中提取资料，供 Batch B/C/D/Final 使用。
**原则：** 只提取，不分析。每份提取物有明确的 Batch/DC 落点。
**颗粒度要求：** 每个提取任务都链接到具体的已知缺陷、CLAUDE.md 规则、或工程师反馈中的精确 PMID/数值。不提取"一般信息"，只提取能直接用于校准、测试、规则归纳的信息。

---

## 一、提取总览

| Batch | 需要信息 | 来源文件夹 | 输出格式 |
|:---|:---|:---|:---|
| B | 检索记录、筛选决策、PMID-数据映射、全文状态、分母 | `01_CER_SOURCE_PACKAGE` > `CLINICAL_EVIDENCE` > `CER` | CSV |
| B | NB 对数据质量的意见 | `02_NB_BENCHMARK_ORIGINAL` > `NB_REVIEW_COMMENTS` | 原文摘录 MD |
| C | Endpoint 分类、比较器基准值 | `01_CER_SOURCE_PACKAGE` > `CER` > `CLINICAL_EVIDENCE` | CSV |
| C | NB 对 endpoint/equivalence 的意见 | `02_NB_BENCHMARK_ORIGINAL` > `NB_QUESTIONS` | 原文摘录 MD |
| D | SOTA 数字、CER 正文、前后修订对比 | `01_CER_SOURCE_PACKAGE` > `CER` + `03_COMPANY_RESPONSES` | 原文文件 |
| D | NB 最终验收结论 | `03_COMPANY_RESPONSES` > `CLOSURE_RECORDS` | 原文摘录 MD |
| 全阶段 | 法规规则 | `/Users/winstonwei/CER-RAG/Source/EU MDCG/` | 原文文件 |

---

## 二、按 Batch 的详细提取任务

### Batch B — 证据完整性（6 个 DC）

#### 任务 B1：检索审计信息 → 落点 DC-1, DC-2
**源文件夹：** `01_CER_SOURCE_PACKAGE/CLINICAL_EVIDENCE/` 中的文献检索报告
**查找关键词：** "search strategy", "PubMed", "Embase", "检索策略", "检索词", "query", "PRISMA"
**提取内容：** 检索词、数据库名称、检索日期、命中数、筛选后数量、入选 PMID 列表
**输出格式：** 每个项目一个 `B1_SEARCH_AUDIT.csv`，字段：

```
project_id, search_round, database, query_string, date_executed, total_hits, humans_filter_applied, humans_hits, dedup_hits, included_pmids, excluded_pmids
```

**最低要求：** 至少 3 个项目有完整检索记录（含检索词）。如果有项目完全没有检索记录 → 标记 `NO_SEARCH_RECORD`。

#### 任务 B2：筛选决策记录 → 落点 DC-3
**源文件夹：** `01_CER_SOURCE_PACKAGE/CLINICAL_EVIDENCE/` 中的文献筛选表
**查找关键词：** "inclusion", "exclusion", "筛选", "纳入", "排除", sample size, N=
**提取内容：** 每篇文献的 PMID、纳入/排除决定、排除原因、样本量
**输出格式：** `B2_SCREENING.csv`（跨项目汇总），字段：

```
project_id, pmid, title, sample_size, decision (included/excluded), exclusion_reason, exclusion_reason_code (N_LT_10/ANIMAL/IN_VITRO/REVIEW/WRONG_POPULATION/OTHER), date_range_start, date_range_end
```

**最低要求：** 至少包含 5 个 "N<10 应排除但纳入" 的案例，和 5 个 "正确排除" 的案例。

#### 任务 B3：全文可用性标记 → 落点 DC-5
**源文件夹：** `01_CER_SOURCE_PACKAGE/CLINICAL_EVIDENCE/` 中的 PDF 全文
**提取内容：** 每个 PMID 的全文状态
**输出格式：** `B3_FULLTEXT_STATUS.csv`，字段：

```
project_id, pmid, fulltext_status (obtained/abstract_only/unobtainable), has_numerical_data, data_source (abstract/fulltext_table/fulltext_text/unknown)
```

**最低要求：** 覆盖至少 20 个 PMID。

#### 任务 B4：PMID-数据溯源 → 落点 DC-4
**源文件夹：** `01_CER_SOURCE_PACKAGE/CER/` 中的临床数据表、endpoint 表
**提取内容：** CER 中引用的每个具体数据点 → 它的来源 PMID → PMID 中是否真的存在该数据
**输出格式：** `B4_PMID_TRACE.csv`，字段：

```
project_id, data_point_description, data_point_value, source_pmid, data_found_in_abstract (yes/no/unknown), data_found_in_fulltext (yes/no/unknown), source_sentence_or_location, confidence (high/medium/low/unverifiable)
```

**最低要求：** 覆盖至少 20 个数据点。

#### 任务 B5：分母/子组标注 → 落点 DC-10
**源文件夹：** `01_CER_SOURCE_PACKAGE/CER/` 中的安全性和有效性数据表
**提取内容：** 每个 rate/proportion 的分子、分母、人群标签
**输出格式：** `B5_DENOMINATOR.csv`，字段：

```
project_id, pmid, endpoint, numerator, denominator, population_label (total/subgroup_name), study_reported_total_n, denominator_matches_study (yes/no), subgroup_correctly_labeled (yes/no)
```

**最低要求：** 包含至少 3 个 "分母混用" 案例（例如 N=216 总样本 vs n=80 子组）。

---

### Batch C — 专家语义可靠性（2 个 DC）

#### 任务 C1：Endpoint 语义分类标注 → 落点 DC-6
**源文件夹：** `01_CER_SOURCE_PACKAGE/CER/` 中的 endpoint 表 + `02_NB_BENCHMARK_ORIGINAL/NB_REVIEW_COMMENTS/` 中 NB 对 endpoint 分类的意见
**提取内容：** 为每个 endpoint 标注正确的语义类别
**标注选项：** `adverse_event` / `serious_adverse_event` / `treatment_failure` / `rescue_therapy_switch` / `inadequate_hemostasis` / `device_deficiency` / `procedural_outcome` / `other`
**输出格式：** `C1_ENDPOINT_SEMANTICS.csv`，字段：

```
project_id, endpoint_name, endpoint_value, correct_semantic_class, common_misclassification, classification_basis (ISO_14155/NB_comment/engineer_correction/expert_judgment), source_evidence
```

**最低要求：** 至少 10 个 endpoint 标注，其中至少 3 个是 `treatment_failure` 或 `inadequate_hemostasis`（非 AE）。

#### 任务 C2：比较器 Benchmark 数据 → 落点 DC-7
**源文件夹：** `01_CER_SOURCE_PACKAGE/CLINICAL_EVIDENCE/` 中的 SOTA/benchmark/literature review
**查找关键词：** "comparator", "alternative", "benchmark", "tourniquet", "suture", "staples", "止血带", "缝线", "缝钉"
**提取内容：** 替代疗法/比较器的性能数据（含 CI 和来源）
**输出格式：** `C2_COMPARATOR_BENCHMARK.csv`，字段：

```
project_id, comparator_name, endpoint, point_estimate, ci_lower, ci_upper, sample_size, source_pmid, directness (direct/indirect/fallback), data_in_original_cer (yes/no/missing), limitation_if_missing
```

**最低要求：** 至少 5 个比较器数据点，含至少 2 个带 CI 的。

#### 任务 C3：Claim-Evidence 支撑标注 → 落点 Claim-Evidence Semantic
**源文件夹：** `01_CER_SOURCE_PACKAGE/CER/` 中的 claim/evidence 矩阵或结论章节
**提取内容：** 每个临床声明 → 支撑它的证据类型和强度
**输出格式：** `C3_CLAIM_EVIDENCE_SUPPORT.csv`，字段：

```
project_id, claim_id, claim_text, evidence_pmid, evidence_support_type (direct/indirect/equivalent/manufacturer/PMS), endpoint_match (yes/partial/no), population_match (yes/partial/no), support_strength (strong/moderate/weak), n_evidence_items
```

---

### Batch D — 验证与 Writer QA（3 个 DC）

#### 任务 D1：SOTA Accounting 数字 → 落点 DC-8, DC-9
**源文件夹：** `01_CER_SOURCE_PACKAGE/CER/` 中的 SOTA 章节或 standalone SOTA report
**提取内容：** 检索策略组数、原始记录数、去重后、筛选后、全文评估数、纳入研究数、证据条目数
**输出格式：** `D1_SOTA_ACCOUNTING.csv`，字段：

```
project_id, section, search_groups_count, raw_records, dedup_records, screened_records, fulltext_assessed, included_studies, evidence_items, numbers_consistent (yes/no), inconsistency_description
```

**最低要求：** 至少 2 个项目有完整 SOTA 数字（最好有数字不一致的项目）。

#### 任务 D2：跨章节一致性检查素材 → 落点 DC-8
**源文件夹：** `01_CER_SOURCE_PACKAGE/CER/` 的完整 CER 文档
**提取内容：** 完整 CER Word/PDF 文件，标注哪些章节定义了 endpoint，哪些章节引用了 endpoint
**输出格式：** 不做 CSV — 直接提供 CER 原文文件 + `D2_CROSS_CHAPTER_NOTES.md`：

```
project_id, cer_file, section, endpoint_definition_or_usage, endpoint_count_in_section, consistent_with_other_sections (yes/no/unknown)
```

#### 任务 D3：Writer 输出素材 → 落点 DC-11
**源文件夹：** `03_COMPANY_RESPONSES/CLOSURE_RECORDS/` 中的最终提交版本 + `01_CER_SOURCE_PACKAGE/CER/` 原始版本
**提取内容：** CER 的原始版本（修改前）和最终版本（NB 验收后），形成 before/after 对比
**输出格式：** 原文文件 + `D3_WRITER_OUTPUT_MANIFEST.csv`：

```
project_id, version (draft/submitted/NB_accepted), cer_file_path, has_writer_issues (yes/no), known_issues_description
```

#### 任务 D4：真实项目验证素材 → 落点 Real Project Validation
**源文件夹：** 选择一个资料最完整的项目
**提取内容：** IFU + RMF + GSPR + literature search + CER draft + CER final + NB review + company response
**输出格式：** `D4_VALIDATION_PROJECT/` 目录，包含完整项目文件 + `D4_PROJECT_READINESS.md` 说明文件完整性。

**推荐候选项目（按优先级）：**

| 优先级 | 项目 | 原因 |
|:--:|:---|:---|
| 1 | `PROJECT_029_苏州心擎` | 心擎=心室辅助/循环支持设备 — endpoint 语义丰富（AE vs device failure vs treatment escalation），适合 DC-6. 可能有完整 NB 审核记录 |
| 2 | `PROJECT_005_北京海杰亚` | 消融设备 — endpoint 清晰（消融成功/并发症），适合 DC-6/DC-10. 已有 manifest |
| 3 | `PROJECT_021_青岛德迈迪` | CLAUDE.md 特别提到此项目 |
| 4 | `PROJECT_042_安徽巨目` | BIGDP2026.6 Phase 7 dry-run 使用过，已有输出 baseline |

---

### 法规文件提取

**源文件夹：** `/Users/winstonwei/CER-RAG/Source/EU MDCG/`

**必须提取的文件：**

| 文件 | 用途 | Batch |
|:---|:---|:---|
| `MDR_02017R0745-...` | MDR Annex XIV 临床评价要求 | 全阶段 |
| `05 MDCG 2020-5...` | 等效性指南 | C3 |
| `md_mdcg_2019_7...` | 临床证据要求 | B2, B3 |
| `CEAR.pdf` | 临床评价评估报告模板 | D |
| `md_cybersecurity_en.pdf` | 网络安全（如涉及软件设备） | C4 |
| `md_mdcg_2020-10-1...` | 安全报告指南 | C1 (AE 分类) |

**最低要求：** 上述 6 个文件就位。127 个文件全部可选。

---

## 三、输出目录结构

提取完成后，请按此结构组织：

```
BIGDP2026_6V2/assets/
├── batch_B/
│   ├── B1_search_audit/          ← 每个项目的检索审计 CSV
│   ├── B2_screening/             ← 跨项目筛选 CSV
│   ├── B3_fulltext_status/       ← 跨项目全文状态 CSV
│   ├── B4_pmid_trace/            ← 跨项目 PMID 溯源 CSV
│   └── B5_denominator/           ← 跨项目分母标注 CSV
├── batch_C/
│   ├── C1_endpoint_semantics/    ← Endpoint 语义分类 CSV
│   ├── C2_comparator_benchmark/  ← 比较器基准 CSV
│   └── C3_claim_evidence/        ← Claim-Evidence 支撑 CSV
├── batch_D/
│   ├── D1_sota_accounting/       ← SOTA 数字 CSV
│   ├── D2_cer_originals/         ← CER 原文文件
│   ├── D3_writer_outputs/        ← Writer 输出 before/after
│   ├── D4_validation_project/    ← 验证项目完整文件
│   └── NB_feedback_excerpts/     ← NB 意见摘录
├── regulatory/
│   └── (法规文件)
└── ASSET_READINESS_REGISTER.csv  ← 更新状态
```

---

## 四、项目优先级

从Master Index 来看，以下项目最有价值（有 CER + NB material）：

| 优先级 | 提取范围 | 说明 |
|:--:|:---|:---|
| **P0** | 3 个项目：选 2 个设备类型差异大的 + 1 个有完整 NB review | 校准用 |
| **P1** | 3 个项目：选不同设备类型 | Stress test 用 |
| **P2** | 2 个项目：选资料完整但在校准中未使用的 | Holdout 用 |
| **P3** | 其余 36 个项目 | 可选 — 用于验证泛化能力 |

**不需要 44 个项目全提取。8 个项目足以覆盖所有 Batch。**

---

## 五、提取后下一步

1. Owner 完成提取 → 文件放到 `assets/` 目录
2. Controller 更新 `ASSET_READINESS_REGISTER.csv`（READY/PARTIAL 变化）
3. Claude Code 读取提取物，回填 `ASSET_DEPENDENCY_MATRIX.csv` 中的 UNKNOWN 字段
4. 如 12 Core Assets 中 ≥8 变为 READY → 重新评估 Path A/B
5. 继续 Batch B 实施（DC-4 补充）+ Batch C + Batch D

---

## 六、参考锚点：每个提取任务对应的已知缺陷和规则

以下为每个提取任务提供精确的参考锚点，来源均为已有文件。确保提取的信息有明确的下游用途。

### B1 检索审计 → DC-1, DC-2

**已知缺陷：** iTClamp 项目人工检索 18 篇→Humans 13 篇→AI 只入选 3 篇（recall=23%）。检索报告只显示数量不显示检索词。

**CLAUDE.md §Literature Management Line 148：** "Every literature search MUST document: exact PubMed query string, date executed, total hits, Humans filter applied, number after each exclusion criterion."

**Defect Map DC-1 Line 16-17：** 需要 `query_string, database, date, total_hits, humans_filter`。

**提取重点：** 有完整 query_string 的检索 → 正例。只有数量无检索词 → 负例。人工 vs 系统检索对比。

---

### B2 筛选决策 → DC-3

**CLAUDE.md Line 143：** "EXCLUDE: Case reports with N<10 patients. EXCLUDE: Animal studies, cadaver studies, porcine/swine models, in vitro only."

**Defect Map DC-3 Line 50：** `N<10 → EXCLUDE (case_report_insufficient); animal/cadaver/in-vitro → EXCLUDE`。

**提取时对标以下 reason_code：**

| code | 含义 | 引用 |
|:---|:---|:---|
| `N_LT_10` | 样本量不足 | CLAUDE.md L143 |
| `ANIMAL` | 动物/尸体/离体 | CLAUDE.md L143 |
| `REVIEW` | 综述作原始数据 | CLAUDE.md L144 |
| `NO_FULLTEXT` | 全文不可得 | CLAUDE.md L158 |
| `TIME_UNSPECIFIED` | 时间范围未记录 | Defect Map DC-3 |

**提取重点：** 正确排除 N<10 的→正例。错误纳入 N<10 的→负例（iTClamp 2-case 文献）。

---

### B3 全文状态 → DC-5

**Defect Map DC-5 Line 78-86：** 人工无法下载全文但系统仍生成数据。需要 `fulltext_status` per PMID：`obtained / abstract_only / unobtainable`。

**CLAUDE.md Line 158：** "Mark each cited PMID as: ✅ Full-text available / ⚠️ Abstract only / ❌ Unobtainable."

**提取重点：** `abstract_only` 的 PMID 在 CER 中产生了数值→负例。

---

### B4 PMID 溯源 → DC-4

**已知精确 PMID（来自工程师反馈）：**
- PMID 31539432 — 数据在 abstract 中找不到
- PMID 32209132 — 同上
- PMID 30635996（McKee JL 2019）— 分母混用

**CLAUDE.md §Data Traceability Line 152-160：** "Every numerical data point MUST be traceable to source PMID. PMID-anchor required. Abstract-verify required. Zero tolerance for orphan data."

**提取重点：** 打开上述 3 个 PMID 的 PubMed abstract，核对 CER 中引用的数据是否真实存在于 abstract 中。标注 `data_found_in_abstract: yes/no`。

---

### B5 分母标注 → DC-10

**已知精确案例：** PMID 30635996, N=216 total, CMF 子集 n=80。报告写成 "87.5% (70/80), N=216" — `N=216` 应该对应 `70/216=32.4%`而非 `87.5%`。

**Defect Map DC-10 Line 169：** "每个 rate 必须标注 numerator, denominator, population (total/subgroup)。denominator 与 study reported N 不一致 → BLOCKED。"

**提取重点：** 重新计算 percentage 验证分母是否正确。子组结果是否被标注为总体结果。

---

### C1 Endpoint 语义 → DC-6

**已知缺陷：** "装置弃用→直接压迫" 和 "装置弃用→止血带" 被标为 AE。应该是 treatment_failure 或 rescue_therapy_switch。

**CLAUDE.md §Endpoint Classification Line 164-167：**

| 正确分类 | 定义 |
|:---|:---|
| `adverse_event` | Device-related untoward medical event (ISO 14155) |
| `treatment_failure` | Clinical decision to abandon device. NOT an AE |
| `inadequate_hemostasis` | Efficacy endpoint, not safety AE |

**提取重点：** 任何"装置弃用→替代疗法"被标为 AE 的→高价值负例。NB review 指出 endpoint 分类错误的→最高价值。

---

### C2 比较器 Benchmark → DC-7

**已知缺陷：** 替代疗法（止血带、缝线、缝钉）有数据但 benchmark 表缺失。有数据的比较器无 CI。

**CLAUDE.md §Statistical Consistency Line 170：** "Wilson Score 95% CI must be computed for EVERY reportable rate. No bare percentages without CI context."

**提取重点：** 比较器表中有数值无 CI→负例。有数值有 CI 有 source PMID→正例。

---

### D1 SOTA Accounting → DC-8, DC-9

**已知精确案例：** "13 篇文章" vs "14 检索词组 / 1000 records / 183 fulltext / 219 evidence" — 自相矛盾。

**Defect Map DC-9 Line 152：** "article_count 必须等于 screening 的 included_count。evidence_count 必须等于 appraisal 的 appraised_count。"

**提取重点：** 同一 SOTA 报告中相邻段落数字不一致→负例。

---

### D2 跨章节一致性 → DC-8

**已知缺陷：** 前文 4 个安全性终点 → 后文综合对比变成 1 个 "1.7% 皮肤损伤"。

**提取重点：** §5（安全性）vs §6（讨论/对比）的 endpoint 列表是否一致。同一 endpoint 值在不同章节是否一致。

---

## 七、所有参考材料索引

| # | 文件 | 用途 |
|:--:|:---|:---|
| 1 | `~/.claude/CLAUDE.md` | 全文 CER 规则——一切提取的最高标准来源 |
| 2 | `BIGDP2026_6V2/BIGDP2026_6V2_ENGINEER_FEEDBACK_DEFECT_MAP.md` | 10 类缺陷的精确 PMID、错误值、所需素材 |
| 3 | `BIGDP2026_6V2/resource_planning/ENGINEER_FEEDBACK_COVERAGE_TARGETS.md` | 每类缺陷的最小可用素材 |
| 4 | `BIGDP2026_6V2/SCORE_CAP_RULES.md` | 扣分规则——告诉你哪些提取物对分数影响最大 |
| 5 | `BIGDP2026_6V2/ASSET_DEPENDENCY_MATRIX.csv` | 每个 DC 依赖的资产列表 |
| 6 | `BIGDP2026_6V2/VALIDATION_PATH_DECISION.md` | 当前 Path B 缺口——提取后哪些可能变 READY |
| 7 | `BIGDP2026_6V2/BIGDP2026_6V2_MASTER_PLAN.md` | 整体升级路线 |
| 8 | `BIGDP2026_6V2/EXPERT_LABEL_SOURCE_POLICY.md` | 标签来源信心级别 |
| 9 | `BIGDP2026_6V2/LOCKED_FEEDBACK_USE_POLICY.md` | NB/engineer feedback 使用边界 |

## 八、每份提取物的下游用途

| 提取物 | 直接校准 | 生成 |
|:---|:---|:---|
| B1 检索 CSV | DC-1/2 gold/counter examples | G_RETRIEVAL_AUDIT test fixtures |
| B2 筛选 CSV | DC-3 screening rules | G_SCREENING reason_code classifier |
| B3 全文 CSV | DC-5 fulltext policy | G_FULLTEXT_BASIS gate 强化 |
| B4 PMID CSV | DC-4 anchor validator | PMID 31539432/32209132 test fixtures |
| B5 分母 CSV | DC-10 denominator validator | McKee-style test fixtures |
| C1 Endpoint CSV | DC-6 semantic classifier | AE/treatment_failure 分类规则 |
| C2 Comparator CSV | DC-7 completeness checker | Wilson CI 验证 |
| C3 Claim-Evidence CSV | Semantic support validator | CER_REASONING_LEDGER 质量 |
| D1 SOTA CSV | DC-8/9 accounting checker | SOTA_ACCOUNTING test fixtures |
| D2 CER 原文 | DC-8 cross-section checker | Writer QA validation |
| D3 Writer before/after | DC-11 writer validator | Post-write representative output |
| D4 验证项目 | All DCs 端到端 | Real project validation score |
