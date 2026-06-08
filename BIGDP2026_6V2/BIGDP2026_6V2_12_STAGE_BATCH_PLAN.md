# BIGDP2026.6V_2 — 12-Stage Batch Plan

**Purpose:** Map 12 CER expert stages into 4 batches. NOT a linear 1→12 execution.
**Naming convention:** All new gates, validators, artifacts, and module names in this plan are `PROPOSED_RUNTIME_LANDING` — final naming and placement must be confirmed by Claude Code against existing architecture before Batch implementation begins.

---

## The 12 CER Expert Stages

| Stage | Name | Primary Output |
|:--:|:---|:---|
| S1 | 产品身份确认 | `device_profile_locked`, `device_identity_lock` |
| S2 | 声明分析与边界 | `claim_ledger`, `claim_classification` |
| S3 | 文献检索 | `search_run_registry`, `RETRIEVAL_AUDIT_TRAIL` (NEW) |
| S4 | 文献筛选与评价 | `evidence_registry`, `SCREENING_DECISIONS` (NEW) |
| S5 | 临床数据提取 | `endpoint_registry`, clinical data points with `PMID_ANCHOR` (NEW) |
| S6 | 终点与 Benchmark 建立 | `sota_benchmark_table`, `BENCHMARK_DERIVATION_TRACE`, `ENDPOINT_SEMANTICS` (NEW) |
| S7 | 等效性评估 | `equivalence_analysis`, 3-dim comparison |
| S8 | 证据→声明映射 | `claim_evidence_matrix`, `CER_REASONING_LEDGER` |
| S9 | Gap / PMCF | `gap_pmcf_recommendations`, `pmcf_decision` |
| S10 | Benefit-Risk / GSPR | `benefit_risk_ledger`, `alignment_matrix` |
| S11 | 专家推理整合 | `CER_REASONING_LEDGER` (finalized), cross-chapter consistency |
| S12 | 写入就绪与交付 | `CER_INPUT_PACKAGE.json`, G46 PASS, Writer semantic QA |

---

## Batch A：Resource Preparation + Defect Mapping + Stage Interface

**覆盖阶段：** S1–S12（横切面）
**依赖：** 无
**为什么这个顺序：** 在写任何代码之前，必须知道每个阶段缺什么、10 类缺陷怎么映射、阶段之间怎么互相影响

| 维度 | 内容 |
|:---|:---|
| **输入素材** | 10 个 Asset Packages（见 ASSET_PREPARATION_SPEC） |
| **输出 artifact** | `STAGE_INTERFACE_MAP.md`、`ENGINEER_FEEDBACK_DEFECT_MAP.md`、`SKILL_AND_TOOL_GAP_PLAN.md`、`ABSORPTION_WORKFLOW.md` |
| **需要的技能** | Controller 规划、法规专家审阅 defect map、工程师确认反馈准确性 |
| **需要的工具** | 无代码工具（纯分析 + 文档） |
| **需要问的问题** | 每个阶段：当前能力是什么？缺口是什么？10 个缺陷属于哪个阶段？需要什么新 gate？回流路径是什么？ |
| **下游影响** | 整个 V_2 的方向和范围由此决定 |
| **验收标准** | 4 个 planning docs 完成；10 defect classes 映射到具体阶段；12 阶段接口关系明确；Skill/tool gap 完成 |

---

## Batch B：Retrieval / Screening / Clinical Data Extraction（S3–S5）

**覆盖阶段：** S3（文献检索）、S4（文献筛选）、S5（临床数据提取）
**依赖：** Batch A 完成（知道缺什么）
**为什么这个顺序：** 数据进入系统的前三步。如果检索不可复现、筛选无规则、数据不可溯源，下游所有推理（S6–S12）都建立在不可靠的基础上

| 维度 | 内容 |
|:---|:---|
| **输入素材** | Asset 01（法规）、02（真实项目）、03（工程师反馈）、06（full-text）、08（manual search gold）、09（denominator gold） |
| **输出 artifact** | `RETRIEVAL_AUDIT_TRAIL` (new)、`SCREENING_RULE_ENGINE` (new)、`PMID_ANCHOR` validator (new)、`DENOMINATOR_VALIDATOR` (new)、`FULLTEXT_STATUS` (new) |
| **缺陷覆盖** | DC-1 (recall), DC-2 (reproducibility), DC-3 (screening errors), DC-4 (data untraceable), DC-5 (fulltext fabrication), DC-10 (denominator) |
| **需要的技能** | Backend Python (gate + pipeline impl)、PubMed MCP (retrieval)、SQL (audit trail storage) |
| **需要的工具** | PubMed MCP、DeerFlow search nodes、liteparse (full-text)、manual search gold comparison |
| **需要问的问题** | 检索审计信息存储在哪里？筛选规则如何与现有 gate 集成？PMID trace 是 hard block 还是 warning？Denominator check 需要 LLM 还是规则？ |
| **下游影响** | S6 benchmark 依赖 S5 数据正确性；S8 claim-evidence 依赖 S5 PMID trace；S11 专家推理依赖 S4 筛选完整性 |
| **验收标准** | **DC-1、DC-2、DC-3、DC-4、DC-5、DC-10 全部 closure**；每类缺陷有对应的 PROPOSED_RUNTIME_LANDING（由 Claude Code 在 Batch implementation 前根据现有架构确认最终落地位置）；semantic tests per DC 全部通过；dry-run 输出检索可复现、筛选有规则、数据有 PMID 锚定 |

---

## Batch C：Endpoint / Benchmark / Equivalence / Claim-Evidence / PMCF / BR-GSPR（S6–S10）

**覆盖阶段：** S6（endpoint + benchmark）、S7（equivalence）、S8（claim-evidence）、S9（gap/PMCF）、S10（BR/GSPR）
**依赖：** Batch B 完成（数据输入可靠）
**为什么这个顺序：** 只有数据可靠了，推理才有意义。S6 endpoint 语义错误会污染 S8 claim-evidence 和 S10 BR。S9 PMCF 判断依赖 S8 的 gap 识别。

| 维度 | 内容 |
|:---|:---|
| **输入素材** | Batch B 输出（可追溯数据）+ Asset 07（expert labels）、10（SOTA gold）、01（法规 ISO 14155） |
| **输出 artifact** | `ENDPOINT_SEMANTIC_CLASSIFIER` (new)、`COMPARATOR_BENCHMARK_COMPLETENESS_CHECK` (new)、`SOTA_ACCOUNTING_CONSISTENCY_CHECKER` (new) |
| **缺陷覆盖** | DC-6 (endpoint semantics), DC-7 (comparator), DC-8 (cross-chapter — 部分，完整在 Batch D), DC-9 (SOTA accounting) |
| **需要的技能** | Backend Python (classifier + validator + gate)、Statistical (Wilson CI computation)、Regulatory (ISO 14155 terminology mapping) |
| **需要的工具** | `scipy.stats` (Wilson CI)、expert labels (gold standard for endpoint classification) |
| **需要问的问题** | Endpoint 语义分类是 rule-based 还是 LLM？Wilson CI 在哪里计算 — pipeline 还是 gate？SOTA accounting mismatch 的容忍度？ |
| **下游影响** | S11 专家推理整合依赖 S6–S10 输出的一致性；S12 Writer 依赖 S8 claim classification + S6 endpoint semantics |
| **验收标准** | 3 new checkers/classifiers 实现；DC-6/7/8/9 的 semantic tests 通过；endpoint 分类正确；comparator benchmark 完整含 CI；SOTA 数字一致 |

---

## Batch D：Reasoning Integration / Writer Semantic QA / Real Project Validation（S11–S12 + 全局）

**覆盖阶段：** S11（专家推理整合）、S12（写入就绪）+ 跨所有阶段的一致性
**依赖：** Batch B + C 完成
**为什么这个顺序：** 只有所有组件都就位，才能做端到端整合和真实项目验证

| 维度 | 内容 |
|:---|:---|
| **输入素材** | Batch B + C 的所有输出 + Asset 05（accepted outputs as baseline）、02（real projects for validation） |
| **输出 artifact** | `CROSS_CHAPTER_CONSISTENCY_CHECKER` (finalized)、Writer semantic QA gate (W_CONSISTENCY)、Regression lock (all tests)、Dry-run validation report |
| **缺陷覆盖** | DC-8 (cross-chapter — 完整闭合)、全局 regression check (DC-1~10 recurrence) |
| **需要的技能** | Backend Python (gates integration)、QA (end-to-end dry-run)、Controller (acceptance review) |
| **需要的工具** | Full pytest suite、dry-run script、deploy_verify.sh (from BIGDP2026.6) |
| **需要问的问题** | 所有新 gate 是否都在 G46 之前？Writer QA gate 在哪一步？真实项目 dry-run 选哪个？ |
| **下游影响** | 这是终点 — 下游就是 release decision |
| **验收标准** | 端到端 dry-run 通过；10 defect classes 全部复验不复发；500+ tests pass；65 checklist items PASS；Controller signs off |
