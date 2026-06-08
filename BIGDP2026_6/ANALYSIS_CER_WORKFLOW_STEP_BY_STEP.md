# DeerFlow CER 工作流：节点级分析 — 当前逻辑 vs 资深工程师

**日期:** 2026-06-08 | **基准:** BIGDP2026.6 代码 + 5 份真实 CER 工程师反馈 | **DAG:** 57 节点

每个节点按三栏分析：当前代码做什么 → 资深工程师做什么 → 具体差距。

---

## 节点 1：Initialize（初始化）

**代码位置:** `graph.py:_node_initialize` | **Agent:** Lead

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 读 `artifact_root`，不存在则 skip。设置 `project_id`、`update_mode`（new/update）。调 `pipeline.prepare_initial_state()` 构建初始 state。 | 打开 CER 项目文件夹，确认三件套齐全（IFU/RMF/TD）。缺 RMF → 不开始。打开 IFU 定位设备名、型号、预期用途、禁忌证。 | Source Preflight 在后端做 4-tier 检查，但 initialize 节点本身不做输入校验。工程师在第一步就卡住缺失文件，系统要到 Source Preflight gate 才报。 |

---

## 节点 2：Input Gate / HC-01（输入门控）

**代码位置:** `graph.py:_node_input_gate` | **Gate:** HC-01

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 展示设备画像给人类确认。人类可选 `confirm` 或 `rework`（goto target）。`REWORK_TARGETS['device_profile'] = ['input_gate', 'intake_pack_review']`。未知 target → `ValueError`。 | 逐项核对：设备名称是否与 IFU 一致？分类（I/IIa/IIb/III）是否正确？预期用途是否完整？有问题 → 修正后重新确认。 | ✅ BIGDP2026.6 修复了空 REWORK_TARGETS。但缺少"交叉验证"逻辑——系统不会自动对比 IFU 中的设备名与 intake pack 中的设备名是否一致。 |

---

## 节点 3：Device Profile（设备画像）

**代码位置:** `graph.py:_node_device_profile` | **Agent:** intake-profile-claim

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 从 IFU 和 intake pack 提取字段：`device_name`, `device_class`, `intended_use`, `mechanism_of_action`, `target_population`, `anatomical_site`, `indications`, `contraindications`。调 `pipeline.build_device_profile()`。 | 交叉验证三个来源（IFU/TD/CER 旧版）中设备信息的一致性。不一致时标注差异。确认适应证列表完整且每个都有临床证据覆盖计划。确认禁忌证与 RMF 危害分析一致。 | 仅提取，无交叉验证。`indications` 和 `contraindications` 不会被逐一映射到后续的 claim。 |

---

## 节点 4：Claim Decomposition（声明分解）

**代码位置:** `graph.py:_node_claim_decomposition` | **Agent:** intake-profile-claim

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 调 `pipeline.build_claims()`（LLM 调用）。从 IFU 提取声明性语句，生成 `claim_ledger[]`。每条有 `claim_id`, `claim_text`, `claim_type`, `criticality`。BIGDP2026.6 新增 `get_ifu_transformation()` 检测营销语言。 | 逐条 IFU 语句分类：临床性能声明 / 临床安全声明 / 可用性声明 / 安全警告 / 非临床陈述 / 营销过度声明。对每条声明问："如果这条被证明是错的，设备还安全有效吗？"→ 决定 criticality。营销语言 → 降级或删除。 | ✅ 营销检测已有。🔶 工程师会做"声明范围 vs 证据范围"对齐——IFU 说"所有血管手术"但证据只有"外周血管"，工程师会 narrowing。系统不做范围对齐。 |

---

## 节点 5：PICO Derivation（PICO 推导）

**代码位置:** `graph.py:_node_pico_derivation` | **Agent:** methodology-sota

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| LLM 从每条 claim 自动生成 P-I-C-O 四元素。产出 `cep_pico_matrix[]`。 | 手工为每条声明构建 PICO。Population 必须精确匹配目标人群（年龄、病种、合并症）。Intervention 必须精确匹配设备+使用方式。Comparator 基于 SOTA 确定标准治疗。Outcome 必须可测量、可量化、有临床意义。 | LLM 生成的 PICO 可能泛化——例如把 "iTClamp" 变成 "ligating clip"。Outcome 没有"可测量性"校验——"improved outcomes" 这样的模糊 Outcome 可以 slip through。 |

---

## 节点 6：Methodology Review（方法论审查）

**代码位置:** `graph.py:_node_methodology_review` | **Agent:** methodology-sota

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 审查 CEP 中的 literature_search_protocol 完整性。确认 `databases`, `inclusion_criteria`, `exclusion_criteria`, `appraisal_method`, `sota_methodology` 字段存在。 | 评估检索方案是否足够。数据库选择：最低 PubMed+Embase（欧盟必须）。纳入标准是否明确（研究类型/RCT/人群/语言/时间）？排除标准是否覆盖动物/in vitro/个案？质量评价工具是否合适（RCT→RoB2，队列→NOS）？ | 仅检查字段存在性，不评估内容合理性。例如 CEP 说"数据库：PubMed"→ 不会提示缺少 Embase。 |

---

## 节点 7：SOTA Search（技术现状检索）

**代码位置:** `graph.py:_node_sota_search` | **Agent:** methodology-sota

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 执行文献检索（Event Bus 并行或串行）。记录 `search_run_registry[]`：数据库、检索式、日期、命中数。BIGDP2026.6 新增 Humans[Mesh] 审计：检测到缺失时记录 warning。 | 逐数据库执行检索。每个检索记录完整 Boolean 表达式。自动追加 `AND Humans[Mesh]`。记录精确检索日期和执行人。通用名 > 品牌名作为检索词。 | ⚠️ Humans filter 仅审计不自动追加。检索词策略（通用名优先）未强制执行。执行人字段常缺。 |

---

## 节点 8：Citation Assignment（引文分配）

**代码位置:** `graph.py:_node_citation_assignment` | **Agent:** methodology-sota

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 给检索结果分配内部引文编号。 | 为每篇纳入文献建立唯一标识，与 PMID/DOI 双向映射。 | 基础功能，差距不大。 |

---

## 节点 9：Retrieval Domain Gate（检索领域门控）

**代码位置:** `gates.py:evaluate_retrieval_domain_gate` | **Gate:** 领域匹配

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 检查检索结果是否匹配设备临床领域。不匹配 → REWORK。 | 如果检索结果全是不同领域的文章（搜血管闭合出来牙科文章），说明检索式有问题，需要重构。 | ✅ 门控存在。 |

---

## 节点 10：Literature Screening（文献筛选）

**代码位置:** `graph.py:_node_literature_screening` | **Agent:** evidence

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 调 `pipeline.screen_literature()`。生成 PRISMA 流程图。BIGDP2026.6 新增 `_auto_classify_exclusion()`：自动为排除文献分类（case report→EXCL-01, animal→EXCL-02, review→EXCL-03, no abstract→EXCL-04, duplicate→EXCL-05）。 | 逐篇读标题+摘要。按纳入/排除标准判定。每篇排除文献记录：排除原因 + 对应标准 ID。N<10 的个案报告强制排除。动物/in vitro 研究强制排除。双人独立筛选，分歧协商解决。 | 🔶 自动分类覆盖 5 种，但无法达到 NLP 级别精度。"这篇是 review 还是 original study？"——自动分类可能误判。N<10 排除和动物排除未在筛选阶段强制执行。无双人筛选机制。 |

---

## 节点 11：Screening Depth Gate（筛选深度门控）

**代码位置:** `gates.py:evaluate_screening_depth_gate` | **Gate:** 筛选深度

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 检查 screening_pool 数量是否达到最低阈值（SCREENING_POOL_FLOOR=30）。不足 → REWORK。 | 确保筛选池足够大以保证检索全面性。 | ✅ 阈值检查。 |

---

## 节点 12：PRISMA Flow Review（PRISMA 审查）HC-3.5

**代码位置:** `graph.py:_node_prisma_flow_review` | **Gate:** HC-3.5

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 展示 PRISMA 流程图给人类审查。包含各阶段数量、排除分布、全文获取状态。人类 confirm 或 rework。 | 检查检索→去重→筛选→纳入的数字是否合理。排除原因分布是否符合预期（不应 80% 都是"其他"）。全文获取率是否可接受。 | ✅ 人类审查点存在。⚠️ 工程师会交叉检查排除文献列表，确认关键文献未被误排除。 |

---

## 节点 13：Evidence Appraisal（证据评价）

**代码位置:** `graph.py:_node_evidence_appraisal` | **Agent:** evidence

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| Event Bus 并行或串行评价证据。六因子评分（study_design 30%, relevance 25%, RoB 15%, sample_size 15%, completeness 10%, stats 5%）。权重三分级（pivotal/supportive/background）。MDCG 2020-6 级别标注。Event Bus 失败时 state snapshot + 去重回退。 | 逐篇评价。牛津 CEBM Level 1a-5。RoB 2 工具评估偏倚风险。NOS 量表评队列研究。每篇写 appraisal summary：为什么这个分数、这个权重。Pivotal 证据必须全文获取并深度评价。 | ⚠️ 评分是黑箱——为什么这篇 75 分那篇 35 分？没有逐维度解释。权重分级无理由说明。全文获取率常为 0（`fulltext_assessed_pool_count: 0`）。 |

---

## 节点 14：Fulltext Basis Gate（全文基础门控）

**代码位置:** `gates.py:evaluate_fulltext_basis_gate` | **Gate:** 全文基础

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 检查 pivotal 证据是否有全文或足够的摘要基础。 | Pivotal 证据必须全文获取。Supportive 可摘要。Background 可仅标题/摘要。 | ⚠️ 门控存在但 pivotal 全文获取率常为 0。 |

---

## 节点 15：Extract Clinical Facts（临床数据提取）🆕 P0-1

**代码位置:** `graph.py:_node_extract_clinical_facts` | **Agent:** evidence

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 正则提取：百分数 `X% (n/N)`、均值 `mean ± SD`、样本量 `N=XXX`。每个事实附 PMID + extraction_basis。终点推断：从匹配文本周围 80 字符推断 5 种终点类型。产出 `clinical_evidence_fact_table[]`。 | 逐摘要读。提取所有临床终点数值：成功率、AE 率、手术时间、住院天数……每项标注 PMID + 摘要原句 + 终点分类。区分疗效终点和安全性终点（per ISO 14155）。 | 🔶 正则覆盖 3 种数值格式。真实文献中还有：HR (95% CI)、median (IQR)、Kaplan-Meier 估计值、OR/RR——正则抓不到。终点推断仅 5 种粗分类。 |

---

## 节点 16：Endpoint Extraction（终点提取）

**代码位置:** `graph.py:_node_endpoint_extraction` | **Agent:** evidence

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 调 `pipeline.extract_endpoints()`（LLM 调用）。产出 `endpoint_registry[]`。**BIGDP2026.6 之前产出全是占位符（adverse events ×9）。** | 从临床数据中提取具体终点名："止血成功率"、"主要不良事件率"、"手术时间"、"30 天再入院率"。每个终点标注类型：主要疗效/主要安全性/次要。 | ❌ **最大差距节点。** 完全依赖 LLM，无结构化提取逻辑。P0-1 的 `extract_clinical_facts` 在下游补偿了数值，但终点命名仍不可控。 |

---

## 节点 17-22：Endpoint Pipeline（终点管线）

**节点:** clinical_fact_registry → endpoint_master → endpoint_selection → reference_framework → evidence_weighting → benchmark_derivation

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 终点注册 → 主终点选择 → 参考框架建立 → 证据加权 → 基准推导。各节点串联处理终点数据流。 | 工程师手工选择 3-5 个核心终点（主要疗效 1-2 + 主要安全性 1-2 + 次要 1-2）。排除不相关终点。为每个终点建立 SOTA 基准值。 | ⚠️ 管线自动化但上游终点质量决定了全链路质量。垃圾进垃圾出。 |

---

## 节点 23：Benchmark Derivation（基准推导）

**代码位置:** `graph.py:_node_build_benchmark_trace` | **Agent:** Lead

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 从 `endpoint_registry` + `sota_benchmark_table` + `evidence_registry` 构建 `BENCHMARK_DERIVATION_TRACE`。每终点：`source_studies[]`（PMID 列表）、`directness`（direct/indirect/fallback）、`confidence`（high/medium/low）、`acceptability_rationale`、`alternatives_rejected_rationale`（fallback 必填）、`limitations[]`。调 `match_benchmark_domain()` 获取领域配置。 | 为每个终点搜寻 SOTA 文献。提取基准值（范围或点估计）。评估基准直接性：是否同一设备/相似设备/替代疗法？评估置信度：源研究数量+质量+可比性。写可接受性理由。fallback 基准必须说明为何没有更好的。 | ✅ 结构完整。🔶 领域模板仅 2 个（cardiac_pfa, urology_nephroscope）。未知领域用通用 fallback——每个新领域都要降级。基准值提取仍依赖上游数据质量。 |

---

## 节点 24：SOTA Endpoint Gate（SOTA 终点门控）

**代码位置:** `gates.py:evaluate_sota_endpoint_gate` | **Gate:** G30

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 检查 SOTA 基准表是否完整。终点是否有足够的 benchmark 数据。不足 → REWORK → query_expansion。 | 每个核心终点是否有可接受的基准？间接基准是否充分论证？fallback 是否合理？ | ✅ 门控路由存在。 |

---

## 节点 25：Pre-G42 Claim-Evidence Candidate Linking（声明-证据候选链接）

**代码位置:** `graph.py:_node_pre_g42_claim_evidence_candidate_linking` | **Agent:** methodology-sota

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 调 `pipeline.build_pre_g42_claim_evidence_candidate_matrix()`。生成初步的 claim-evidence 候选配对。 | 对每条声明，列出可能支持它的证据候选列表。标注每条候选的相关性和适用性。 | 基础功能。 |

---

## 节点 26：Evidence Sufficiency Gate（证据充分性门控）**G42**

**代码位置:** `gates.py:evaluate_evidence_sufficiency_gate` | **Gate:** G42

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 13 种 failure pattern 路由。动态 max rounds：Class III +2, high-criticality +1, cap 6。每轮检查证据池增长 ≥15%。不足 → query_expansion（螺旋检索）。max rounds 达到且仍 EVIDENCE_TRULY_INSUFFICIENT → BLOCKED → controlled_compromise。 | 同样的逻辑——证据不够就继续搜，但不能无限搜。搜了 3-5 轮还是不够 → 证据真不够，不能假装够。需要人工决定：接受风险 or 缩小声明范围。 | ✅ 13 pattern + 动态轮次。🔶 终点成熟度因子仍浅——未考虑"这个领域通常需要多少证据才够"。 |

---

## 节点 27：Query Expansion（查询扩展）

**代码位置:** `graph.py:_node_query_expansion` | **Agent:** methodology-sota

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 扩展检索查询：同义词、上位词、相关 MeSH terms。循环回 sota_search。 | 分析"为什么第一次没搜到"——检索词太窄？数据库不够？纳入标准太严？调整策略后重新检索。 | ⚠️ 仅扩展查询词，不分析失败原因。 |

---

## 节点 28：Claim-Evidence Matrix（声明-证据矩阵）

**代码位置:** `graph.py:_node_claim_evidence_matrix` | **Agent:** writer

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 调 `pipeline.build_claim_evidence_benefit_risk_ledgers()`。构建 `claim_evidence_matrix[]`：每条声明的 `evidence_ids[]`、`support_type`、`conclusion_strength`。 | 手工建立声明→证据映射表。每对链接标注：这个证据直接支持声明的哪部分？支持强度：充分/部分/弱。 | ✅ 结构存在。⚠️ 链接数曾为 0——BIGDP2026.6 的 G43/G46 强制执行了链接。 |

---

## 节点 29：Claim-Evidence Gate（声明-证据门控）**G43**

**代码位置:** `gates.py:evaluate_claim_evidence_gate` | **Gate:** G43

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 验证每条声明至少 1 个 evidence_id。检查 `evidence_support_type`。不足 → REWORK。从 `CER_REASONING_LEDGER` 读取分类上下文。 | 不仅验证"有没有链接"，还要验证"链接对不对"——这个证据真的支持这个声明吗？ | ⚠️ 仅验证链接存在性，不验证语义支持。一篇关于止血钳的文章链接到"减少疼痛"的声明 → G43 会 PASS，但工程师会 reject。 |

---

## 节点 30：Gap/PMCF（差距/上市后临床跟踪）

**代码位置:** `graph.py:_node_gap_pmcf` | **Agent:** writer

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 调 `pipeline.build_gap_pmcf_recommendations()`。生成 `gap_pmcf_recommendations[]`。 | 对每条声明评估证据差距。不足 → 推荐 PMCF 研究设计（样本量、终点、随访时间）。不足但可接受 → 标注限制。完全不足 → 声明必须降级。 | ⚠️ PMCF 建议偏通用——"建议进行 PMCF 研究"而没有具体设计参数。 |

---

## 节点 31-32：SOTA Clinical Context + Claim-SOTA Alignment（SOTA 临床背景 + 声明对齐）

**代码位置:** `graph.py:_node_sota_clinical_context`, `_node_claim_sota_alignment` | **Agent:** writer

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 注入 SOTA 临床背景。将声明与 SOTA 基准对齐。HC-06 人类审查。 | 确认每项声明的性能水平与 SOTA 基准一致。显著偏离 SOTA 的声明需要特别论证。 | ✅ 人类审查点存在。 |

---

## 节点 33-36：Equivalence Chain（等效性链）

**节点:** device_equivalence_search → vigilance_search → equivalence_analysis → risk_gspr_mapping

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 等效设备检索。警戒数据检索（MHRA/BfArM/FDA）。三维度等效性分析。风险→GSPR 映射。 | MDR Article 61 三维度比较。差异影响评估。等效设备临床数据不同于直接证据。警戒数据检索必须覆盖多国数据库。 | 🔶 三维度比较逻辑在 YAML 规则中（EQV-01~03），但运行时部分执行。等效证据被误标为直接证据的风险存在。 |

---

## 节点 37-39：Evidence Review → Writer Synthesis → Benefit-Risk

**节点:** evidence_review_gates → writer_synthesis → benefit_risk_ledger → br_justified_gate (G44)

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 证据审查门控。写作综合。获益-风险账本。G44 获益风险审查。 | 综合所有证据，逐条 GSPR 论证。量化获益 vs 风险。不确定时不能强行结论。 | 🔶 writer_synthesis 是 LLM 生成。G44 门控存在但 BR 账本可能空洞。 |

---

## 节点 40-41：Alignment Matrix → Alignment Gate（对齐矩阵 + 门控）

**代码位置:** `alignment_matrix` → `alignment_gate` (G45)

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 生成 IFU/CER/GSPR/RMF 对齐矩阵。G45 审查。 | 确认 CER 结论与 IFU 不冲突。安全声明有 RMF 支撑。临床声明有证据支撑。 | ✅ G45 存在。 |

---

## 节点 42-44：Expert Reasoning Ledgers（专家推理账本）🆕 BIGDP2026.6

**节点:** `build_reasoning_ledger` → `build_ifu_evolution_ledger` → `build_benchmark_trace`

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| `_node_build_reasoning_ledger`：从 claim_evidence_matrix 等 5 个上游 artifact 构建。每条声明：分类、支持类型、结论强度、差距处置。调 `get_conclusion_strength()` 从决策表推导。`_node_build_ifu_evolution_ledger`：5 阶段 IFU 演变追踪。营销语言检测。`_node_build_benchmark_trace`：每终点基准审计轨迹。 | 同样的推理——分类声明、评估支持类型、确定结论强度、处置差距。 | ✅ 三个账本结构完整。🔶 内容质量依赖上游——上游弱则账本弱。 |

---

## 节点 45：Pre-Writer Readiness Gate（写入就绪门控）**G46**

**代码位置:** `gates.py:evaluate_pre_writer_readiness_gate` | **Gate:** G46

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 13 个条件：5 个真评估器（claim_evidence, retrieval_completeness, endpoint_framework, clinical_data, eu_market）+ 3 个账本检查 + BR/alignment/SOTA/fulltext_basis 真评估 + evidence_sufficiency/retrieval_domain/screening_pool 上游门控读取。**0 个无声 PASS。** BLOCKED → Writer 不能启动。 | 发布前最后检查：身份确认？声明锁定？基准可追溯？证据链接完整？差距已处置？BR 已论证？GSPR/RMF/IFU 对齐？IFU 声明已演变？未解决项有妥协或人工决定？ | ✅ **BIGDP2026.6 核心成果。** G46 从占位符升级为真门禁。13/13 条件无静默通过。 |

---

## 节点 46-48：Final Chain（最终链）

**节点:** endpoint_framework_lock → clinical_data_consolidation → cer_input_package_export

| 当前逻辑 | 资深工程师会做什么 | 差距 |
|:---|:---|:---|
| 终点框架锁定。临床数据整合。导出 CER_INPUT_PACKAGE.json：引用完整性检查（orphan evidence_id→BLOCKED）、`package_schema_version: 1.0.0`、3 个账本嵌入。 | 最终检查：所有数据一致、所有引用可追溯、所有结论有证据。导出给 Writer。 | ✅ 导出检查完善。 |

---

## 差距汇总

```
节点                                  成熟度    关键差距
══════════════════════════════════════════════════════════════════
 1  Initialize                        ████████  Source Preflight 后置
 2  Input Gate / HC-01                █████████ ✅
 3  Device Profile                    ███████░  交叉验证缺失
 4  Claim Decomposition               ████████  声明范围不对齐
 5  PICO Derivation                   ██████░░  LLM 泛化+Outcome模糊
 6  Methodology Review                ███████░  仅字段存在性检查
 7  SOTA Search                       ████████  Humans 仅审计
 8  Citation Assignment               █████████ ✅
 9  Retrieval Domain Gate             █████████ ✅
10  Literature Screening              ███████░  N≥10/动物未强制执行
11  Screening Depth Gate              █████████ ✅
12  PRISMA Flow Review                ████████  ✅
13  Evidence Appraisal                ███████░  评分黑箱+全文获取率0
14  Fulltext Basis Gate               ███████░  pivotal 全文率0
15  Extract Clinical Facts 🆕         ██████░░  正则覆盖有限(3种格式)
16  Endpoint Extraction               ████░░░░  ❌ 最大差距—LLM占位符
17-22 Endpoint Pipeline               ██████░░  上游弱则全链弱
23  Benchmark Derivation              ████████  领域模板仅2个
24  SOTA Endpoint Gate                █████████ ✅
25  Pre-G42 Linking                   █████████ ✅
26  G42 Evidence Sufficiency          ████████░ 终点成熟度因子浅
27  Query Expansion                   ██████░░  不分析失败原因
28  Claim-Evidence Matrix             ████████  ✅
29  G43 Claim-Evidence Gate           ███████░  仅验证链接存在性
30  Gap/PMCF                          ███████░  PMCF建议偏通用
31-32 SOTA Clinical + Alignment       ████████  ✅
33-36 Equivalence Chain               ██████░░  三维比较部分执行
37-39 Evidence→BR                     ███████░  BR账本可能空洞
40-41 Alignment + Gate                ████████  ✅
42-44 Expert Ledgers 🆕               ████████  结构完整，依赖上游
45  G46 Writer Release Board          █████████ ✅ 核心成果
46-48 Final Chain                     █████████ ✅
```

**最值得投入的 3 个节点：16（Endpoint Extraction）、13（Evidence Appraisal 透明化）、7（Humans 强制执行）。**
