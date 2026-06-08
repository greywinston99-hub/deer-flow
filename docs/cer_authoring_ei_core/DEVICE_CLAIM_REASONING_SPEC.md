# DEVICE CLAIM REASONING SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## 一、声明分解（Claim Decomposition）

每个 CER 声明从 claim_decomposition（V1 state）消费。Claim Reasoning 验证每个声明是否有充分的证据支撑。

---

## 二、Required Source Profile per Claim Type（Default Baselines）

⚠️ **以下为默认基线。** 可通过 device_class / risk_level / intended_use / available_data_profile 覆盖，所有覆盖必须记录在 reasoning_audit_ledger。

每种 claim_type 定义最低证据要求（required_source_profile）：

| Claim Type | 最低 source_type | 最低数量 | 最低 quality_tier | 可否等效设备 |
|---|---|---|---|---|
| **safety_clinical** | subject_device_clinical | ≥1 | acceptable+ | 否 |
| **safety_post_market** | subject_device_pms | ≥1 | acceptable | 否 |
| **performance_technical** | subject_device_test | ≥1 | acceptable+ | 否 |
| **performance_clinical** | subject_device_clinical | ≥1 | acceptable+ | 条件性* |
| **sota_benchmark** | 任意 ADMISSIBLE for SOTA | ≥3 | acceptable | 是 |
| **risk_context** | 任意 ADMISSIBLE for Risk | ≥1 | marginal+ | 是 |
| **benefit_risk_positive** | subject_device_clinical + pms | ≥2 | acceptable+ | 否 |
| **design_safety** | subject_device_risk + subject_device_test | ≥1 | acceptable | 否 |
| **usability** | subject_device_ifu + 任意 usability data | ≥1 | marginal+ | 条件性 |
| **material_biocompatibility** | subject_device_test | ≥1 | acceptable+ | 否 |

*performance_clinical 可用等效设备仅当 equivalence rationale 成立且性能指标在 equivalence scope 内。

### 2.1 Source Profile Override Rules

以下条件可覆盖默认 required_source_profile。所有覆盖必须记录在 reasoning_audit_ledger 且为确定性规则（非 LLM 决定）。

| Override Trigger | 覆盖动作 | 示例 |
|---|---|---|
| **device_class = III** (implantable) | UPGRADE safety_clinical min count to ≥2 | 植入物需要更多安全性证据 |
| **risk_level = high** | UPGRADE min quality_tier to good+ | 高风险设备需更高质量证据 |
| **intended_use = pediatric** | ADD population requirement (pediatric data required) | 儿科适应症需儿科人群数据 |
| **available_data_profile = limited** | DOWNGRADE required count（记录为 gap） | 罕见病设备可能仅有少量数据 |
| **well_established_technology** | ALLOW literature_path alternative (Annex X 1.1b) | SOTA 文献可替代部分临床研究 |

**覆盖记录格式**（入 reasoning_audit_ledger）：
```text
override_entry:
  claim_id: CLAIM-###
  override_trigger: device_class=III | risk_level=high | intended_use=pediatric | available_data_profile=limited
  original_profile: {...}
  overridden_profile: {...}
  override_rationale: str
  audit_entry_id: AUD-###
```

---

## 三、声明推理四步骤

```text
Step 1: Claim Decomposition
  claim_id → claim_type → required_source_profile

Step 2: Evidence Matching
  从 evidence_registry 匹配 claim_type 的可采信证据
  → matching_evidence: [EVID-###]
  → missing_evidence: 与 required_source_profile 的差距

Step 3: Support Level Determination
  评估 matching_evidence 是否满足 required_source_profile
  → claim_support_level: STRONG / MODERATE / WEAK / INSUFFICIENT

Step 4: Conclusion Boundary
  claim_support_level → max_conclusion_strength
  → writer_allowed_statements
```

---

## 四、Claim Support Level 判定

### 4.1 STRONG Support

| 条件 |
|---|
| 满足 required_source_profile |
| ≥2 subject device evidence items with quality_tier ≥ good |
| 方向一致（无 DIRECTIONAL 冲突） |
| 无 CRITICAL 冲突 |
| G42 PASS |

### 4.2 MODERATE Support

| 条件 |
|---|
| 满足 required_source_profile |
| ≥1 subject device evidence with quality_tier ≥ acceptable |
| 方向一致 |
| 无 CRITICAL 冲突 |

### 4.3 WEAK Support

| 条件 |
|---|
| 部分满足 required_source_profile（如缺少某种 source_type） |
| 或 evidence quality_tier = marginal |
| 或有 HIGH 冲突 |
| 或仅有 indirect/equivalence evidence |

### 4.4 INSUFFICIENT Support

| 条件 |
|---|
| 完全不满足 required_source_profile |
| 或全部 evidence quality_tier ≤ marginal |
| 或存在未解决的 CRITICAL 冲突 |
| 或全是 low-confidence facts |

---

## 五、Missing Evidence Gap 识别

对比 required_source_profile 和 available_evidence，识别缺失：

| 缺失类型 | 触发条件 | 对应 absence_of_evidence 类别 |
|---|---|---|
| missing_source_type | required_source_profile 中要求的 source_type 无对应证据 | not_searched / searched_not_found |
| insufficient_count | 证据数量 < required count | 按缺失端点处理 |
| insufficient_quality | 全部证据 quality_tier < required | found_but_low_quality |
| indirect_only | 仅有 indirect/equivalence 证据，无 subject device | found_but_indirect |
| missing_endpoint_data | 有 evidence 但缺少特定端点数据 | missing_endpoint |

---

## 六、输出

### 6.1 claim_support_matrix

```text
per claim:
  claim_id: str
  claim_type: str
  required_source_profile: dict
  matching_evidence_ids: [str]
  matching_evidence_count: int
  missing_evidence_gaps: [{gap_type, description, absence_category}]
  claim_support_level: str       # STRONG / MODERATE / WEAK / INSUFFICIENT
  max_conclusion_strength: str   # STRONG / MODERATE / CAUTIOUS / INSUFFICIENT
  quantitative_allowed: bool
```

### 6.2 writer_conclusion_constraints

```text
per claim:
  allowed_language_strength: str
  forbidden_phrases: [str]
  required_caveats: [str]
  quantitative_allowed: bool
```

---

## 七、禁止

- ❌ 降低 required_source_profile 以匹配现有证据
- ❌ 将 indirect evidence 计入 subject device count
- ❌ 在 evidence 不满足 required_source_profile 时标记 STRONG
- ❌ 忽略 missing_evidence_gaps
- ❌ 让 LLM 决定 claim_support_level

---

*CCD 签发：2026-05-12*
