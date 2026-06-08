# REGULATORY EVIDENCE ADMISSIBILITY SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## 一、基础原则

监管可采信性（Regulatory Admissibility）定义每种 `source_type` 对每种 `claim_type` 的可采信等级。基于 MDR 2017/745 Annex IX/X、MDCG 2020-5、MEDDEV 2.7/1 Rev.4。

**监管可采信性 ≠ 科学有效性。** 科学上有效的研究可能因 device_relationship=competitor 而在监管上不可采信。

---

## 二、Admissibility 等级

| 等级 | 含义 |
|---|---|
| **ADMISSIBLE** | 可独立支撑声明 |
| **CONDITIONAL** | 需满足特定条件才可支撑声明 |
| **CONTEXT_ONLY** | 仅提供临床上下文，不可直接支撑声明 |
| **NOT_ADMISSIBLE** | 不可用于此类声明 |

---

## 三、Source Type × Claim Type 可采信性矩阵

### 3.1 完整矩阵

| Source Type | Safety Claim | Performance Claim | SOTA Context | Risk Context |
|---|---|---|---|---|
| **subject_device_clinical_investigation** | ADMISSIBLE | ADMISSIBLE | ADMISSIBLE | ADMISSIBLE |
| **subject_device_clinical_data** | ADMISSIBLE | ADMISSIBLE | ADMISSIBLE | ADMISSIBLE |
| **subject_device_pms_pmcf** | ADMISSIBLE | CONDITIONAL¹ | ADMISSIBLE | ADMISSIBLE |
| **subject_device_psur** | ADMISSIBLE | CONTEXT_ONLY | ADMISSIBLE | ADMISSIBLE |
| **subject_device_vigilance** | ADMISSIBLE | NOT_ADMISSIBLE | CONTEXT_ONLY | ADMISSIBLE |
| **subject_device_test_performance** | NOT_ADMISSIBLE | ADMISSIBLE² | CONTEXT_ONLY | NOT_ADMISSIBLE |
| **subject_device_risk_management** | ADMISSIBLE | NOT_ADMISSIBLE | CONTEXT_ONLY | ADMISSIBLE |
| **subject_device_ifu** | CONTEXT_ONLY | CONTEXT_ONLY | CONTEXT_ONLY | CONTEXT_ONLY |
| **subject_device_gspr** | CONTEXT_ONLY | CONTEXT_ONLY | CONTEXT_ONLY | CONTEXT_ONLY |
| **equivalent_device_literature** | CONDITIONAL³ | CONDITIONAL³ | ADMISSIBLE | ADMISSIBLE |
| **similar_device_literature** | NOT_ADMISSIBLE | NOT_ADMISSIBLE | ADMISSIBLE | CONDITIONAL⁴ |
| **competitor_device_public** | NOT_ADMISSIBLE | NOT_ADMISSIBLE | ADMISSIBLE | NOT_ADMISSIBLE |
| **previous_generation_device** | CONDITIONAL⁵ | CONDITIONAL⁵ | ADMISSIBLE | CONDITIONAL |
| **literature_pubmed_sota** | NOT_ADMISSIBLE⁶ | NOT_ADMISSIBLE⁶ | ADMISSIBLE | CONDITIONAL⁷ |
| **public_registry_eudamed** | CONTEXT_ONLY | NOT_ADMISSIBLE | NOT_ADMISSIBLE | CONTEXT_ONLY |
| **public_registry_gudid_fda** | CONTEXT_ONLY | NOT_ADMISSIBLE | NOT_ADMISSIBLE | CONTEXT_ONLY |
| **manufacturer_cep_technical_file** | ADMISSIBLE | ADMISSIBLE | CONTEXT_ONLY | ADMISSIBLE |
| **other_manufacturer_data** | CONDITIONAL | CONDITIONAL | CONTEXT_ONLY | CONDITIONAL |

### 3.2 条件说明

¹ PMS/PMCF 数据支撑 performance claim 需有明确性能指标数据
² 台架/性能测试仅可支撑技术性能声明，不可支撑临床性能声明
³ 仅在 equivalence rationale 成立且声明在 equivalence scope 内
⁴ 仅可提供风险上下文（非独立风险估计）
⁵ 需有改进对比数据
⁶ 除非是 subject device 的已发表临床研究（则归入 subject_device 类）
⁷ 非 subject device 的 SOTA 文献可为风险提供一般背景

---

## 四、MDR 证据等级要求

### 4.1 Annex X 1.1(a) — 临床研究路径

适用于：可植入设备、III 类设备（非 well-established technology 豁免）

| 要求 | Admissibility 含义 |
|---|---|
| Subject device 临床研究 | 必须。subject_device_clinical_investigation = ADMISSIBLE for all claims |
| 等效设备数据 | 条件性。equivalent_device 仅在 equivalence 成立时 ADMISSIBLE |
| PMS/PMCF 数据 | 补充性。不可替代临床研究但可补充 |

### 4.2 Annex X 1.1(b) — 文献路径

适用于：well-established technology with sufficient clinical data in literature

| 要求 | Admissibility 含义 |
|---|---|
| 充分文献 | literature_pubmed_sota 中对 subject device 的研究 = ADMISSIBLE |
| 等效设备文献 | CONDITIONAL（需 equivalence 论证） |
| SOTA 文献 | 可构建 SOTA 基准（context only for claims） |

### 4.3 MDCG 2020-5 — Equivalence Guidance

| 要求 | Admissibility 含义 |
|---|---|
| 技术等效 | 必须。technical_comparability ≥ 2 |
| 生物等效 | 必须。biological_comparability ≥ 2 |
| 临床等效 | 必须。clinical_comparability ≥ 2 |
| Equivalence rationale 文档 | 必须。缺失 → equivalent_device → NOT_ADMISSIBLE |

---

## 五、PMCF 数据的特殊地位

| PMCF 数据类型 | Safety | Performance | SOTA |
|---|---|---|---|
| PMCF study 结果 | ADMISSIBLE | ADMISSIBLE | CONTEXT_ONLY |
| PMCF survey | CONDITIONAL | CONDITIONAL | CONTEXT_ONLY |
| PMCF registry | ADMISSIBLE | CONDITIONAL | ADMISSIBLE |
| PMCF literature review | CONTEXT_ONLY | CONTEXT_ONLY | ADMISSIBLE |

PMCF 数据可补充但不能替代 pre-market 临床研究数据（MDR Article 61(1)）。

---

## 六、缺失临床数据的后果

| 缺失数据类型 | Regulatory Impact |
|---|---|
| 无 subject device 临床研究 | 不可走 Annex X 1.1(a) 路径 → 需 well-established technology + 充分文献 |
| 无 subject device 安全性数据 | Safety claims → INSUFFICIENT → 不可声称安全 |
| 无 subject device 性能数据 | Performance claims → INSUFFICIENT → 不可声称有效 |
| 无等效论证文档 | Equivalent device → NOT_ADMISSIBLE |
| 仅竞品数据 | 仅可构建 SOTA 背景基准 |

---

## 七、Admissibility 判定流程

```text
输入: evidence (source_type + device_relationship) × claim_type
  ↓
Step 1: 查矩阵 → 基础 admissibility
  ↓
Step 2: 如 CONDITIONAL → 检查条件是否满足
  ↓
Step 3: 如 ADMISSIBLE 或 CONDITIONAL 满足 → 进入 evidence_scoring
  ↓
Step 4: 如 NOT_ADMISSIBLE 或 CONDITIONAL 不满足 → 排除出该声明证据池
  ↓
输出: admissibility_level + admissibility_rationale
```

---

## 八、禁止

- ❌ 将 CONTEXT_ONLY 证据用于直接支撑声明
- ❌ 在 equivalence 未验证时使用 equivalent_device 证据
- ❌ 将 competitor 数据用于 subject device 的安全性/性能声明
- ❌ 用 SOTA 通用文献声称 subject device 的安全性/有效性
- ❌ 在无 PMCF 明确性能数据时引用 PMCF 支撑性能声明

---

*CCD 签发：2026-05-12*
