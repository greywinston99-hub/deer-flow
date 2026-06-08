# CER/RMF Evidence Intelligence Core Upgrade — Master Plan

> CCD | 2026-05-12 | Planning Only — Do Not Implement

---

## 一、Context：为什么需要这次升级

### 已有资产（Built, Validated, 165 Tests）

| 层 | 内容 | 状态 |
|---|---|---|
| **V2 Evidence Chain** | 多源证据模型（16 source types）、设备关系分类、可比性评分、allowed-use 矩阵 | ✅ 已实现 → `RELEASE_EVIDENCE_PACK_INDEX.md` |
| **V3-Core Toolchain** | PDF/DOCX 解析、OCR 回退、MCP 适配器、临床事实提取、语义端点映射、CT.gov 映射、冲突检测、G42 信号桥接、Human Review Queue、Fact-Anchored Writer Claims | ✅ 已实现 → `V3_CORE_IMPLEMENTATION_PROOF_INDEX.md` |
| **Spiral Architecture** | 硬门控路由（PASS/REWORK/BLOCKED）、有界证据螺旋（3 轮）、Pre-Writer Readiness Gate、Controlled Compromise | ✅ 已实现 → `SPIRAL_ARCHITECTURE_IMPLEMENTATION_PROOF_INDEX.md` |

### 核心缺口

**V2 控制证据对象和 allowed-use。V3-Core 从文档中提取结构化临床事实。但两者之间缺少一个关键层：将事实转化为推理的「证据智能核心」。**

当前系统的推理路径是断裂的：
- `clinical_evidence_fact_table` 有数据，但没有规则决定哪些事实可以支撑哪些结论
- SOTA benchmark 有数据源，但没有合成方法论
- Benefit-risk 有框架，但没有从事实到 BR 结论的推理链
- PMCF gap 有触发条件，但没有推理闭环
- Writer 有事实锚定声明，但没有结论强度上限
- 缺失证据时系统沉默，而不是明确声明「无法得出结论」

### 本次升级目标

**构建统一的 CER/RMF Evidence Intelligence Core（证据智能核心层）**，位于数据提取层（V2+V3）和 Writer 输出层之间，负责：

```
临床事实 → 证据评分 → 监管可采信性 → 声明推理 → SOTA/BR/PMCF 推理 → Writer 结论边界
```

---

## 二、架构定位：五层模型 + I/O Contract

```text
Layer 5: WRITER OUTPUT（CER 文档）
  ↑ conclusion boundaries, fact-anchored claims

Layer 4: REASONING INTELLIGENCE ← 本次升级
  SOTA synthesis, BR reasoning, PMCF gap, claim reasoning,
  equivalence bridging, absence-of-evidence, conclusion strength
  ∥  REASONING_INPUT_OUTPUT_CONTRACT（精确接口定义）
  ∥  SCORING_CALIBRATION_AND_THRESHOLD_POLICY（评分校准策略）

Layer 3: EVIDENCE APPRAISAL ← 已有（V2 + V3 部分）
  evidence_registry, G42, fact_role_cap, conflict detection,
  allowed-use matrix, comparability scoring

Layer 2: DATA EXTRACTION ← 已有（V3-Core）
  clinical_evidence_fact_table, semantic endpoint mapping,
  CT.gov facts, document parsing, OCR

Layer 1: RAW INPUT ← 已有
  PDF, DOCX, PubMed, PMC, Europe PMC, ClinicalTrials.gov
```

**关键约束**：Layer 4 不能绕过 Layer 3。推理必须消费 evidence_registry 中已经过评价的证据，不能直接消费原始 fact_table。

### Reasoning Input/Output Contract（跨层接口契约）

每个 spec 不自行定义输入输出 schema。统一由 `REASONING_INPUT_OUTPUT_CONTRACT_SPEC.md` 定义：

**从 V3-Core → Intelligence Core 的精确输入**：
- `clinical_evidence_fact_table`（含 fact_id, evidence_id, endpoint_family, value_numeric, value_unit, CI, p_value, extraction_confidence, normalizer_status, conflict_status）
- `evidence_registry`（含 evidence_id, source_type, device_relationship, comparability_band, allowed_claim_types, evidence_role, fact_role_cap）
- `semantic_endpoint_mapping_table`（含 fact_id, endpoint_family, mapping_confidence, endpoint_cluster_id）
- `evidence_conflict_report`（含 conflict_id, evidence_ids, conflict_type, severity）
- `human_review_queue`（含 review_id, fact_id, trigger_reason, status）

**从 Intelligence Core → Writer 的精确输出**：
- `claim_support_matrix`（claim_id → support_level + max_conclusion_strength + supporting_evidence_ids）
- `sota_benchmark_table`（endpoint_cluster → benchmark_range + subject_device_position + benchmark_confidence）
- `benefit_risk_conclusion`（overall_judgment + br_acceptability_confidence + per_claim_benefit + per_claim_risk）
- `pmcf_gap_register`（gap_id → gap_type + severity + pmcf_objective + affected_claims）
- `cer_rmf_crosswalk_table`（crosswalk_id → cer_claim + rmf_hazard + link_type + evidence_ids）
- `reasoning_audit_ledger`（audit_entry_id → reasoning_step + rule_applied + input_artifacts + output_artifacts）
- `human_review_packet`（packet_id → trigger + tier + affected_claims + decision_options）
- `writer_conclusion_constraints`（per claim: allowed_language_strength + forbidden_phrases + quantitative_allowed_flag）

---

## 三、核心推理链（6 步 + 结构约束）

```
STEP 1: Facts → Evidence Strength（事实 → 证据强度）
  clinical_evidence_fact_table
  → evidence_scoring_model（多因子评分，非监管认证，内部推理辅助）
  → evidence_strength_score + evidence_quality_tier + score_calibration_status
  ⚠  评分是 provisional 的。阈值和校准策略见 SCORING_CALIBRATION_AND_THRESHOLD_POLICY。

STEP 2: Evidence Strength → Claim Support（证据强度 → 声明支撑）
  evidence_strength_score + regulatory_admissibility
  → device_claim_reasoning（声明所需证据画像）
  → claim_support_level + missing_evidence_gaps
  ⚠  缺失证据推理见 ABSENCE_OF_EVIDENCE_REASONING_SPEC（7 种类别，非仅 5 种）。

STEP 3: Claim Support → SOTA / BR / PMCF Reasoning（三项独立推理）
  claim_support_level
  → sota_benchmark_synthesis  → benchmark_confidence（独立）
  → benefit_risk_reasoning     → br_acceptability_confidence（独立）
  → pmcf_gap_reasoning         → pmcf_gap_severity（独立）
  ⚠  三者不使用同一个通用评分。各有独立的置信度/严重度输出。

STEP 4: Reasoning → Writer Conclusion Boundary（推理 → Writer 边界）
  synthesis_conclusions + br_conclusions + pmcf_conclusions
  → claim_conclusion_strength（结论强度上限）
  → writer_allowed_statements（Writer 允许的声明类型和强度）

STEP 5: Unresolved Uncertainty → Tiered Human Review（分层人工审查）
  Tier 1 (自动): low-confidence fact, normalization_failure, medium conflict
  Tier 2 (标记): HIGH conflict, missing non-critical endpoint, equivalence indirect
  Tier 3 (阻塞): CRITICAL conflict, missing essential endpoint, conclusion INSUFFICIENT
  → human_review_packet（结构化审查包，按 tier 组织）

STEP 6: CER ↔ RMF Cross-Linking（领域边界保留）
  CER safety claims → RMF hazard records（可追溯性）
  RMF risk controls → CER performance evidence（一致性）
  ⚠  交叉链接 = 可追溯性和一致性。不是合并 CER 和 RMF 判断。
  → cer_rmf_evidence_crosswalk
```

---

## 四、20 个输出文件的设计范围

### 文件 1：`CER_RMF_EVIDENCE_INTELLIGENCE_CORE_MASTER_PLAN.md`

**主计划文件**。汇总全部 20 个 spec 的架构关系、数据流、集成点。定义 Layer 4 的边界（什么归 Intelligence Core，什么归已有的 V2/V3）。定义各 spec 之间的依赖顺序。

### 文件 2：`CLINICAL_FACT_LAYER_FINAL_SCOPE.md`

**事实层的最终边界定义**。

必须明确：
- 事实层负责什么：从文档中提取结构化临床数据点（数值、端点、人群、统计量）
- 事实层不负责什么：不评价证据质量、不判断监管可采信性、不合成结论、不替代证据
- 事实层到推理层的接口：fact_table → evidence_scoring 的输入格式
- 事实层的已知局限：OCR 不确定性、非英语文档、非标准端点标签、缺失全文
- fact 不被绕过的前提条件

### 文件 3：`REGULATORY_EVIDENCE_ADMISSIBILITY_SPEC.md`

**监管可采信性规则**。基于 MDR Annex IX/X、MDCG 2020-5、MEDDEV 2.7/1 Rev.4。

定义每种 source_type 对每种 claim_type 的可采信性：

| Source Type | Safety Claim | Performance Claim | SOTA Context | Risk Context |
|---|---|---|---|---|
| subject_device_clinical_investigation | ADMISSIBLE | ADMISSIBLE | ADMISSIBLE | ADMISSIBLE |
| subject_device_pms_pmcf | ADMISSIBLE | CONDITIONAL | ADMISSIBLE | ADMISSIBLE |
| equivalent_device_literature | CONDITIONAL¹ | CONDITIONAL¹ | ADMISSIBLE | ADMISSIBLE |
| similar_device_literature | NOT_ADMISSIBLE | NOT_ADMISSIBLE | ADMISSIBLE | CONDITIONAL |
| competitor_device_public | NOT_ADMISSIBLE | NOT_ADMISSIBLE | ADMISSIBLE | NOT_ADMISSIBLE |
| literature_pubmed_sota | NOT_ADMISSIBLE² | NOT_ADMISSIBLE² | ADMISSIBLE | CONDITIONAL |

¹ 仅在 equivalence rationale 成立且 equivalence scope 内
² 除非是 subject device 的已发表临床研究

必须覆盖：
- 监管可采信性 ≠ 科学有效性
- MDR 对临床证据的等级要求（Annex X 1.1(a) vs 1.1(b) vs 1.2）
- equivalence 路径的特殊要求（MDCG 2020-5）
- PMCF 数据的特殊地位
- 缺失临床数据的后果

### 文件 4：`ABSENCE_OF_EVIDENCE_REASONING_SPEC.md`

**缺失证据的推理规则**。这是推理核心的中心组件——缺失证据推理贯穿所有下游模块。

核心原则：
- 「没有证据」≠「没有风险」
- 「没有证据」≠「安全有效」
- 缺失证据 → 结论降级，不是否定结论
- 缺失证据 ≠ 搜索失败（区分「未搜索」「搜索了未找到」「找到了但质量低」「找到了但不直接」「有记录无结果」「端点缺失」「冲突」）

七种缺失证据类别：

| 类别 | 定义 | 示例 | 结论影响 |
|---|---|---|---|
| **not_searched** | 未检索该源类型 | PMS 数据库未查询 | 不可声称全面检索 |
| **searched_not_found** | 检索了但零命中 | PubMed 检索零结果 | 可声称「未发现已发表文献」 |
| **found_but_low_quality** | 检索命中但质量不可接受 | OCR 低分的扫描文档 | 证据存在但不可采信 → background |
| **found_but_indirect** | 检索命中但不直接 | 相似设备数据但无 subject device 数据 | 有限使用（similar device rules） |
| **no_results** | 记录存在但无结果数据 | CT.gov 注册但 NO_RESULTS_AVAILABLE | 元数据可用但不产生 fact |
| **missing_endpoint** | 有 evidence 但缺特定端点 | 有安全性数据但无有效性数据 | 部分支持，缺失端点降级 |
| **conflicting** | 有多条证据但方向矛盾 | 研究 A 获益 vs 研究 B 危害 | CRITICAL 冲突 → 阻塞（非静默平均） |

每种场景的推理规则：
- 可以说什么（如「当前证据不包含长期安全性数据」）
- 不能说什么（如禁止写「长期安全性已确认」）
- 结论强度上限（如「不充分」或「谨慎」）
- PMCF 触发条件
- 是否进入 human review（按 tier）

### 文件 5：`EQUIVALENCE_SIMILARITY_BRIDGING_SPEC.md`

**等效/相似/竞品证据的桥接推理**。

在已有 `SIMILAR_COMPETITOR_EVIDENCE_SPEC.md`（V2）的基础上，增加推理层的桥接逻辑：

- **等效设备**：需要哪些证据才能声称等效（技术/生物/临床三要素）？等效论证失败时如何降级？
- **相似设备**：可以桥接到哪些类型的声明？桥接需要哪些额外前提？
- **竞品设备**：仅可用于 SOTA benchmark。什么情况下竞品数据可以暗示 subject device 的性能预期？
- **前代设备**：改进声明需要哪些对比数据？

桥接推理的结论强度上限：
- 等效设备证据 → 最高「中等」（除非有 subject device 直接证据补充）
- 相似设备证据 → 最高「谨慎」
- 竞品设备证据 → 不可用于 subject device 声明

### 文件 6：`EVIDENCE_SYNTHESIS_METHOD_POLICY.md`

**证据合成方法论策略**。

三种合成方法 + 适用条件：

| 方法 | 适用条件 | 输出 |
|---|---|---|
| **Narrative Synthesis**（叙述性合成） | 异质性过高、<3 个可比研究、非量化端点 | 结构化叙述 + 方向性结论 |
| **Benchmark Synthesis**（基准合成） | ≥3 个可比研究、同质端点、可量化 | 范围/分布 + 中位数/均值 + 异质性描述 |
| **No Synthesis**（不合成） | 仅有 1-2 个研究、严重冲突未解决、证据不可比 | 逐项列出 + 不聚合结论 |

**禁止**：
- 在冲突未解决时静默平均
- 在异质性过高时做 meta-analysis
- 对不同 source_type 的证据不做区分地混合

### 文件 7：`DEVICE_CLAIM_REASONING_SPEC.md`

**设备声明推理**。

定义每种 claim_type 需要的证据画像（required_source_profile）：

| Claim Type | 最低 source_type | 最低证据数 | 最低质量等级 | 可否用等效设备 |
|---|---|---|---|---|
| safety_clinical | subject_device_clinical | ≥1 | acceptable+ | 否 |
| performance_technical | subject_device_test | ≥1 | acceptable+ | 否 |
| performance_clinical | subject_device_clinical | ≥1 | acceptable+ | 条件性 |
| safety_post_market | subject_device_pms | ≥1 | acceptable | 否 |
| sota_benchmark | 任意 ADMISSIBLE | ≥3 | acceptable | 是 |
| benefit_risk_positive | subject_device_clinical + pms | ≥2 | acceptable+ | 否 |

声明推理步骤：
1. Claim decomposition → required_source_profile
2. Evidence matching → claim_support_level（强/中/弱/不充分）
3. Missing evidence → gap identification
4. Conclusion boundary → max_conclusion_strength

### 文件 8：`EVIDENCE_SCORING_MODEL_SPEC.md`

**证据评分模型**。

⚠️ **评分是 provisional 的**：这是内部推理辅助工具，不是外部监管认证。评分为下游模块（Claim Reasoning, SOTA, BR, PMCF）提供统一的证据质量信号，但每个下游模块有自己的置信度评估。

多因子评分（非单维度 Oxford LoE）：

| 因子 | 权重 | 评分范围 |
|---|---|---|
| Study Design（研究设计） | 25% | 0-4 |
| Device Relationship（设备关系） | 25% | 0-4 |
| Data Quality（数据质量：样本量、随访、统计） | 20% | 0-4 |
| Fact Confidence（事实置信度，来自 V3） | 15% | 0-4 |
| Conflict Status（冲突状态，来自 V3） | 10% | 0-4 |
| Regulatory Admissibility（监管可采信性） | 5% | 0-4 |

输出：
- `evidence_strength_score`（0-100 连续值）
- `evidence_quality_tier`（excellent / good / acceptable / marginal / insufficient）
- `score_calibration_status`（provisional / internally_calibrated / human_reviewed）
- `score_confidence`（评分本身的置信度——输入数据质量影响评分可靠性）
- `score_limitations`（评分限制说明）

**阈值和校准策略**见 `SCORING_CALIBRATION_AND_THRESHOLD_POLICY.md`（文件 20）。评分阈值的初始设定基于 MEDDEV 2.7/1 Rev.4 和 Oxford LoE 的理论映射，后续通过 calibration 项目数据校准。human_reviewed 状态仅在人工确认评分合理后设定。

### 文件 9：`SOTA_BENCHMARK_SYNTHESIS_SPEC.md`

**SOTA 基准合成**。

输入：被标记为 ADMISSIBLE for SOTA 的证据 + 其 clinical_evidence_fact_table

合成步骤：
1. 端点聚合：按 endpoint_cluster 分组（复用 V3 语义端点映射结果）
2. 异常值检测：排除不可比的研究（不同人群、过时技术）
3. 基准计算：对每个 cluster 计算范围（range）、中位数（median）、四分位距（IQR）
4. 设备定位：subject device 的性能数据在基准中的位置
5. 差距描述：如有差距，量化（如「低于基准中位数 12%」）

⚠️ **SOTA 有独立的置信度**：`benchmark_confidence`（high / medium / low / insufficient_data）。不与其他模块共享通用评分。

`benchmark_confidence` 判定：
- **high**：≥5 个高质量可比研究、同质端点、低异质性
- **medium**：3-4 个可比研究、或存在一定异质性
- **low**：<3 个可比研究、或仅相似/竞品数据
- **insufficient_data**：无可比数据

输出：
- `sota_benchmark_table`：端点的基准范围 + subject device 位置 + benchmark_confidence
- `sota_narrative`：结构化叙述（不是自由文本）
- `sota_gap_flags`：标记 subject device 显著偏离基准的端点
- 标记 NR（Needs Review）字段供人工确认

特殊规则：
- <3 个可比数据点 → 不计算基准，benchmark_confidence = insufficient_data
- 仅竞品/相似设备数据 → 可构建「背景基准」，benchmark_confidence 上限 medium，标注数据来源限制

### 文件 10：`BENEFIT_RISK_REASONING_SPEC.md`

**受益-风险推理**。

基于 ISO 14971、MDR Annex I 的结构化 BR 框架。

输入：
- claim_support_level（来自 Device Claim Reasoning）
- clinical_evidence_fact_table 中的安全性和有效性端点
- risk_management_file 中的风险控制措施

推理步骤：
1. **受益识别**：每个 performance/safety claim → 量化受益（如成功率 87.3%）
2. **风险识别**：每个 safety endpoint → 量化风险（如 SAE rate 2.1%）
3. **受益-风险权衡**：受益是否大于风险？
   - 受益明显 > 风险 → favorable
   - 受益 ≈ 风险 → balanced（需额外论证或限制适应症）
   - 受益 < 风险 → unfavorable（不应通过）
4. **不确定性折价**：证据不充分的 claim → 受益向下折价
5. **整体 BR 结论**：favorable / acceptable / borderline / unfavorable

⚠️ **BR 有独立的置信度**：`br_acceptability_confidence`（high / medium / low / insufficient_evidence）。不与 SOTA 或 PMCF 共享通用评分。

`br_acceptability_confidence` 判定：
- **high**：受益和风险均有 ≥2 subject device high-quality 证据，方向一致
- **medium**：≥1 subject device acceptable+ 证据，受益方向清晰
- **low**：仅 indirect 证据可用，或 benefit 或 risk 一侧证据薄弱
- **insufficient_evidence**：缺少受益或风险的关键端点数据

**禁止**：
- 在证据不充分时声称「受益大于风险」
- 仅引用受益数据而不提及风险数据
- 对利益和风险使用不同的证据标准
- br_acceptability_confidence 为 insufficient_evidence 时输出 favorable/acceptable

### 文件 11：`PMCF_GAP_REASONING_SPEC.md`

**PMCF 差距推理**。

PMCF gap 的触发条件（从事实和数据中自动识别）：

| Gap 类型 | 触发条件 | PMCF 目标 |
|---|---|---|
| long_term_data | 随访 < 预期植入物使用寿命 | 长期随访 |
| population_gap | 样本不覆盖目标人群亚组 | 扩大人群 |
| rare_event | 样本量不足以检测罕见事件 | 扩大样本/注册 |
| comparator_gap | 缺少对照数据 | 对照研究 |
| real_world | 仅有 RCT 数据，缺少真实世界数据 | PMS/注册 |
| design_evolution | 设备设计变更后无临床数据 | 设计变更后临床跟踪 |

⚠️ **PMCF 有独立的严重度**：`pmcf_gap_severity`（critical / high / medium / low）。不与 SOTA 或 BR 共享通用评分。

`pmcf_gap_severity` 判定：
- **critical**：缺失安全关键端点（如无 AE 数据）、BR 结论 borderline 且缺失数据为关键因素
- **high**：缺失有效性端点、样本量显著不足以检测预期 AE 率
- **medium**：缺失特定人群数据但主要人群已覆盖、随访偏短但不低于同类设备标准
- **low**：缺失补充性数据但对主要结论影响小

PMCF 推理输出：
- `pmcf_objectives`：基于 gap 的 PMCF 目标列表
- `pmcf_methods`：建议的 PMCF 方法（如 PMCF study, registry, survey, literature review）
- `pmcf_gap_severity`：critical / high / medium / low
- `pmcf_timeline`：建议的时间框架

**不自动填充 PMCF**：系统识别 gap 和严重度，但不编造 PMCF 计划细节。gap_severity = critical → Tier 3 human review。

### 文件 12：`CER_RMF_EVIDENCE_CROSSWALK_SPEC.md`

**CER/RMF 证据交叉链接**。

⚠️ **Crosswalk = 可追溯性和一致性，不是合并 CER 和 RMF 判断。** CER 和 RMF 保持各自独立的评估领域和结论逻辑。

定义 CER 和 RMF 之间的证据可追溯性：

| CER 元素 | RMF 元素 | 链接方向 | 链接性质 |
|---|---|---|---|
| Safety claim（AE rate） | Hazard identification | CER → RMF | CER 提供 AE 发生率数据，RMF 独立评估 hazard |
| Risk claim（risk probability） | Risk estimation | CER → RMF | CER 提供风险概率证据，RMF 独立做 risk estimation |
| Performance claim（success rate） | Risk control verification | CER ← RMF | RMF 定义需要的性能证据类型，CER 提供该证据 |
| Benefit conclusion | Risk acceptability | CER → RMF | 受益论证作为风险可接受性的输入之一 |
| PMCF objective | Post-market surveillance | CER → RMF | PMCF gap 信息传递给上市后监控计划 |
| Risk control measure | CER safety evidence | CER ← RMF | 风险控制措施的存在为 CER 安全性声明提供上下文 |

交叉链接数据结构：
```json
{
  "crosswalk_id": "CW-###",
  "cer_claim_id": "CLAIM-###",
  "rmf_hazard_id": "HAZ-###",
  "link_type": "cer_supports_rmf | rmf_requires_cer",
  "link_nature": "traceability | consistency",
  "evidence_ids": ["..."],
  "link_rationale": "...",
  "domain_boundary_note": "CER 评估 ≠ RMF 评估。此链接仅表示证据共用关系。"
}
```

**不做什么**：
- ❌ 不将 CER 结论直接作为 RMF 的风险接受
- ❌ 不让 RMF 的风险估计覆盖 CER 的受益论证
- ❌ 不创建合并的 CER-RMF 分数

### 文件 13：`CLAIM_CONCLUSION_STRENGTH_SPEC.md`

**声明结论强度**。

四级结论强度 + 条件：

| 强度 | 标签 | 最低条件 |
|---|---|---|
| **STRONG** | 「证实」「已确认」 | ≥2 subject device high-quality 证据，一致方向，G42 PASS，无 CRITICAL 冲突 |
| **MODERATE** | 「支持」「表明」 | ≥1 subject device acceptable+ 证据，方向一致，无 CRITICAL 冲突 |
| **CAUTIOUS** | 「提示」「有限证据表明」 | 仅 indirect/equivalent 证据可用，或 evidence 有 MEDIUM 冲突 |
| **INSUFFICIENT** | 「当前证据无法得出结论」 | 无 subject device 证据，或全部 low-confidence，或 CRITICAL 冲突未解决 |

Writer 约束：
- 不得使用超出结论强度的措辞
- 每个声明必须标注结论强度
- INSUFFICIENT 的声明 → 不生成肯定性文字 → 生成「无法得出结论」陈述 → 触发 PMCF gap

### 文件 14：`REASONING_AUDIT_LEDGER_SPEC.md`

**推理审计台账**。

记录从 fact → conclusion 的每一步推理：

```json
{
  "audit_entry_id": "AUD-###",
  "timestamp": "...",
  "reasoning_step": "evidence_scoring | claim_reasoning | sota_synthesis | br_reasoning | pmcf_gap",
  "input_artifacts": ["FACT-###", "EVID-###"],
  "reasoning_rule_applied": "rule_id",
  "intermediate_result": {...},
  "output_artifacts": ["..."],
  "confidence": "high | medium | low",
  "assumptions": ["..."],
  "alternative_interpretations": ["..."]
}
```

审计要求：
- 每条结论必须可追溯到源头 fact
- 每个推理步骤必须记录应用的规则
- 每条规则的应用必须可复现
- 假设和替代解释必须显式记录

### 文件 15：`EVIDENCE_INTELLIGENCE_HUMAN_REVIEW_PACKET_SPEC.md`

**人工审查包**。

⚠️ **仅高影响力不确定性触发人工审查。分三层触发——不是所有低置信度都扔给人工。**

#### Tier 1 — Automatic（自动处理，不入人工审查包）

系统自动处理，仅记录日志：

| 触发条件 | 处理方式 |
|---|---|
| 单个 low-confidence fact | 自动降级到 background |
| normalization_failure | 自动标记，入 human_review_queue（非阻塞） |
| 非关键端点的 medium 冲突 | 自动标记 |
| TRANSLATION_NEEDED | 自动入 human_review_queue，不阻塞推理 |

#### Tier 2 — Flagged（标记供审查，不阻塞）

系统继续推理但标记审查点：

| 触发条件 | 处理方式 |
|---|---|
| HIGH conflict（magnitude / statistical） | 标记 claim，降低结论强度但不阻塞 |
| 缺失非关键端点 | 标记 gap，触发 PMCF |
| 等效论证使用 indirect 证据 | 标记限制条件 |
| benchmark_confidence = low | 标记 NR 字段 |

#### Tier 3 — Blocking（阻塞，需人工决策后继续）

系统暂停推理链，生成决策选项，等待人工输入：

| 触发条件 | 处理方式 |
|---|---|
| CRITICAL conflict（directional） | 阻塞相关声明 → 人工判断采纳哪方证据 |
| 缺失安全关键端点（如无 AE 数据） | 阻塞 BR 结论 → 人工判断是否可接受 |
| 等效论证完全失败 | 阻塞等效路径 → 人工判断替代方案 |
| 结论强度 INSUFFICIENT | 阻塞 Writer → 人工决定补充证据/接受限制/放弃 |
| br_acceptability_confidence = insufficient_evidence | 阻塞 BR 输出 |
| pmcf_gap_severity = critical | 阻塞 PMCF 输出 |

审查包内容（Tier 2 和 Tier 3 格式相同，Tier 3 多 decision_required = true）：

```json
{
  "packet_id": "HRP-###",
  "tier": 2 | 3,
  "trigger": "critical_conflict | missing_essential_endpoint | equivalence_failed | conclusion_insufficient",
  "affected_claims": ["CLAIM-###"],
  "evidence_summary": {...},
  "decision_options": ["option_a", "option_b"],
  "recommendation": "...",
  "decision_required": true | false,
  "deadline_signal": "routine | urgent"
}
```

### 文件 16：`EVIDENCE_INTELLIGENCE_VALIDATION_HARNESS_SPEC.md`

**验证框架**。

验证 Intelligence Core 的正确性，而不只是测试覆盖率。

验证维度：
1. **正向验证**：给定理想输入，输出是否符合预期？（如 subject device high-quality evidence → STRONG conclusion）
2. **负向验证**：给定不足输入，系统是否正确降级？（如只有 low-confidence facts → INSUFFICIENT）
3. **对手验证**：构造边界/冲突/矛盾的输入，系统是否正确处理？
4. **回归验证**：已有 165 tests 必须继续通过

**八个必含的负向/对手验证案例**：

| # | 案例 | 输入构造 | 预期行为 |
|---|---|---|---|
| N1 | **强声明 + 弱证据** | claim=safety_clinical, 仅 competitor evidence low-quality | 结论 INSUFFICIENT, 不生成肯定性声明 |
| N2 | **竞品证据误用** | 仅有 competitor device 数据, claim=performance_clinical | Admissibility NOT_ADMISSIBLE, 不支撑声明 |
| N3 | **端点语义不匹配** | fact endpoint="血压" mapped to claim endpoint="心输出量" | 映射 unmatched, 不链接声明 |
| N4 | **OCR-低分 pivot 事实** | extraction_confidence=OCR_uncertain 的 fact 被用作 primary | fact_role_cap=background, evidence 被降级 |
| N5 | **静默冲突平均** | 研究 A: 成功率 95%, 研究 B: 成功率 60%, 同 endpoint_cluster | CRITICAL 冲突被标记, 不输出平均值 |
| N6 | **缺失 subject device 临床数据** | 仅有 literature_pubmed_sota + similar_device | 所有 subject device claims → INSUFFICIENT, Controlled Compromise 触发 |
| N7 | **CER/RMF 不匹配** | CER safety claim 有 evidence, RMF 对应 hazard 无 evidence | Crosswalk 标记 mismatch, 不合并判断 |
| N8 | **PMCF 触发链** | 随访 6 月、样本量 20、单臂 → 3 个 gap 同时触发 | 全部 3 个 gap 被识别, gap_severity 分级正确 |

完整验证案例数 ≥24（8 负向 + 8 正向 + 8 边界）。

### 文件 17：`CODEX_BATCH_PLAN_DRAFT_EI_CORE.md`

**Codex 实现批次计划**。

将 Intelligence Core 拆分为可顺序实现的批次：

- **Batch EI-1**：Evidence Scoring Model + Regulatory Admissibility
- **Batch EI-2**：Device Claim Reasoning + Claim Conclusion Strength
- **Batch EI-3**：Absence of Evidence Reasoning + Evidence Synthesis Method Policy
- **Batch EI-4**：Equivalence/Similarity Bridging
- **Batch EI-5**：SOTA Benchmark Synthesis
- **Batch EI-6**：Benefit-Risk Reasoning
- **Batch EI-7**：PMCF Gap Reasoning
- **Batch EI-8**：CER/RMF Crosswalk + Reasoning Audit Ledger
- **Batch EI-9**：Human Review Packet + Validation Harness

每个批次：problem/goal/boundary/acceptance/stop-condition 格式 → 不固定实现路径 → 不碰 graph/gates/agents

### 文件 18：`PRE_PILOT_EI_CORE_VALIDATION_CRITERIA.md`

**恢复 Pilot 前的验证标准**。

在 Intelligence Core 实现并验证通过后，才能恢复 pilot：

1. 全部 EI-1 到 EI-9 测试通过（baseline 165 + new 44 = ≥209 tests）
2. 验证框架的 24 个案例全部通过
3. 负向/对手案例正确降级（不自作主张）
4. graph/gates/agents 零变化
5. CAL-001 重跑：evidence intelligence 输出符合预期
6. 人工审查包结构完整

不满足任一条件 → Pilot 继续暂停。

### 文件 19：`REASONING_INPUT_OUTPUT_CONTRACT_SPEC.md`

**推理层输入输出接口契约**。

⚠️ **每个 spec 不自行发明输入输出 schema。统一由此契约定义。**

**从 V3-Core → Intelligence Core 的精确输入**（每个字段的 source 来源和格式约束）：

| 输入数据 | 来源 | 关键字段 |
|---|---|---|
| clinical_evidence_fact_table | pipeline.py (V3) | fact_id, evidence_id, endpoint_family, value_numeric, value_unit, CI_lower, CI_upper, p_value, population_n, extraction_confidence, normalizer_status |
| evidence_registry | pipeline.py (V2+V3) | evidence_id, source_type, device_relationship, comparability_band, allowed_claim_types, evidence_role, fact_role_cap, g42_fact_signal |
| semantic_endpoint_mapping_table | pipeline.py (V3) | fact_id, endpoint_family, mapping_confidence, endpoint_cluster_id, match_dimensions |
| evidence_conflict_report | pipeline.py (V3) | conflict_id, evidence_ids, conflict_type, severity |
| human_review_queue | pipeline.py (V3) | review_id, fact_id, trigger_reason, status |
| claim_decomposition | state (V1) | claim_id, claim_type, required_source_profile |

**从 Intelligence Core → Writer 的精确输出**（每个输出的 schema 和消费限制）：

| 输出 | Schema | Writer 如何使用 |
|---|---|---|
| claim_support_matrix | claim_id → support_level + max_conclusion_strength + supporting_evidence_ids + missing_evidence_flags | 决定哪些声明可以写、用什么强度的措辞 |
| sota_benchmark_table | endpoint_cluster → benchmark_range + subject_device_position + benchmark_confidence + data_source_count | Writer SOTA section 的结构化数据源 |
| benefit_risk_conclusion | overall_judgment + br_acceptability_confidence + per_claim_benefit_quantified + per_claim_risk_quantified | Writer BR section 的核心论据 |
| pmcf_gap_register | gap_id → gap_type + gap_severity + pmcf_objective + affected_claims | Writer PMCF section 的 gap 列表 |
| cer_rmf_crosswalk_table | crosswalk_id → cer_claim + rmf_hazard + link_type + link_nature + evidence_ids | 跨文档引用（不合并） |
| reasoning_audit_ledger | audit_entry_id → step + rule_applied + inputs + outputs + assumptions | 审计附件 |
| human_review_packet | packet_id → trigger + tier + affected_claims + decision_options + decision_required | 人工审查包 |
| writer_conclusion_constraints | per claim: allowed_language_strength + forbidden_phrases + quantitative_allowed_flag | Writer 的硬约束 |

### 文件 20：`SCORING_CALIBRATION_AND_THRESHOLD_POLICY.md`

**评分校准和阈值策略**。

⚠️ **Evidence scoring 是内部推理辅助，不是外部监管认证。评分不得被声称或理解为监管级别的证据质量认证。**

**评分状态（score_calibration_status）**：
- `provisional`：初始阈值设定，基于 MEDDEV 2.7/1 Rev.4 + Oxford LoE 的理论映射，未经过 calibration 数据验证
- `internally_calibrated`：经过 calibration 项目（CAL-001/002/003）的评分分布验证，阈值调整过
- `human_reviewed`：人工确认评分合理（仅在 Tier 2/3 human review 中设定）

**阈值设定原则**：
1. 初始阈值基于 MEDDEV 2.7/1 Rev.4 的 evidence level 映射
2. 权重分配基于 regulatory relevance（device relationship 和 study design 是监管审查的核心关注点）
3. 阈值不可由 LLM 调整——必须是确定性计算
4. 阈值变更需 CCD 审批，记录在 DECISION_LOG

**校准方法**：
- Calibration 项目（CAL-001/002/003）的评分分布与人工 reviewer 的独立评分对比
- 如果系统评分与人工评分偏离 >20 分（0-100 scale），需要阈值调整
- 校准仅在 pilot 恢复前做一次，pilot 中不自行校准

**禁止**：
- ❌ 将分数视为绝对质量指标
- ❌ 用评分替代 G42 的 claim-specific evidence sufficiency 判断
- ❌ 对不同 regulatory context 使用同一套阈值

---

## 五、Hard Boundaries（不可逾越）

1. **事实不绕过证据注册** → fact 必须通过 evidence_registry 才能被 Reasoning 消费
2. **推理不绕过 G42** → claim support 必须通过 G42 验证
3. **冲突不静默平均** → 冲突必须标记，不得在未解决时聚合
4. **缺失证据不编造结论** → 不得在无证据时声称「安全有效」；缺失证据分 7 类，每类有独立的推理规则
5. **相似/竞品证据不超范围使用** → 严格按 allowed-use 矩阵
6. **结论强度不超证据支撑** → Writer 措辞受 conclusion_strength 硬约束
7. **人工审查仅用于高影响力不确定性** → Tier 1 自动处理，Tier 2 标记，仅 Tier 3 阻塞
8. **Pilot 前必须通过全部验证标准** → 不满足不恢复
9. **推理 I/O 由统一契约定义** → 每个 spec 不自行发明输入输出 schema，所有接口见 REASONING_INPUT_OUTPUT_CONTRACT_SPEC.md
10. **证据评分是 provisional 的内部辅助** → 不是外部监管认证，阈值需校准策略，不可由 LLM 调整
11. **CER/RMF 交叉链接保留领域边界** → crosswalk = 可追溯性和一致性，不是合并 CER 和 RMF 判断
12. **SOTA/BR/PMCF 各有独立置信度** → 不使用一个通用评分驱动三者；各自有 benchmark_confidence / br_acceptability_confidence / pmcf_gap_severity

---

## 六、与已有系统的集成点

| Intelligence Core 组件 | 消费已有 | 被谁消费 |
|---|---|---|
| Evidence Scoring | V3 fact_table + V2 evidence_registry | Claim Reasoning, SOTA, BR |
| Regulatory Admissibility | V2 source_type + device_relationship | Claim Reasoning |
| Claim Reasoning | Evidence Scoring + Admissibility | SOTA, BR, PMCF, Writer |
| SOTA Synthesis | Claim Reasoning + fact_table | Writer (SOTA section) |
| BR Reasoning | Claim Reasoning + fact_table | Writer (BR section) |
| PMCF Gap | Claim Reasoning | Writer (PMCF section) |
| CER/RMF Crosswalk | Claim Reasoning | RMF pipeline (future) |
| Audit Ledger | 全部上游组件 | Human Review Packet |
| Conclusion Strength | Claim Reasoning + BR + PMCF | Writer (conclusion language) |

---

## 七、Gate Integration Verification

### 问题

EI Core 不修改 graph.py / gates.py / agents.py。但 EI 输出（claim_support_matrix, writer_conclusion_constraints, benefit_risk_conclusion, pmcf_gap_register）必须被 G42/G46 消费，才能在证据不充分时触发 Controlled Compromise。

### 已有门控资产

基于 `SPIRAL_ARCHITECTURE_IMPLEMENTATION_PROOF_INDEX.md`：
- **G42 per-claim sufficiency** → IMPLEMENTED in gates.py ✅
- **G46 pre_writer_readiness_gate** → IMPLEMENTED in gates.py ✅
- **Controlled compromise node** → IMPLEMENTED in pipeline.py ✅
- **Gate signal contract** → IMPLEMENTED in gates.py + state.py ✅

### 集成路径（状态中介，不修改门控代码）

```
EI Core → state fields:
  claim_support_matrix
  writer_conclusion_constraints
  benefit_risk_conclusion
  pmcf_gap_register

G42/G46 ← state fields (existing reads):
  evidence_registry
  claim_decomposition
  gate_signal_contract

Pipeline bridge (Option C, CCD recommended):
  _build_ei_gate_signals() 在 pipeline.py 中：
    读取 EI outputs → 转换为 gate-readable signals
    → 写入 state.gate_signals
    → G46 已有逻辑消费 gate_signals → BLOCKED → Controlled Compromise
```

**关键触发条件**：
- `claim_support_matrix` 中所有 critical claims 均为 INSUFFICIENT → G46 BLOCKED
- `benefit_risk_conclusion.br_acceptability_confidence = insufficient_evidence` → G46 BLOCKED
- `pmcf_gap_register` 中有 gap_severity = critical → G46 标记但可能不阻塞

### 风险

Gate 代码可能当前不读取 `claim_support_matrix` / `writer_conclusion_constraints`。**如果门控无法消费 EI 输出，EI 输出将对 Writer 约束不可见——Writer 可能在证据不充分时仍生成肯定性声明。**

### 预 EI-1 验证要求

**在 CODEX_EI_1 开始前**，CCD 必须验证（通过读取 gates.py 或 runtime proof）：
1. G42 是否读取 `evidence_registry` 中的 `fact_role_cap` 字段？
2. G46 是否聚合 `gate_signals` 并支持 BLOCKED 路由？
3. Controlled Compromise 是否在 G46=BLOCKED 时正确触发？

如果任一答案为否 → **停止 EI-1** → 请求 Owner 授权门控集成策略。

### 门控集成策略选项（供 Owner 决策）

| 选项 | 方案 | 门控代码变更 |
|---|---|---|
| **A** | 直接修改 G42/G46 函数读取 EI state 字段 | 修改 gates.py |
| **B** | 新增 G47-G50 条件专门消费 EI 输出 | 修改 gates.py |
| **C (CCD 推荐)** | `_build_ei_gate_signals()` in pipeline.py 将 EI 输出转换为 gate_signals，G46 已有逻辑消费 | 不修改 gates.py |

---

## 八、不做什么

- ❌ 不重写 Writer agent prompt（Writer 消费 Intelligence Core 的输出，不是替代）
- ❌ 不修改 graph.py / gates.py / agents.py（已有硬门控和螺旋架构保持不变）
- ❌ 不让 LLM 做推理判断（推理规则是确定性的，不是 prompt-based）
- ❌ 不自动提升事实置信度
- ❌ 不在证据不充分时完成 CER
- ❌ 不恢复 pilot 直到验证标准全部达标
- ❌ 不让每个 spec 自行定义 I/O schema（统一由 I/O Contract 定义）
- ❌ 不将 evidence scoring 声称或理解为监管级认证
- ❌ 不合并 CER 和 RMF 的判断
- ❌ 不用一个通用评分驱动 SOTA + BR + PMCF
- ❌ 不把所有低置信度事实扔给人工审查
- ❌ 不实现——仅规划

---

## 九、20 个输出文件的总依赖顺序

写文件顺序按依赖关系排列（被依赖的先写）：

```
Phase A: 基础和接口
  1. CER_RMF_EVIDENCE_INTELLIGENCE_CORE_MASTER_PLAN.md
  2. CLINICAL_FACT_LAYER_FINAL_SCOPE.md
 19. REASONING_INPUT_OUTPUT_CONTRACT_SPEC.md

Phase B: 证据评价（消费 A）
  3. REGULATORY_EVIDENCE_ADMISSIBILITY_SPEC.md
  8. EVIDENCE_SCORING_MODEL_SPEC.md
 20. SCORING_CALIBRATION_AND_THRESHOLD_POLICY.md

Phase C: 推理核心（消费 B）
  4. ABSENCE_OF_EVIDENCE_REASONING_SPEC.md
  5. EQUIVALENCE_SIMILARITY_BRIDGING_SPEC.md
  6. EVIDENCE_SYNTHESIS_METHOD_POLICY.md
  7. DEVICE_CLAIM_REASONING_SPEC.md

Phase D: 综合分析（消费 C）
  9. SOTA_BENCHMARK_SYNTHESIS_SPEC.md
 10. BENEFIT_RISK_REASONING_SPEC.md
 11. PMCF_GAP_REASONING_SPEC.md

Phase E: 约束和追溯（消费 D）
 12. CER_RMF_EVIDENCE_CROSSWALK_SPEC.md
 13. CLAIM_CONCLUSION_STRENGTH_SPEC.md
 14. REASONING_AUDIT_LEDGER_SPEC.md

Phase F: 人工决策和验证（消费 E）
 15. EVIDENCE_INTELLIGENCE_HUMAN_REVIEW_PACKET_SPEC.md
 16. EVIDENCE_INTELLIGENCE_VALIDATION_HARNESS_SPEC.md

Phase G: 实施规划（消费全部）
 17. CODEX_BATCH_PLAN_DRAFT_EI_CORE.md
 18. PRE_PILOT_EI_CORE_VALIDATION_CRITERIA.md
```

---

*CCD 签发：2026-05-12 | Planning Only | 修订版 2 — 含 7 项结构约束 + 20 文件*

---

*CCD 签发：2026-05-12 | Planning Only*
