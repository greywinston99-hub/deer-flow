# BIGDP2026.6V_2 — Stage Interface Map

**Purpose:** Analyze dependencies and feedback loops between 12 CER stages. Clarify: what flows forward, what flows backward, what needs human gate, what needs Claude Code fix, what is just missing project data.
**Naming convention:** All new components referenced here (gates, validators, checkers, classifiers) are `PROPOSED_RUNTIME_LANDING` — defined by the capability they provide (e.g., "PMID-trace verification"), with final code placement determined by Claude Code during Batch implementation review.
**Current phase:** `PLAN_REVIEW` — no Claude Code code implementation permitted.

---

## Forward Dependencies（正向依赖）

```
S1 (产品身份)
 │
 ├─→ S2 (声明分析) — identity 错误 → claim boundary 错误
 ├─→ S3 (检索) — identity → PICO → search strategy
 ├─→ S7 (等效性) — identity → 3-dim comparison target
 ├─→ S10 (GSPR) — identity → applicable GSPR requirements
 │
S2 (声明边界)
 │
 ├─→ S3 (检索) — claim → PICO → search query
 ├─→ S6 (endpoint) — claim → which endpoints to extract
 ├─→ S8 (claim-evidence) — claim → evidence linkage target
 ├─→ S12 (Writer) — claim → what can be stated in CER
 │
S3 (检索)
 │
 ├─→ S4 (筛选) — search results → screening pool
 ├─→ G42 (evidence sufficiency) — retrieval audit → spiral decision
 │
S4 (筛选)
 │
 ├─→ S5 (数据提取) — included studies → data extraction target
 ├─→ S6 (benchmark) — study pool → benchmark derivation pool
 │
S5 (临床数据)
 │
 ├─→ S6 (endpoint/benchmark) — extracted data → benchmark values
 ├─→ S8 (claim-evidence) — data points → evidence for claims
 ├─→ S10 (BR/GSPR) — safety data → risk assessment
 │
S6 (endpoint/benchmark)
 │
 ├─→ S7 (等效性) — own device endpoints → comparison with equivalent device
 ├─→ S8 (claim-evidence) — benchmark → claim support strength
 ├─→ S9 (PMCF) — benchmark gap → PMCF need
 ├─→ S12 (Writer) — benchmark values → CER §3/§6 tables
 │
S7 (等效性)
 │
 ├─→ S8 (claim-evidence) — equivalence status → evidence route
 │
S8 (claim-evidence)
 │
 ├─→ S9 (PMCF) — gap identification → PMCF trigger
 ├─→ S12 (Writer) — evidence support → CER conclusion strength
 │
S9 (PMCF)
 │
 ├─→ S10 (BR) — PMCF mitigates residual risk
 ├─→ S12 (Writer) — PMCF plan → CER limitation section
 │
S10 (BR/GSPR)
 │
 ├─→ G46 (writer release) — BR completeness → release gate
 ├─→ S12 (Writer) — risk/benefit conclusion → CER §7
 │
S11 (专家推理整合)
 │
 ├─→ S12 (Writer) — finalized reasoning → writing constraints
 │
S12 (写入就绪)
 │
 └─→ G46 → CER_INPUT_PACKAGE → Claude Code Writer
```

---

## Backward Feedback Loops（回流）

### 下游发现问题 → 回流到上游

| 下游发现 | 回流到 | 需要 Human Gate? | 需要 Claude Code 修系统? | 只是项目资料不足? |
|:---|:---|:---|:---|:---|
| S12 Writer 发现 endpoint 定义不一致（DC-8） | S6 endpoint selection | ✅ HC-06 rework | ❌ 系统应检测到不一致并阻止 Writer | ❌ |
| S12 Writer 发现 comparator benchmark 缺失（DC-7） | S6 benchmark derivation | ✅ HC-06 rework | ✅ PROPOSED: completeness checker | ❌ |
| S12 Writer 发现数据无 PMID 溯源（DC-4） | S5 data extraction | ❌ 系统应自动 BLOCK | ✅ PROPOSED: PMID-trace validator | ❌ |
| S11 推理发现 SOTA 数字不一致（DC-9） | S3 search + S4 screening + S5 extraction | ❌ 系统应自动检测 | ✅ PROPOSED: SOTA accounting checker | ❌ |
| S11 推理发现 denominator 混用（DC-10） | S5 data extraction | ❌ 系统应自动 BLOCK | ✅ PROPOSED: denominator validator | ❌ |
| S11 推理发现 endpoint 分类错误（DC-6） | S6 endpoint semantics | ✅ HC-06 rework (if ambiguous) | ✅ PROPOSED: endpoint classifier | ❌ |
| S8 claim-evidence 发现文献筛选不当（DC-3） | S4 screening | ❌ 系统应在 S4 就阻止 | ✅ PROPOSED: screening rule engine | ❌ |
| G42 发现检索 recall 不足（DC-1） | S3 search strategy | ❌ 系统应在 S3 就记录审计 | ✅ PROPOSED: retrieval audit trail | ❌ |
| G42 发现检索不可复现（DC-2） | S3 search strategy | ❌ 系统应在 S3 就强制 | ✅ PROPOSED: query string requirement | ❌ |
| G46 发现 full-text 不可得但生成了数据（DC-5） | S5 data extraction | ❌ 系统应自动 BLOCK | ✅ PROPOSED: fulltext-basis validator | ❌ |

---

## Human Gate Placement

| HC Point | Stage | When Triggered | 本轮强化 |
|:---|:---|:---|:---|
| HC-01 | S1 产品身份 | device_profile 确认 | 不变 |
| HC-02 | S2 声明分析 | claim_decomposition 确认 | 增加 DC-6 endpoint class preview |
| HC-03 | S3 检索 | sota_search_strategy 确认 | **新增** retrieval audit preview（显示检索词、命中数、recall vs gold set 对比） |
| HC-04 | S4 筛选 | prisma_flow_review 确认 | **新增** screening decisions 显示（每篇文献 inclusion/exclusion + reason_code） |
| HC-05 | S5 数据提取 | evidence_appraisal 确认 | **新增** PMID traceability summary（多少数据点有 PMID 锚定、多少 abstract_verified） |
| HC-06 | S6 endpoint | endpoint_extraction 确认 | **新增** endpoint semantic classification preview（AE vs treatment_failure vs inadequate_hemostasis） |
| HC-07 | S12 写入就绪 | pre_writer_summary 确认 | **新增** Writer constraint card（哪些 claim 只能写 limited、哪些需要 PMCF disclaimer） |

---

## Claude Code 修系统 vs 项目资料不足

| 场景 | 是系统缺陷 | 是项目资料不足 |
|:---|:---|:---|
| 检索词未记录 | ✅ 系统未强制 | — |
| Full-text 无法下载 | — | ✅ 客户未提供全文 |
| 无 PMID 锚定的数据 | ✅ 系统允许 | — |
| 某些 comparator 无公开数据 | — | ✅ 领域文献缺失 |
| Endpoint 分类错误 | ✅ 系统无分类器 | — |
| SOTA 数字不一致 | ✅ 系统未交叉验证 | — |
| Denominator 混用 | ✅ 系统未检查 | — |

**规则:** 系统缺陷 → Claude Code 修系统。项目资料不足 → 标记 limitation，不修系统。
