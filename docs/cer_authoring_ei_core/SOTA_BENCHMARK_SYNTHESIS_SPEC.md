# SOTA BENCHMARK SYNTHESIS SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## ⚠️ 独立置信度

**SOTA 合成有独立的置信度 `benchmark_confidence`。** 不与 BR 或 PMCF 共享通用评分。

---

## 一、输入

- 被标记为 ADMISSIBLE for SOTA Context 的 evidence（来自 Admissibility Spec）
- 其关联的 clinical_evidence_fact_table（通过 evidence_id）
- semantic_endpoint_mapping_table（端点聚类）

---

## 二、合成步骤

```text
Step 0: Comparability Check（前置条件）
  对每个候选 study 评估 5 个维度的可比性：
    0a. endpoint_definition — same measurement method or equivalent
    0b. timepoint — within ±20% of median follow-up across studies
    0c. population — same target population or explicitly documented rationale
    0d. procedure/anatomy context — not mixing different approaches
    0e. device_relationship — subject + equivalent + similar only, NOT competitor-only
  任一维度不通过 → study excluded from benchmark → listed in excluded_studies

Step 1: Endpoint Clustering
  按 endpoint_cluster_id 分组（复用 V3 语义端点映射结果），仅包含 Step 0 通过的可比 studies

Step 2: Synthesis Method Selection
  按 EVIDENCE_SYNTHESIS_METHOD_POLICY：
    comparable_studies ≥ 3 → Benchmark Synthesis
    comparable_studies ≥ 1 → Narrative Synthesis
    comparable_studies = 0 → No Synthesis（insufficient_data）

Step 3: Benchmark Calculation（仅 Benchmark Synthesis）
  range = [min, max]
  median = 中位数
  mean = 均值
  IQR = [Q1, Q3]

Step 4: Subject Device Positioning
  subject_device_value vs benchmark_range

Step 5: Gap Quantification
  如有差距：量化
```

---

## 三、Benchmark Confidence 判定

| 等级 | 条件 |
|---|---|
| **high** | ≥5 个高质量可比研究、同质端点、低异质性（IQR/median < 0.3） |
| **medium** | 3-4 个可比研究、或存在一定异质性（0.3 ≤ IQR/median < 0.5） |
| **low** | <3 个可比研究、或仅相似/竞品数据、或 IQR/median ≥ 0.5 |
| **insufficient_data** | 无可比数据（<1 or all excluded） |

---

## 四、输出

### 4.1 sota_benchmark_table

```text
per endpoint_cluster:
  endpoint_cluster_id: str
  endpoint_family: str
  synthesis_method: str           # benchmark / narrative / none
  total_candidate_studies: int    # Step 0 前的候选 study 总数
  excluded_studies: [{study_id, exclusion_reason, failed_dimensions}]
  comparable_studies: int         # Step 0 后的可比 study 数
  comparability_assessment: {endpoint_definition: pass/fail, timepoint: pass/fail, population: pass/fail, procedure_context: pass/fail, device_relationship: pass/fail}
  data_source_types: [str]
  benchmark_range: {min, max}|null
  benchmark_median: float|null
  benchmark_mean: float|null
  benchmark_iqr: {q1, q3}|null
  heterogeneity_ratio: float|null # IQR/median
  subject_device_value: float|null
  subject_device_position: str|null # above/within/below/unknown
  gap_description: str|null
  benchmark_confidence: str       # high / medium / low / insufficient_data
  nr_flags: [str]                 # Needs Review
  data_limitations: [str]         # 如「仅竞品数据」「样本量小」
```

### 4.2 sota_narrative

结构化叙述（不是自由文本），基于 sota_benchmark_table 生成。每个 endpoint_cluster 一段叙述，包含：
- 基准范围描述
- Subject device 位置
- 差距描述
- 置信度声明
- 数据限制声明

---

## 五、特殊规则

### 5.1 数据不足

- <3 个可比数据点 → benchmark_confidence = insufficient_data
- 不计算 range/median/IQR
- narrative 描述为「当前数据不足以建立可靠的 SOTA 基准」
- NR 标记

### 5.2 仅有相似/竞品数据

- 可构建「背景基准」
- benchmark_confidence 上限 = medium
- 必须标注「基准基于非 subject device 数据」
- 每个数据点标注 device_relationship

### 5.3 仅有 subject device 数据

- 如 subject device 有多篇研究 → 可构建 subject device 自身基准
- benchmark_confidence 上限 = medium（缺少外部参照）
- 标注为「subject device only benchmark」

---

## 六、与 Evidence Synthesis Method Policy 的关系

本 spec 消费 `EVIDENCE_SYNTHESIS_METHOD_POLICY.md` 来决定每个 cluster 使用哪种合成方法。SOTA 特有的规则：
- 合成方法选择后，SOTA 额外计算 subject_device_position 和 gap
- Narrative synthesis 结果仍需输出到 sota_benchmark_table（但不含 range/median/IQR）

---

## 七、禁止

- ❌ 在 <3 个可比数据点时声称基准可靠
- ❌ 将竞品数据基准当作 subject device 的临床标准
- ❌ 在 heterogeneity 过高时声称精确基准值
- ❌ 不标注数据来源限制
- ❌ 将 SOTA benchmark_confidence 用于 BR 或 PMCF

---

*CCD 签发：2026-05-12*
