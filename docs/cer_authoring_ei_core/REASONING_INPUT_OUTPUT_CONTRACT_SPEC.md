# REASONING INPUT/OUTPUT CONTRACT SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## 约束声明

**每个 Evidence Intelligence Core 的 spec 不自行发明输入输出 schema。所有跨层接口统一由此契约定义。**

违反此契约的 spec 必须重写，不得进入实现阶段。

---

## 一、从 V3-Core → Intelligence Core 的精确输入

### 1.1 clinical_evidence_fact_table

| 来源 | pipeline.py (V3-Core) |
|---|---|
| 消费方 | Evidence Scoring, Claim Reasoning, SOTA, BR, PMCF |
| 消费方式 | 通过 evidence_registry 间接消费，不直接读取 fact_table |

```text
关键字段（Intelligence Core 消费的字段）:
  fact_id: str           # FACT-###
  evidence_id: str       # EVID-###  → 链接到 evidence_registry
  endpoint_family: str   # safety / effectiveness / hemodynamic / ...
  endpoint_label: str    # 人类可读标签
  value_type: str        # rate / mean / median / OR / RR / HR / count / qualitative
  value_numeric: float   # 提取数值
  value_unit: str        # % / mmHg / mL / events / score
  population_n: int      # 样本量
  follow_up: str         # 随访时长
  CI_lower: float|null
  CI_upper: float|null
  p_value: float|null
  comparator: str|null   # 对照组描述
  extraction_method: str # direct_text / table_cell / OCR_recovered / LLM_inferred
  extraction_confidence: str  # high / medium / low / OCR_uncertain
  normalizer_status: str # raw / normalized / needs_human_review
  source_language: str|null
  translation_flags: str|null  # TRANSLATION_NEEDED
```

### 1.2 evidence_registry

| 来源 | pipeline.py (V2 + V3) |
|---|---|
| 消费方 | Evidence Scoring, Claim Reasoning, Admissibility |

```text
关键字段:
  evidence_id: str              # EVID-###
  source_type: str              # literature_pubmed_sota / subject_device_clinical_study / ...
  device_relationship: str      # subject / similar / competitor / previous_gen / unrelated
  comparability_band: str       # HIGH / MEDIUM / LOW / NOT_COMPARABLE
  comparability_score_raw: int  # 0-9
  allowed_claim_types: [str]    # safety_clinical, performance_clinical, ...
  evidence_role: str            # pivotal / supportive / background
  fact_role_cap: str|null       # pivotal_eligible / supportive / background (V3)
  g42_fact_signal: str|null     # V3 G42 信号
  study_design: str|null
  sample_size: int|null
  oxford_level: str|null
```

### 1.3 semantic_endpoint_mapping_table

| 来源 | pipeline.py (V3-Core) |
|---|---|
| 消费方 | Claim Reasoning, SOTA Benchmark |

```text
关键字段:
  fact_id: str               # FACT-###
  endpoint_family: str       # 映射后的标准 family
  mapping_confidence: str    # high / medium / low / unmatched
  endpoint_cluster_id: str   # CLUSTER-### 用于冲突检测和 SOTA 分组
  match_dimensions: [str]    # 哪些维度通过（endpoint_definition, measurement_method, ...）
  similarity_score: float    # 0-1
```

### 1.4 evidence_conflict_report

| 来源 | pipeline.py (V3-Core) |
|---|---|
| 消费方 | Evidence Scoring, Claim Reasoning, Human Review |

```text
关键字段:
  conflict_id: str        # CONFLICT-###
  endpoint_family: str
  evidence_ids: [str]     # 冲突涉及的多条证据
  conflict_type: str      # DIRECTIONAL / MAGNITUDE / STATISTICAL / POPULATION / TEMPORAL
  severity: str           # CRITICAL / HIGH / MEDIUM
  description: str
```

### 1.5 human_review_queue

| 来源 | pipeline.py (V3-Core) |
|---|---|
| 消费方 | Human Review Packet |

```text
关键字段:
  review_id: str       # HR-###
  fact_id: str         # FACT-###
  evidence_id: str     # EVID-###
  trigger_reason: str  # low_confidence / normalization_failure / translation_needed / conflict_flagged
  trigger_detail: str
  status: str          # pending | reviewed | promoted | dismissed
```

### 1.6 claim_decomposition

| 来源 | state.py (V1) |
|---|---|
| 消费方 | Claim Reasoning |

```text
关键字段:
  claim_id: str                   # CLAIM-###
  claim_type: str                 # safety_clinical / performance_clinical / ...
  claim_text: str
  required_source_profile: dict   # {min_source_type, min_evidence_count, min_quality_tier, allow_equivalent}
```

---

## 二、从 Intelligence Core → Writer 的精确输出

### 2.1 claim_support_matrix

| 输出格式 | Dict[claim_id → claim_support] |
|---|---|
| 消费方 | Writer (决定声明措辞强度) |

```text
claim_support 结构:
  claim_id: str
  support_level: str            # STRONG / MODERATE / CAUTIOUS / INSUFFICIENT
  max_conclusion_strength: str  # STRONG / MODERATE / CAUTIOUS / INSUFFICIENT
  supporting_evidence_ids: [str]
  missing_evidence_flags: [str] # not_searched / searched_not_found / found_but_low_quality / ...
  quantitative_allowed: bool    # 是否允许引用具体数值
```

### 2.2 sota_benchmark_table

| 输出格式 | List[endpoint_benchmark] |
|---|---|
| 消费方 | Writer (SOTA section) |

```text
endpoint_benchmark 结构:
  endpoint_cluster_id: str
  endpoint_family: str
  benchmark_range: {min: float, max: float}
  benchmark_median: float
  benchmark_iqr: {q1: float, q3: float}
  subject_device_value: float|null
  subject_device_position: str  # above_benchmark / within_benchmark / below_benchmark
  benchmark_confidence: str     # high / medium / low / insufficient_data
  data_source_count: int
  nr_flags: [str]               # Needs Review 标记
```

### 2.3 benefit_risk_conclusion

| 输出格式 | Dict |
|---|---|
| 消费方 | Writer (BR section) |

```text
结构:
  overall_judgment: str            # favorable / acceptable / borderline / unfavorable
  br_acceptability_confidence: str # high / medium / low / insufficient_evidence
  per_claim_benefit: [{claim_id, benefit_description, benefit_quantified, benefit_confidence}]
  per_claim_risk: [{claim_id, risk_description, risk_quantified, risk_confidence}]
  uncertainty_discounts: [str]     # 不确定性折价说明
```

### 2.4 pmcf_gap_register

| 输出格式 | List[pmcf_gap] |
|---|---|
| 消费方 | Writer (PMCF section) |

```text
pmcf_gap 结构:
  gap_id: str
  gap_type: str              # long_term_data / population_gap / rare_event / comparator_gap / real_world / design_evolution
  gap_severity: str          # critical / high / medium / low
  pmcf_objective: str
  pmcf_method_suggestion: str
  affected_claims: [str]
  trigger_condition: str     # 触发该 gap 的具体条件
```

### 2.5 cer_rmf_crosswalk_table

| 输出格式 | List[crosswalk] |
|---|---|
| 消费方 | CER + RMF 文档引用 |

```text
crosswalk 结构:
  crosswalk_id: str          # CW-###
  cer_claim_id: str          # CLAIM-###
  rmf_hazard_id: str|null    # HAZ-### (nullable if RMF data not available)
  link_type: str             # cer_supports_rmf / rmf_requires_cer
  link_nature: str           # traceability / consistency
  evidence_ids: [str]
  link_rationale: str
  domain_boundary_note: str  # "CER 评估 ≠ RMF 评估。此链接仅表示证据共用关系。"
```

### 2.6 reasoning_audit_ledger

| 输出格式 | List[audit_entry] |
|---|---|
| 消费方 | 审计附件 (not Writer) |

```text
audit_entry 结构:
  audit_entry_id: str          # AUD-###
  timestamp: str
  reasoning_step: str          # evidence_scoring / claim_reasoning / sota_synthesis / br_reasoning / pmcf_gap
  rule_applied: str            # rule_id
  input_artifacts: [str]       # FACT-###, EVID-###, etc.
  intermediate_result: dict
  output_artifacts: [str]
  confidence: str              # high / medium / low
  assumptions: [str]
  alternative_interpretations: [str]
```

### 2.7 human_review_packet

| 输出格式 | List[review_packet] |
|---|---|
| 消费方 | 人工审查工作流 |

```text
review_packet 结构:
  packet_id: str            # HRP-###
  tier: int                 # 2 | 3
  trigger: str              # critical_conflict / missing_essential_endpoint / equivalence_failed / conclusion_insufficient
  affected_claims: [str]
  evidence_summary: dict
  decision_options: [str]
  recommendation: str
  decision_required: bool   # true for Tier 3
  deadline_signal: str      # routine / urgent
```

### 2.8 writer_conclusion_constraints

| 输出格式 | Dict[claim_id → constraints] |
|---|---|
| 消费方 | Writer (硬约束，不可违反) |

```text
per-claim constraints 结构:
  claim_id: str
  allowed_language_strength: str  # STRONG / MODERATE / CAUTIOUS / INSUFFICIENT
  forbidden_phrases: [str]        # 禁止使用的措辞列表
  quantitative_allowed: bool      # 是否允许引用具体数值
  required_caveats: [str]         # 必须附加的限定语句
```

---

## 三、消费规则

1. Intelligence Core 组件只能读取「从 V3-Core 输入」中列出的字段
2. Intelligence Core 组件必须输出「到 Writer 输出」中列出的结构
3. 中间计算产物（如 evidence_strength_score）不直接暴露给 Writer，仅作为内部推理辅助
4. 每个输出结构的必填字段不得为 null（除非标注 nullable）
5. Writer 不得消费未在此契约中列出的 Intelligence Core 输出

---

*CCD 签发：2026-05-12*
