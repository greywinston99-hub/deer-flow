# BIGDP2026.6V_2 — Skill & Tool Gap Plan

**Purpose:** Per-stage assessment of: what rules/SOPs are needed, what tools/skills are missing, what MCP/external resources are needed, who implements what.

---

## Stage 1: 产品身份确认

| 维度 | 评估 |
|:---|:---|
| **规则/SOP** | BIGDP2026.6 已有 `device_identity_lock`；本轮不需要新增 |
| **工具缺口** | 无 |
| **谁实现** | 继承 BIGDP2026.6 |
| **需要人工专家** | HC-01 确认时 |

---

## Stage 2: 声明分析与边界

| 维度 | 评估 |
|:---|:---|
| **规则/SOP** | BIGDP2026.6 已有 CLAIM_CLASSIFICATION_DECISION_TABLE；本轮增加 endpoint-mismatch detection（claim 声称的 endpoint 与 S6 实际提取的不一致） |
| **工具缺口** | `endpoint_claim_matcher` — 检查 claim 中提到的 endpoint 是否都在 endpoint_registry 中 |
| **谁实现** | Claude Code（pipeline.py claim decomposition） |
| **需要人工专家** | 边界模糊时（performance claim vs clinical claim 区分） |

---

## Stage 3: 文献检索

| 维度 | 评估 |
|:---|:---|
| **规则/SOP** | 本轮新增：`SRC-04` retrieval audit trail 要求、`SRC-05` minimum databases（PubMed+Embase）、`SRC-06` query string preservation |
| **工具缺口** | `RETRIEVAL_AUDIT_TRAIL` artifact（新）、`G_RETRIEVAL_AUDIT` gate（新）、manual search gold comparison tool |
| **MCP/外部** | PubMed MCP（已有）、Embase API（如需） |
| **谁实现** | Claude Code（graph.py search nodes + gates.py new gate）；Controller prepares manual search gold |
| **需要人工专家** | Manual search gold set 建立；检索策略审阅（HC-03） |

---

## Stage 4: 文献筛选与评价

| 维度 | 评估 |
|:---|:---|
| **规则/SOP** | 本轮新增：`SCR-01` N<10 → EXCLUDE、`SCR-02` animal/cadaver/in-vitro → EXCLUDE、`SCR-03` time_range_unspecified → REWORK、`SCR-04` exclusion_reason_code required |
| **工具缺口** | `SCREENING_RULE_ENGINE`（新）、`G_SCREENING` gate（新）、screening decisions logger |
| **MCP/外部** | liteparse（full-text screening data extraction） |
| **谁实现** | Claude Code（pipeline.py screening + gates.py）；Controller prepares screening gold labels |
| **需要人工专家** | 边界文献的 inclusion/exclusion 判断（HC-04）；规则不覆盖的 edge cases |

---

## Stage 5: 临床数据提取

| 维度 | 评估 |
|:---|:---|
| **规则/SOP** | 本轮新增：`DAT-01` PMID_ANCHOR — every data point must have source PMID、`DAT-02` abstract_verified flag、`DAT-03` fulltext_status per evidence、`DAT-04` numerator/denominator/population required、`DAT-05` denominator must match study reported N |
| **工具缺口** | `DATA_TRACEABILITY_VALIDATOR`（新）、`DENOMINATOR_VALIDATOR`（新）、`FULLTEXT_STATUS` checker（新）、`G_DENOMINATOR` gate（新） |
| **MCP/外部** | PubMed MCP（abstract verification）、liteparse（full-text data extraction）、scipy.stats（Wilson CI） |
| **谁实现** | Claude Code（3 new validators + gates）；Controller prepares denominator gold labels |
| **需要人工专家** | Subgroup identification（abstract 中不一定明确）；data point verification（HC-05） |

---

## Stage 6: 终点与 Benchmark 建立

| 维度 | 评估 |
|:---|:---|
| **规则/SOP** | 本轮新增：`EPT-01` endpoint semantic classifier（AE/treatment_failure/inadequate_hemostasis/other）、`EPT-02` comparator benchmark completeness、`EPT-03` Wilson 95% CI required for every rate、`EPT-04` SOTA accounting consistency |
| **工具缺口** | `ENDPOINT_SEMANTIC_CLASSIFIER`（新）、`COMPARATOR_BENCHMARK_CHECKER`（新）、`SOTA_ACCOUNTING_CONSISTENCY_CHECKER`（新）、`WilsonCI` calculator |
| **MCP/外部** | scipy.stats（Wilson CI）、expert labels（gold standard for endpoint classification） |
| **谁实现** | Claude Code（classifier + checkers + gates）；Controller + Domain Expert 提供 expert labels |
| **需要人工专家** | Endpoint classification labels（AE vs treatment_failure 区分需要临床判断）；comparator benchmark acceptability |

---

## Stage 7: 等效性评估

| 维度 | 评估 |
|:---|:---|
| **规则/SOP** | BIGDP2026.6 已有 3-dim rule（结构/机理/适应症）；本轮强化：equivalent device 的 benchmark 数据也必须满足 DC-4/5/10（PMID trace、fulltext、denominator） |
| **工具缺口** | 等效设备数据的 traceability 要求与 subject device 一致 |
| **谁实现** | 继承 BIGDP2026.6 EQUIVALENCE_ROUTE_LOCK；Claude Code 扩展数据质量要求 |
| **需要人工专家** | 3-dim 判断的边界情况 |

---

## Stage 8: 证据→声明映射

| 维度 | 评估 |
|:---|:---|
| **规则/SOP** | BIGDP2026.6 已有 CLAIM_CLASSIFICATION、EVIDENCE_SUPPORT、CONCLUSION_STRENGTH；本轮强化：每个 claim 的 evidence 必须 pass DC-4（PMID trace）+ DC-5（fulltext）+ DC-10（denominator） |
| **工具缺口** | `CLAIM_EVIDENCE_INTEGRITY_CHECKER` — 验证每个 claim-evidence link 的数据质量 |
| **谁实现** | Claude Code（扩展 G43 claim_evidence gate） |
| **需要人工专家** | 间接证据支撑强度的判断 |

---

## Stage 9: Gap / PMCF

| 维度 | 评估 |
|:---|:---|
| **规则/SOP** | BIGDP2026.6 已有 PMCF 4-rule decision；本轮不变 |
| **工具缺口** | 无新增 |
| **谁实现** | 继承 BIGDP2026.6 |
| **需要人工专家** | PMCF study design（不在系统范围内） |

---

## Stage 10: Benefit-Risk / GSPR

| 维度 | 评估 |
|:---|:---|
| **规则/SOP** | 本轮强化：BR 分析中的 safety data 必须满足 endpoint semantic correctness（DC-6） |
| **工具缺口** | `BR_DATA_QUALITY_CHECK` — safety endpoint 语义正确性验证 |
| **谁实现** | Claude Code（扩展 G44 benefit_risk gate） |
| **需要人工专家** | Risk acceptability judgment（不在系统范围内） |

---

## Stage 11: 专家推理整合

| 维度 | 评估 |
|:---|:---|
| **规则/SOP** | 本轮新增：`INT-01` cross-chapter consistency — same endpoint across chapters must have identical values、`INT-02` SOTA accounting consistency — all numbers trace to source node outputs |
| **工具缺口** | `CROSS_CHAPTER_CONSISTENCY_CHECKER`（新）、全局 consistency report |
| **谁实现** | Claude Code（checker + gate + writer remediation） |
| **需要人工专家** | 跨章节 narrative consistency（数值一致性由系统检查，叙述一致性需要人工） |

---

## Stage 12: 写入就绪与交付

| 维度 | 评估 |
|:---|:---|
| **规则/SOP** | BIGDP2026.6 已有 G46 Writer Release Board + Claude Code handoff pre-flight；本轮新增：Writer semantic QA gate |
| **工具缺口** | `WRITER_SEMANTIC_QA_GATE` — Writer 输出后检查（endpoint 一致性、数值一致性、conclusion 措辞与 CER_REASONING_LEDGER 一致） |
| **谁实现** | Claude Code（writer_remediation/writer_gates.py 扩展） |
| **需要人工专家** | 最终 CER 全文的 NB 风格审阅（human style review — 已有 HC） |

---

## 跨阶段工具需求汇总

| 工具/能力 | 阶段 | 类型 | 实现方 | 状态 |
|:---|:---|:---|:---|:---|
| RETRIEVAL_AUDIT_TRAIL | S3 | PROPOSED artifact | Claude Code | `NEEDS_SETUP` |
| G_RETRIEVAL_AUDIT | S3 | PROPOSED gate | Claude Code | `NEEDS_SETUP` |
| SCREENING_RULE_ENGINE | S4 | PROPOSED engine | Claude Code | `NEEDS_SETUP` |
| G_SCREENING | S4 | PROPOSED gate | Claude Code | `NEEDS_SETUP` |
| DATA_TRACEABILITY_VALIDATOR | S5 | PROPOSED validator | Claude Code | `NEEDS_SETUP` |
| DENOMINATOR_VALIDATOR | S5 | PROPOSED validator | Claude Code | `NEEDS_SETUP` |
| FULLTEXT_STATUS checker | S5 | PROPOSED checker | Claude Code | `NEEDS_SETUP` |
| G_DENOMINATOR | S5 | PROPOSED gate | Claude Code | `NEEDS_SETUP` |
| ENDPOINT_SEMANTIC_CLASSIFIER | S6 | PROPOSED classifier | Claude Code | `NEEDS_SETUP` |
| COMPARATOR_BENCHMARK_CHECKER | S6 | PROPOSED checker | Claude Code | `NEEDS_SETUP` |
| SOTA_ACCOUNTING_CONSISTENCY_CHECKER | S6 | PROPOSED checker | Claude Code | `NEEDS_SETUP` |
| WilsonCI calculator | S6 | PROPOSED util | Claude Code | `AVAILABLE` (scipy.stats) |
| CROSS_CHAPTER_CONSISTENCY_CHECKER | S11 | PROPOSED checker | Claude Code | `NEEDS_SETUP` |
| WRITER_SEMANTIC_QA_GATE | S12 | PROPOSED gate | Claude Code | `NEEDS_SETUP` |
| Expert labels | S4,S5,S6 | 标注数据 | Domain Expert | `HUMAN_SUPPLIED` |
| Manual search gold | S3 | 校准数据 | Controller/Owner | `HUMAN_SUPPLIED` |
| Denominator gold | S5 | 校准数据 | Controller/Owner | `HUMAN_SUPPLIED` |
| SOTA accounting gold | S6 | 校准数据 | Controller/Owner | `HUMAN_SUPPLIED` |
| Deploy verify script | 全局 | PROPOSED QA tool | Claude Code | `NEEDS_SETUP` |
| PubMed MCP | S3,S5 | 现有 MCP | 已有 | `AVAILABLE` |
| liteparse (full-text + tables) | S4,S5 | 现有 CLI | 已有 | `AVAILABLE` |
| DeerFlow graph.py / gates.py | 全局 | 现有 runtime | 已有 | `AVAILABLE` |
| BIGDP2026.6 expert_rule_loader | S6,S8,S11 | 现有 module | 已有 | `AVAILABLE` |
| BIGDP2026.6 cer_package_validator | S12 | 现有 validator | 已有 | `AVAILABLE` |
| Embase API | S3 | 外部 API | — | `OPTIONAL` |
