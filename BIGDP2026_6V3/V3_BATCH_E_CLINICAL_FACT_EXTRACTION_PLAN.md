# V3 — Batch E: Clinical Fact Extraction V2

**Target:** Upgrade 1
**Stages:** S5 (clinical data extraction), feeds S6 (benchmark) and S10 (BR/GSPR)
**Current Score:** 65 → Target: 75
**Execution Order:** E0 (eligibility) → E1 (extraction) — sequential within batch

---

## E0 — Clinical Data Eligibility Layer（NEW）

**法规问题：** 这篇文献能不能作为数据来源？全文有没有？数字来自哪里？endpoint 是否与 target claim 相关？

每条 clinical fact 在提取前必须先判定：

| Field | Values | Description |
|:---|:---|:---|
| source_eligibility | fulltext_verified / abstract_only / secondary_source / unavailable / unknown | 能否作为数据来源 |
| data_use_allowed | benchmark / BR / background_only / not_allowed | 该数据可用于 CER 的什么用途 |
| evidence_tier | tier1_direct / tier2_supporting / tier3_contextual / unacceptable | 证据层级 |
| clinical_use_limitation | none / population_mismatch / endpoint_mismatch / indirect / sample_size / fulltext_unverified / other | 临床使用限制 |

**集成：** clinical_fact_registry_v2 的每条记录包含上述 4 字段。G46 的 data-traceability condition 消费 source_eligibility。

## E1 — Clinical Fact Extraction V2

**当前问题：**

现有 clinical_fact_registry 主要覆盖：
- `X% (n/N)` 比例提取
- `mean ± SD` 提取
- `N=XXX` 样本量提取

不覆盖：
- HR / RR / OR / CI / p-value
- median / IQR
- Kaplan-Meier 数据
- subgroup 标注
- table / figure 数据
- follow-up duration
- adverse event severity
- source sentence / table anchor

## 2. Design

### 2.1 clinical_fact_registry_v2 schema

```
fact_id, pmid, source_type (abstract/fulltext_table/fulltext_text/figure),
source_sentence, fact_type (proportion/mean/median/hr/rr/or/ci/pvalue/km/survival/
followup/ae_count/ae_severity/other), value, ci_lower, ci_upper, numerator,
denominator, population_label, subgroup_label, endpoint_label, endpoint_class,
extraction_confidence, extraction_method (regex/llm/hybrid)
```

### 2.2 New parsers

| Parser | Input | Output |
|:---|:---|:---|
| Statistical fact parser | Abstract/fulltext text | HR, RR, OR, CI, p-value, median, IQR |
| Subgroup detector | Clinical text + fact registry | Subgroup-labeled facts |
| Table/figure extractor | PDF tables/figures via liteparse | Table-derived clinical facts |
| Follow-up duration parser | Methods/results text | Follow-up duration with unit |
| AE severity extractor | Safety results text | AE count + severity grade |

### 2.3 Integration

- clinical_fact_registry_v2 替代 clinical_fact_registry（保持向后兼容）
- G_DENOMINATOR 消费 registry_v2 中的 denominator + population_label + subgroup_label
- BENCHMARK_DERIVATION_TRACE 消费 registry_v2 中的 CI/range 数据
- BENEFIT_RISK_LEDGER 消费 registry_v2 中的 AE severity + follow-up

## 3. Required Assets

- B4 PMID trace (PARTIAL) — 用于验证提取准确性
- B5 denominator labels (PARTIAL) — 用于校准 subgroup detector
- 如果 PARTIAL → heuristic rules，max CLOSED_WITH_HEURISTIC_VALIDATION

## 4. Implementation Scope

**Can do now (no asset dependency):**
- Schema design + field definitions
- Statistical fact parser (regex-based)
- Table/figure extractor (liteparse integration)
- Follow-up duration parser
- Registry v2 node registration in graph

**Needs Tier 2 assets:**
- Subgroup detector calibration
- AE severity classifier calibration
- Extraction accuracy validation against gold data

## 5. Tests

**E0 Eligibility:**
- [ ] fulltext_verified → data_use_allowed = benchmark/BR
- [ ] abstract_only → data_use_allowed = background_only, clinical_use_limitation = fulltext_unverified
- [ ] secondary_source → data_use_allowed ≤ supporting, clinical_use_limitation = indirect
- [ ] unavailable → data_use_allowed = not_allowed

**E1 Extraction:**

| Test | Type |
|:---|:---|
| Proportion extraction (X%, n/N) | Regression |
| Mean ± SD extraction | Regression |
| HR extraction (e.g., "HR 0.72 (95% CI 0.58–0.89)") | New |
| RR extraction | New |
| OR extraction | New |
| CI extraction with Wilson score verification | New |
| p-value extraction | New |
| Median/IQR extraction | New |
| Subgroup label detection | New |
| Follow-up duration extraction | New |
| AE severity extraction | New |
| Table-derived fact from liteparse output | New |
| Orphan numeric fact (no PMID) → FAIL | New |
| Denominator mismatch → FAIL | Regression |

## 6. Validation Criteria

**Batch E PASS:**
- [ ] ≥50 clinical facts extracted from test fixtures
- [ ] ≥10 table-derived facts
- [ ] ≥10 CI/range/statistical facts
- [ ] ≥5 subgroup facts
- [ ] 0 orphan numeric facts (all facts have PMID)
- [ ] Denominator validator passes on all test fixtures
- [ ] All new + regression tests pass
- [ ] clinical_fact_registry_v2 wired into graph
- [ ] Backward compatibility: existing consumers still work

## 7. Score Impact

| Score Area | Current | Target |
|:---|:--:|:--:|
| Clinical fact source traceability | 6/12 (capped) | 8/12 |
| Denominator correctness | 5/10 (capped) | 7/10 |
| S5 Stage Score | 65 | 75 |
