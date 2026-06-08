# CLINICAL FACT LAYER — FINAL SCOPE

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## 一、Fact Layer 负责什么

临床事实提取层从已解析的文档内容（文本 + 表格）和外部临床数据库记录中，提取结构化、源锚定的临床数据点。

### 核心职责

| 职责 | 说明 |
|---|---|
| 数据提取 | 从 PDF/DOCX/OCR 文本和表格中提取数值、端点、人群、统计量 |
| 源锚定 | 每个 fact 追溯到源文档的页码、表格、文本摘录 |
| 置信度标注 | 标注提取方式（direct_text/table_cell/LLM_inferred/OCR_recovered） |
| 双语处理 | 保留原始语言摘录，标签归一化到英文 |
| 端点映射 | 将提取的原始端点标签映射到标准 endpoint_family（6 维度匹配） |
| 临床源适配 | 将 ClinicalTrials.gov 等外部数据库记录转换为 fact |

### Fact Table 完整 Schema

```text
clinical_evidence_fact_table:
  fact_id: FACT-###
  evidence_id: EVID-###
  candidate_claim_ids: [CLAIM-###]  (nullable at extraction)
  endpoint_family: safety / effectiveness / hemodynamic / device_integrity /
                   quality_of_life / biomarker / usability / post_market
  endpoint_label: 人类可读的端点名称
  value_type: rate / mean / median / OR / RR / HR / count / qualitative
  value_numeric: 提取的数值
  value_unit: % / mmHg / mL / events / score
  population_n: 该端点的样本量
  follow_up: 随访时长
  CI_lower / CI_upper: 置信区间
  p_value: 统计显著性
  comparator: 对照组描述
  source_page: 源文档页码
  source_table: 源文档表格引用
  source_excerpt: 提取文本片段
  original_excerpt: 非英语文档的源语言摘录
  source_language: 源文档语言代码
  extraction_method: direct_text / table_cell / OCR_recovered / LLM_inferred
  extraction_confidence: high / medium / low / OCR_uncertain
  normalizer_status: raw / normalized / needs_human_review
  translation_flags: TRANSLATION_NEEDED (if applicable)
```

### 置信度门控

置信度 = min(extraction_method_confidence, 四个 validator 的最低分)

| 提取方式 | 方法置信度 | 全部 validator 通过 | ≥1 validator 失败 |
|---|---|---|---|
| direct_text | high | high | medium |
| table_cell | high | high | medium |
| LLM_inferred | medium | medium | low |
| OCR_recovered | low | low | low |

四个 validator：numeric_sanity, unit_consistency, denominator_numerator_check, source_excerpt_cross_check

## 二、Fact Layer 不负责什么

| 不负责 | 属于哪层 | 原因 |
|---|---|---|
| 评价证据质量 | Evidence Appraisal (Layer 3) | Fact 是数据点，不是质量判断 |
| 判断监管可采信性 | Intelligence Core (Layer 4) | 可采信性基于 source_type + device_relationship |
| 合成结论 | Intelligence Core (Layer 4) | Fact 是原子数据，不聚合 |
| 替代证据注册 | Evidence Appraisal (Layer 3) | fact 补充 evidence，不替代 |
| 决定证据角色 | Layer 3 + Layer 4 | fact_role_cap 是信号，最终角色多层决定 |
| 生成 CER 文本 | Writer (Layer 5) | Fact 提供数据锚点，Writer 生成文本 |

## 三、Fact → Intelligence Core 接口

Fact Layer 输出以下数据供 Intelligence Core 消费：

| 输出 | 消费模块 | 用途 |
|---|---|---|
| clinical_evidence_fact_table | Evidence Scoring | data_quality + fact_confidence 因子 |
| clinical_evidence_fact_table | Claim Reasoning | 声明支撑的事实基础 |
| clinical_evidence_fact_table | SOTA Benchmark | 基准计算的数据源 |
| clinical_evidence_fact_table | BR Reasoning | 受益和风险量化 |
| clinical_evidence_fact_table | PMCF Gap | gap 触发条件判断 |
| semantic_endpoint_mapping_table | Claim Reasoning | 端点链接到声明 |
| evidence_conflict_report | Scoring + Claim Reasoning | 冲突对评分和结论的影响 |
| human_review_queue | Human Review Packet | 低置信度事实审查需求 |

**关键约束**：Intelligence Core 不直接消费 `clinical_evidence_fact_table`。所有消费必须通过 `evidence_registry` 中与 fact 关联后的 evidence 对象。

## 四、已知局限

| 局限 | 影响 | 缓解 |
|---|---|---|
| OCR 不确定性 | OCR_recovered → low confidence → background only | OCR 质量信号 + human review queue |
| 非英语文档 | 源语言摘录保留，标签归一化 | TRANSLATION_NEEDED，不自动翻译 |
| 非标准端点标签 | 语义映射可能失败或低置信度 | 6 维度匹配 + unmatched → human review |
| 缺失全文 | 仅摘要时无法提取表格和详细数据 | LLM_inferred → medium confidence |
| 表格解析错误 | Camelot/PyMuPDF 可能错误解析 | table_cell 有 cross-check validator |
| CT.gov 无结果 | NO_RESULTS_AVAILABLE → 不产生 fact | 记录保留为背景 evidence |

## 五、Fact 不被绕过的前提条件

1. `clinical_evidence_fact_table` 必须在 `evidence_registry` 构建后、`evidence_scoring` 运行前完成
2. 每条 fact 必须链接到一条 evidence（`fact.evidence_id` 不可为空）
3. Fact 提取的确定性规则不得被 LLM 覆盖
4. Fact 置信度门控（method + validators）在提取时完成，不被下游事后调整
5. Bilingual fact 的 `original_excerpt` 必须保留，不被翻译替代

---

*CCD 签发：2026-05-12*
