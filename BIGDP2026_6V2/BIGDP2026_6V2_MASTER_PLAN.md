# BIGDP2026.6V_2 — Master Plan

**Project:** BIGDP2026.6V_2
**Type:** Major System Upgrade — Evidence Integrity & Clinical Fact Reliability
**Controller:** DeerFlow CER System Controller
**Naming convention:** All new gates, validators, artifact names, and module names in this plan are `PROPOSED_RUNTIME_LANDING`. Final naming and placement must be confirmed by Claude Code against the existing architecture before Batch implementation begins. The plan defines *what* capability is needed and *which defect class* it closes; Claude Code determines *where* and *how* it lands in the codebase.
**Date:** 2026-06-08
**Predecessor:** BIGDP2026.6 (ACCEPTED, 2026-06-08)

---

## 1. 本轮升级目标

BIGDP2026.6 完成了三项核心架构升级：
- P0 安全修复（G46 硬化、HC-01 rework、MAX_SPIRAL_ROUNDS、Event Bus dedupe）
- 专家推理账本框架（CER_REASONING_LEDGER、IFU_CLAIM_EVOLUTION_LEDGER、BENCHMARK_DERIVATION_TRACE）
- Handoff 双向闭合（DeerFlow validator + Claude Code pre-flight）

但工程师在实际项目运行中发现的 10 类缺陷表明：**当系统真正面对具体临床文献时，"账本框架"存在但"账本内容"的可靠性和正确性仍有系统性缺口。** 这些不是单个项目的偶发问题——它们是系统能力的结构性缺陷。

BIGDP2026.6V_2 专注于五个维度：
1. **Evidence Integrity** — 检索可复现、筛选有规则、数据可溯源至 PMID
2. **Clinical Fact Reliability** — 全文不可得时不编造数据、denominator/subgroup 不混用
3. **SOTA Accounting** — 数字一致、来源可追、推导透明
4. **Endpoint Semantics** — 不良事件 vs 治疗失败 vs 止血不足的语义区分
5. **Writer Consistency** — 前后章节 endpoint 定义一致、comparator benchmark 完整

---

## 2. 与 BIGDP2026.6 的关系

| 维度 | BIGDP2026.6 状态 | 本轮 V_2 定位 |
|:---|:---|:---|
| Gate 硬化 (G42/G43/G46) | ACCEPTED | 继承，G42 增加 retrieval audit 检查 |
| 专家推理账本框架 | ACCEPTED（schema + node + wiring） | 深化：账本内容必须由 expert rules + gold data 驱动 |
| Handoff 双向闭合 | ACCEPTED | 继承，增加 content-level semantic validation |
| Expert rulebook runtime | ACCEPTED（Repair Sprint R1） | 新增 10 类 defect-class 规则 |
| SOTA benchmark 泛化 | ACCEPTED（config-driven） | 深化：benchmark derivation trace 完整性 |
| 检索质量 | PARTIAL（search_run_registry 存在但无审计） | **本轮重点** |
| 文献筛选正确性 | NOT_COVERED | **本轮重点** |
| 数据 PMID 溯源 | PARTIAL（evidence_registry 有 evidence_id，但无 PMID-trace） | **本轮重点** |
| 全文可靠性 | NOT_COVERED | **本轮重点** |
| Endpoint 语义 | PARTIAL（endpoint_registry 存在，但无 classification rules） | **本轮重点** |
| SOTA accounting 一致性 | NOT_COVERED | **本轮重点** |
| Denominator/subgroup | NOT_COVERED | **本轮重点** |
| Cross-chapter consistency | PARTIAL（alignment_gate 存在，但只检查存在性不检查值一致性） | **本轮重点** |

---

## 3. 覆盖状态总表

### 3.1 已被 BIGDP2026.6 充分覆盖（继承，本轮不重复）

- P0 gate safety (G46 BLOCKED 不可绕过)
- HC rework routing
- MAX_SPIRAL_ROUNDS 统一
- Event Bus dedupe
- Expert reasoning ledger framework (schemas + nodes + G46 consumption)
- Claude Code handoff pre-flight validation
- Benchmark domain externalization (YAML config)

### 3.2 部分覆盖（本轮深化）

- Expert rulebook runtime consumption → 增加 10 defect-class 规则
- Endpoint classification → 增加 semantic endpoint classifier
- G42 evidence sufficiency → 增加 retrieval audit trail check
- G43 claim-evidence linkage → 增加 PMID-trace 验证
- SOTA benchmark derivation → 增加 accounting consistency check

### 3.3 尚未充分解决（本轮重点攻克）

- 检索可复现性（无检索词记录）
- 文献筛选规则（样本量阈值、时间范围）
- 数据 PMID 溯源验证
- 全文可用性验证（无全文 = 不生成具体数据）
- Endpoint 语义分类（AE vs treatment failure vs inadequate hemostasis）
- Comparator benchmark 完整性
- 跨章节 endpoint 一致性
- SOTA 数字 accounting 一致性
- Denominator / subgroup 区分
- 跨章节上下文一致性

---

## 4. 工程师反馈为什么是 Hard Acceptance

工程师反馈来自真实 CER/SOTA 报告的系统生成结果。它们是系统在实际临床文献面前暴露出的缺陷证据，不是假设的边界情况。

本轮 hard acceptance 原则：
- 每个工程师反馈缺陷类必须有对应的 rule（规则）
- 每个 rule 必须有对应的 semantic test（语义测试）
- 每个 test 必须有对应的 fixture（测试用例）
- 每个 fixture 必须可追溯到真实项目场景
- 修复必须落地为 runtime code / gate / validator / writer constraint
- 不能只停留在 Markdown / YAML / 文档

---

## 5. 四批次执行路线

### Batch A：资源准备 + 缺陷映射 + 阶段接口图
- 前期资料准备（Asset Preparation Spec 定义的 10 个资源包）
- 10 类缺陷拆解为 defect classes
- 12 阶段接口图（依赖、回流、human gate）
- 技能与工具缺口分析
- **验收：** 所有资源包就位；10 defect classes 完成映射；12 阶段接口关系明确

### Batch B：检索 / 筛选 / 临床数据提取
- 检索可复现性（检索词记录、检索策略审计）
- 文献筛选规则实现（样本量阈值、时间范围、排除原因编码）
- PMID 溯源验证实现
- 全文可用性验证实现
- Denominator/subgroup 区分实现
- **验收：** 4 个新 gate/validator 实现并通过 semantic tests

### Batch C：Endpoint / Benchmark / Equivalence / Claim-Evidence / PMCF / BR-GSPR
- Endpoint 语义分类器
- Comparator benchmark 完整性
- SOTA accounting 一致性
- 跨章节 endpoint 一致性
- Claim-evidence strength 传播
- **验收：** 5 个 semantic validators 实现并通过 fixture-driven tests

### Batch D：Reasoning Integration / Writer Semantic QA / Real Project Validation
- 专家推理整合（所有 Batch B+C 组件接入 G42/G43/G46）
- Writer semantic QA gate（输出前后一致性检查）
- 真实项目复验（至少 1 个项目跑完整链路）
- Regression lock（所有 BIGDP2026.6 tests + 新 tests 全部 pass）
- **验收：** 端到端 dry-run 通过；10 类工程师反馈问题逐项复验不再出现

---

## 6. 停止条件

每个批次有独立停止条件。全局停止条件：
- 任何批次连续 3 次验收不通过 → STOP，Controller review
- 发现需要架构重写（>500 行改动触及 graph 核心路由）→ STOP
- Expert labels 不可得导致规则无法归纳 → STOP，标记 UNKNOWN，记录依赖
- Full-text 不可得导致 gold set 无法建立 → 仅做 partial validation，标记局限性

---

## 7. 风险

| 风险 | 缓解 |
|:---|:---|
| 工程师反馈样本量不足（10 个问题来自有限项目） | 归纳为 defect classes 而非单点修复；同类问题可泛化 |
| Full-text 获取依赖外部条件 | 区分 "全文可得" 和 "摘要可得" 两条验证路径 |
| Expert labels 需要法规专家时间 | 先做 rule-based 自动分类，human labels 用于校准和 hard cases |
| 本轮新增 gate 可能影响 pipeline 速度 | 新 gate 设计为 lightweight deterministic checks，不做 LLM 调用 |
