# BIGDP2026.6V_2 — Owner 系统性资产提取规范

**目标：** 从 44 个 L1 项目中选取 15–20 个项目，提取结构化资产，使 Patch A 输出可直接被 Batch B/C/D/Final 吸收为 rule / fixture / semantic test / runtime validator / writer QA / validation evidence。
**原则：** 每条提取数据必须带着吸收目的出生——有 target_batch、target_dc、score_area、dataset_role、evidence_level、absorption_type。不提取"一般信息"。
**参考锚点：** `~/.claude/CLAUDE.md`（全文 CER 规则）、`BIGDP2026_6V2/BIGDP2026_6V2_ENGINEER_FEEDBACK_DEFECT_MAP.md`（10 类缺陷精确描述）、`SCORE_CAP_RULES.md`（扣分规则）。

---

## 一、本轮排除项目

**南驰 / iTClamp / A06 已吸收项目不进入本轮新提取。**

| 项目 | 本轮角色 | 允许 | 不允许 |
|:---|:---|:---|:---|
| A06_南驰 / iTClamp | Historical Regression only | 作为历史问题来源、作为回归测试参考 | 作为本轮 calibration / stress / holdout 项目、计入新资产覆盖数量、参与新规则归纳 |

原因：该项目已被 BIGDP2026.6 和 V2 前期多次吸收。继续作为主样本会导致系统围绕 iTClamp 过拟合，无法泛化到其他器械类型和 NB 反馈风格。

---

## 二、15–20 项目选择策略

### 项目结构

| 类型 | 数量 | 用途 |
|:---|:--:|:---|
| Calibration | 8–10 | 提炼规则、SOP、fixtures、gold labels |
| Stress | 4–5 | 测试资料缺失、endpoint 模糊、全文不可得、denominator 错误 |
| Holdout | 3–5 | 不参与规则归纳，只做最终验证 |
| Special Evidence | 0–2 | 专门补某一类缺口（PMCF、equivalence、SOTA accounting） |
| **总计** | **15–20** | |

### 选择原则

1. 优先选有 CER + SOTA + 文献检索 + NB feedback + final accepted version 的项目
2. 优先选不同器械类型（避免同一 domain 全进 calibration）
3. 优先选不同缺陷类型（避免只覆盖某几类 DC）
4. 优先选不同 NB 机构（避免过拟合某个 NB 的审核风格）
5. Holdout 项目不参与 calibration 规则归纳和 fixture 生成
6. 南驰 / iTClamp 不进入本轮新提取

### 校准项目最低要求

Calibration 8–10 个项目的分布要求：

| 要求 | 最低数量 |
|:---|:--:|
| 有完整 SOTA / search 记录 | ≥5 |
| 有全文或 PMID 数据表 | ≥5 |
| 有 NB feedback | ≥4 |
| 有 before/after CER 版本 | ≥3 |
| 有 denominator / endpoint 详细数据表 | ≥4 |

### Stress 项目选择标准

挑问题多的：文献少、全文缺失、endpoint 模糊、comparator 缺失、SOTA 数字混乱、NB feedback 多轮、IFU/RMF/GSPR 不一致。

### Holdout 项目选择标准

挑资料完整但不参与规则归纳的：有 IFU/RMF/GSPR/CER/SOTA，有 final accepted CER。

### Dataset Role Lock（角色锁定规则）

| 项目角色 | 能做什么 | 禁止什么 |
|:---|:---|:---|
| Calibration | 生成规则、fixtures、tests | 不能作为最终泛化证明 |
| Stress | 测试极端情况、缺失资料、模糊判断 | 不能作为主要规则来源 |
| Holdout | 最终验证 | 不能参与规则归纳、不能生成 fixtures |
| Historical Regression | 只做历史回归参考 | 不计入新资产覆盖 |
| Special Evidence | 专门补某一 DC 缺口 | 不用于其他 DC 的泛化规则 |

---

## 三、项目选择覆盖矩阵

创建 `PROJECT_SELECTION_COVERAGE_MATRIX.csv`，每个候选项目一行。字段：

```csv
project_id,project_name,device_type,NB_body_if_known,has_CER,has_SOTA,has_IFU,has_RMF,has_GSPR,has_literature_search,has_fulltext,has_NB_feedback,has_company_response,has_final_accepted_version,has_before_after,DC1_search,DC2_query,DC3_screening,DC4_pmid_trace,DC5_fulltext,DC6_endpoint,DC7_comparator,DC8_consistency,DC9_sota_accounting,DC10_denominator,DC11_writer,dataset_role,selection_reason,exclusion_reason
```

### DC 覆盖配额（Patch A 验收标准）

| 缺陷类 | 最低覆盖项目数 |
|:---|:--:|
| DC-1/2 检索召回和检索词 | ≥5 |
| DC-3 筛选规则 | ≥5 |
| DC-4 PMID 数据溯源 | ≥5 |
| DC-5 全文状态 | ≥5 |
| DC-6 endpoint 语义 | ≥6 |
| DC-7 comparator benchmark | ≥4 |
| DC-8/9 SOTA accounting / 上下文一致性 | ≥5 |
| DC-10 denominator/subgroup | ≥4 |
| DC-11 Writer before/after | ≥4 |

**Patch A 不以项目数量为唯一验收标准，而以 DC 覆盖配额为验收标准。**

---

## 四、提取任务：Batch B — 证据完整性

每个任务给出：目标 DC、参考锚点、输出 CSV 字段、最低数量、正例/负例提示。

### B1 检索审计 → DC-1, DC-2

**源文件夹：** `01_CER_SOURCE_PACKAGE/CLINICAL_EVIDENCE/`
**查找：** "search strategy", "PubMed", "Embase", "检索策略", "检索词", "query", "PRISMA"
**CLAUDE.md 规则（Line 148）：** Every search MUST document: exact PubMed query string, date, total hits, Humans filter, count after each exclusion.
**Defect Map引用：** DC-1 Line 16-17（query_string, database, date, total_hits, humans_filter）、DC-2 Line 33

**输出：** `B1_SEARCH_AUDIT.csv`

```
project_id, search_round, database, query_string, date_executed, total_hits, humans_filter_applied, humans_hits, dedup_hits, included_pmids, excluded_pmids
```

**最低：** ≥5 项目有完整检索记录。正例=含 query_string。负例=只有数量无检索词。

### B2 筛选决策 → DC-3

**源文件夹：** `01_CER_SOURCE_PACKAGE/CLINICAL_EVIDENCE/` 文献筛选表
**CLAUDE.md（Line 143）：** EXCLUDE: N<10 case reports, animal/cadaver/in-vitro.
**Defect Map DC-3 Line 50：** N<10→EXCLUDE, animal→EXCLUDE, time_unspecified→REWORK

**输出：** `B2_SCREENING.csv`

```
project_id, pmid, title, sample_size, decision, exclusion_reason, reason_code, date_range_start, date_range_end
```

**reason_code 枚举：** `N_LT_10 | ANIMAL | IN_VITRO | REVIEW | WRONG_POPULATION | NO_FULLTEXT | TIME_UNSPECIFIED | OTHER`

**最低：** ≥5 项目。≥5 个正确排除 N<10 案例。≥5 个正确排除动物/体外案例。

### B3 全文状态 → DC-5

**源文件夹：** `01_CER_SOURCE_PACKAGE/CLINICAL_EVIDENCE/` PDF 全文
**CLAUDE.md（Line 158）：** Mark each PMID: ✅ Full-text / ⚠️ Abstract only / ❌ Unobtainable.

**输出：** `B3_FULLTEXT_STATUS.csv`

```
project_id, pmid, fulltext_status, has_numerical_data, data_source
```

**fulltext_status 枚举：** `obtained | abstract_only | unobtainable`
**data_source 枚举：** `abstract | fulltext_table | fulltext_text | unknown`

**最低：** ≥5 项目，≥20 PMID。正例=obtained 且有数据来源标注。负例=abstract_only 却产生了数值型数据。

### B4 PMID 溯源 → DC-4

**已知精确 PMID（来自工程师反馈）：** PMID 31539432, PMID 32209132, PMID 30635996
**CLAUDE.md §Data Traceability（Line 152–160）：** Every data point MUST have source PMID. Abstract-verify required. Zero tolerance for orphan data.

**输出：** `B4_PMID_TRACE.csv`

```
project_id, data_point_description, data_point_value, source_pmid, data_found_in_abstract, data_found_in_fulltext, source_sentence_or_location, confidence
```

**最低：** ≥5 项目，≥20 数据点。正例=数据在 abstract 中可找到且有 source sentence。负例=PMID 中找不到声称的数据。

### B5 分母标注 → DC-10

**已知精确案例：** PMID 30635996, N=216 total, CMF 子集 n=80. "87.5% (70/80), N=216" — denominator mismatch.
**Defect Map DC-10 Line 169：** numerator, denominator, population (total/subgroup). Mismatch → BLOCKED.

**输出：** `B5_DENOMINATOR.csv`

```
project_id, pmid, endpoint, numerator, denominator, population_label, study_reported_total_n, denominator_matches_study
```

**最低：** ≥4 项目，≥3 个分母混用负例，≥3 个正确分母正例。

---

## 五、提取任务：Batch C — 专家语义可靠性

### C1 Endpoint 语义分类 → DC-6

**已知缺陷：** "装置弃用→直接压迫/止血带" 被标为 AE。应为 treatment_failure 或 inadequate_hemostasis。
**CLAUDE.md §Endpoint Classification（Line 164–167）：**
- `adverse_event` = Device-related untoward medical event (ISO 14155)
- `treatment_failure` = Clinical decision to abandon device. NOT an AE.
- `inadequate_hemostasis` = Efficacy endpoint, not safety AE.

**输出：** `C1_ENDPOINT_SEMANTICS.csv`

```
project_id, endpoint_name, endpoint_value, correct_semantic_class, common_misclassification, classification_basis, source_evidence
```

**semantic_class 枚举：** `adverse_event | serious_adverse_event | treatment_failure | rescue_therapy_switch | inadequate_hemostasis | device_deficiency | procedural_outcome | other`

**classification_basis 枚举：** `ISO_14155 | NB_comment | engineer_correction | expert_judgment | heuristic`

**最低：** ≥6 项目，≥20 endpoint 标注。≥3 个 treatment_failure 或 inadequate_hemostasis 案例。

### C2 比较器 Benchmark → DC-7

**已知缺陷：** 止血带/缝线/缝钉有数据但 benchmark 表缺失。有数据无 CI。
**CLAUDE.md §Statistical Consistency（Line 170）：** Wilson 95% CI for EVERY reportable rate. No bare percentages.

**输出：** `C2_COMPARATOR_BENCHMARK.csv`

```
project_id, comparator_name, endpoint, point_estimate, ci_lower, ci_upper, sample_size, source_pmid, directness, in_original_cer
```

**最低：** ≥4 项目，≥10 比较器数据点。正例=有 CI + source PMID。负例=有数值无 CI、无 source。

### C3 Claim-Evidence 支撑 → Semantic Support

**输出：** `C3_CLAIM_EVIDENCE_SUPPORT.csv`

```
project_id, claim_id, claim_text, evidence_pmid, evidence_support_type, endpoint_match, population_match, support_strength, n_evidence_items
```

**evidence_support_type 枚举：** `direct | indirect | equivalent | manufacturer | PMS`
**最低：** ≥5 项目，≥15 claim-evidence pairs。

---

## 六、提取任务：Batch D — 验证与 Writer QA

### D1 SOTA Accounting → DC-8, DC-9

**已知缺陷：** "13 articles" vs "14 search groups / 1000 records / 183 fulltext / 219 evidence".
**Defect Map DC-9 Line 152：** article_count = screening included_count; evidence_count = appraisal appraised_count.

**输出：** `D1_SOTA_ACCOUNTING.csv`

```
project_id, section, search_groups, raw_records, dedup_records, screened_records, fulltext_assessed, included_studies, evidence_items, numbers_consistent
```

**最低：** ≥5 项目有 SOTA 数字。≥2 项目有数字不一致案例（负例）。

### D2 跨章节一致性 → DC-8

**已知缺陷：** 前文 4 个安全性终点 → 后文变成 1 个 "1.7% 皮肤损伤"。
**输出：** CER 原文文件 + `D2_CROSS_CHAPTER_NOTES.md`

```
project_id, cer_file, section, endpoint_definition_count, endpoint_usage_count, consistent
```

**最低：** ≥5 项目有完整 CER 文件。≥2 项目有前后不一致案例。

### D3 Writer 输出 → DC-11

**源文件夹：** `03_COMPANY_RESPONSES/` before/after + `01_CER_SOURCE_PACKAGE/CER/` 原始版
**输出：** `D3_WRITER_MANIFEST.csv` + 原文文件

```
project_id, version, cer_file_path, has_writer_issues, known_issues
```

**version 枚举：** `draft | submitted | NB_round1 | NB_round2 | NB_accepted`
**最低：** ≥4 项目有 before/after CER。≥2 项目有 ≥2 轮 NB revision。

### D4 验证项目 → Real Project Validation

**从 Holdout 项目中选 1–2 个。** 如果 D4 选用 calibration 项目，必须标记 `validation_type = calibration_replay`，不能作为 full holdout validation。
**输出：** `D4_VALIDATION_PROJECT/` 完整文件 + `D4_READINESS.md`

---

## 七、法规资源：Rule Extraction Targets

法规文件不只是"引用资料"，必须进入 rule extraction。创建 `REGULATORY_RULE_EXTRACTION_TARGETS.csv`：

```
document_name, file_path, clause_or_section, regulatory_topic, target_dc, target_batch, target_rule_type, expected_runtime_use, expected_writer_constraint, required_or_optional
```

| 文件 | target_dc | target_rule_type |
|:---|:---|:---|
| MDR Annex XIV | DC-4, DC-11 | clinical evaluation evidence chain |
| MDCG 2020-5 Equivalence | Claim-evidence | equivalence limitation rules |
| CEAR | Final validation | NB assessment checklist |
| MDCG 2020-10-1 Safety Reporting | DC-6 | AE/incident classification |
| ISO 14155 (via MDR references) | DC-6 | endpoint taxonomy |

**最低：** 6 个核心法规文件。`required_or_optional = required` 的必须就位。

---

## 八、Asset-to-Absorption Contract

每份提取物必须声明以下吸收属性。创建 `ASSET_ABSORPTION_CONTRACT.csv`：

```
extract_id, target_batch, target_dc, absorption_type, closure_level_supported, score_area, can_train_rules, can_validate_holdout, writer_allowed, locked_boundary
```

| 字段 | 枚举值 |
|:---|:---|
| target_batch | B / C / D / Final |
| target_dc | DC-1 ~ DC-11 |
| absorption_type | rule / SOP / fixture / semantic_test / runtime_validator / writer_QA / validation_asset |
| closure_level_supported | FULLY_CLOSED / DERIVED_VALIDATION / HEURISTIC_ONLY / SYNTHETIC_ONLY |
| score_area | 12 个评分维度之一 |
| can_train_rules | yes / no |
| can_validate_holdout | yes / no |
| writer_allowed | yes / no |
| locked_boundary | open_input / calibration_only / validation_only / locked_no_writer / holdout_only |

**核心原则：每条提取数据必须带着吸收目的出生。没有 absorption_type 和 target_dc 的提取物不是资产，只是资料堆。**

---

## 九、提取质量验收标准

每个 CSV 必须通过以下质量门：

| 检查项 | 要求 |
|:---|:---|
| source_file_path | 不得为空 |
| source_quote_or_anchor | gold / expert / source_verified 级别不得为空 |
| evidence_level | 必填 |
| dataset_role | 必填（calibration / stress / holdout / historical） |
| locked_status | 必填 |
| writer_access_allowed | 必填 |
| confidence | 必填（high / medium / low / unverifiable） |
| DC mapping | 必填 |
| score_area mapping | 必填 |
| duplicate check | 同一 PMID / endpoint / claim 不得重复且不得自相矛盾 |
| holdout contamination check | holdout 项目数据不得出现在 rule source 中 |

**Patch A 输出不可直接进入代码。必须先通过质量门验证。**

---

## 十、吸收就绪判定

Patch A 完成后，创建 `PATCH_A_ABSORPTION_READINESS_REPORT.md`。必须回答：

1. 哪些 DC 已有 gold / expert / source_verified 资产？
2. 哪些 DC 只有 heuristic / report-derived 资产？
3. 哪些 DC 仍 NOT_FOUND？
4. 南驰 / iTClamp 是否未被计入本轮 calibration / holdout 数量？
5. 是否达到 DC 覆盖配额？
6. 是否有 holdout contamination？
7. 哪些 CSV 可直接生成 fixtures？
8. 哪些 CSV 可直接生成 semantic tests？
9. 哪些资产支持 Path A FULLY_CLOSED？
10. 哪些资产只能支持 Path B capped score？
11. 最终 Path A 还是 Path B？
12. 是否 READY_FOR_CLAUDE_CODE_ABSORPTION？

---

## 十一、输出目录结构

```
BIGDP2026_6V2/assets/
├── PROJECT_SELECTION_COVERAGE_MATRIX.csv
├── ASSET_ABSORPTION_CONTRACT.csv
├── REGULATORY_RULE_EXTRACTION_TARGETS.csv
├── PATCH_A_ABSORPTION_READINESS_REPORT.md
├── batch_B/
│   ├── B1_search_audit/
│   ├── B2_screening/
│   ├── B3_fulltext_status/
│   ├── B4_pmid_trace/
│   └── B5_denominator/
├── batch_C/
│   ├── C1_endpoint_semantics/
│   ├── C2_comparator_benchmark/
│   └── C3_claim_evidence/
├── batch_D/
│   ├── D1_sota_accounting/
│   ├── D2_cer_originals/
│   ├── D3_writer_outputs/
│   ├── D4_validation_project/
│   └── NB_feedback_excerpts/
└── regulatory/
```

---

## 十二、提取后流程

1. Owner 完成 15–20 项目提取 → 文件放入 `assets/` 目录
2. Controller 运行质量门验证（Section 九的 11 项检查）
3. Controller 填写 `ASSET_ABSORPTION_CONTRACT.csv`
4. Controller 更新 `ASSET_READINESS_REGISTER.csv` 和 `VALIDATION_PATH_DECISION.md`
5. Controller 生成 `PATCH_A_ABSORPTION_READINESS_REPORT.md`
6. 如 READY_FOR_CLAUDE_CODE_ABSORPTION → Claude Code 吸收 Batch B → C → D
7. 如 NOT_READY → 精确指出哪个 DC 的覆盖配额未达、哪个 CSV 质量门未过
