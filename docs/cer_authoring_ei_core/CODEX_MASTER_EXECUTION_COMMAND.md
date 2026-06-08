# CODEX MASTER EXECUTION COMMAND — EI Core Full Upgrade

> CCD 签发 | 2026-05-13 | v3 — Complete file usage guide

---

## 执行模式

**一条指令。Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5，闭环一次性到底。**

Phase 之间不等待。Class B 自动修复（最多 3 轮）。Class C 记录后继续。**只有 Class A 才 STOP。**

---

## 一、文件地图：27 个文件，分类使用

所有文件在此目录：

```
/Users/winstonwei/Documents/Playground/deer-flow/docs/cer_authoring_ei_core/
```

### A 类 — 总控文件（先读，每个 Phase 都参考）

| # | 文件名 | 读它做什么 | 何时读 |
|---|---|---|---|
| 1 | `EI_CORE_EXECUTION_FRAMEWORK.md` | **入口。** 5 阶段完整定义、每阶段标准 9 步流程、Claude 审计契约（输入/输出格式）、Failure Class A/B/C 判定、LOOP_STATE.json schema、Spec Coverage Matrix 格式 | 开始前读一次。每阶段开始前回顾该阶段的 §。 |
| 2 | `PHASE_MANIFEST.md` | **权限表。** 每阶段的 allowed_scope、forbidden_scope、dependent specs、test count、audit checklist、hard_stop_conditions、staged-only 声明、downstream consumption expectation | 每阶段 Intake 时读该阶段的条目 |
| 3 | `CODEX_MASTER_EXECUTION_COMMAND.md` | **本文件。** 闭环总指令 | 开始前读一次 |

### B 类 — 架构与规则（全局参考，所有 Phase 遵守）

| # | 文件名 | 读它做什么 | 何时读 |
|---|---|---|---|
| 4 | `CER_RMF_EVIDENCE_INTELLIGENCE_CORE_MASTER_PLAN.md` | 五层架构、12 条 Hard Boundaries、推理链 6 步、集成点矩阵 | 开始前读一次。遇到边界问题时回查。 |
| 5 | `REASONING_INPUT_OUTPUT_CONTRACT_SPEC.md` | **字段字典。** 每个 EI 输出的精确字段名、类型、来源、消费方。实现时必须对齐此文件的字段名，不得自创。 | Phase 1-4 实现前必读。写入 state 字段时对照。 |
| 6 | `CLINICAL_FACT_LAYER_FINAL_SCOPE.md` | Fact Layer 边界。明确什么归 fact 层、什么归推理层。 | Phase 1 实现前读。确保不绕过 evidence_registry。 |

### C 类 — 阶段 Specs（按 Phase 读取，实现依据）

**Phase 1 — EI-1 (Evidence Scoring + Admissibility)**

| # | 文件名 | 内容 |
|---|---|---|
| 7 | `EVIDENCE_SCORING_MODEL_SPEC.md` | 六因子加权评分公式、quality tier 映射、score_calibration_status、calibration_required |
| 8 | `REGULATORY_EVIDENCE_ADMISSIBILITY_SPEC.md` | 16 source_type × 4 claim_type 可采信性矩阵、MDR Annex X 要求、条件说明 |
| 9 | `SCORING_CALIBRATION_AND_THRESHOLD_POLICY.md` | 阈值是 heuristic baseline、calibration mandatory before pilot、校准方法 |

**Phase 2 — EI-2~4 (Claim Reasoning + Absence + Synthesis + Bridging)**

| # | 文件名 | 内容 |
|---|---|---|
| 10 | `DEVICE_CLAIM_REASONING_SPEC.md` | Required source profiles（默认基线）+ override 规则（downgrade→gap 耦合）+ claim_support_level 判定 |
| 11 | `CLAIM_CONCLUSION_STRENGTH_SPEC.md` | 四级结论强度（STRONG/MODERATE/CAUTIOUS/INSUFFICIENT）+ Writer 措辞硬约束 + quantitative_allowed |
| 12 | `ABSENCE_OF_EVIDENCE_REASONING_SPEC.md` | 7 种缺失证据类别 + 每类可说什么/不可说什么/结论上限/PMCF 触发/human review tier |
| 13 | `EVIDENCE_SYNTHESIS_METHOD_POLICY.md` | 3 种合成方法（benchmark/narrative/none）+ 选择流程 + 禁止事项 |
| 14 | `EQUIVALENCE_SIMILARITY_BRIDGING_SPEC.md` | 4 种设备关系桥接推理 + 结论强度上限 + bridging_assessment 输出 |

**Phase 3 — EI-5~7 (SOTA + BR + PMCF)**

| # | 文件名 | 内容 |
|---|---|---|
| 15 | `SOTA_BENCHMARK_SYNTHESIS_SPEC.md` | 5 维度可比性检查（Step 0）+ benchmark 计算 + benchmark_confidence + excluded_studies |
| 16 | `BENEFIT_RISK_REASONING_SPEC.md` | BR 推理 5 步 + br_acceptability_confidence + 不确定性折价 + 禁止事项 |
| 17 | `PMCF_GAP_REASONING_SPEC.md` | 6 种 gap 触发条件 + gap_severity 判定 + PMCF objective 模板（不自动填充细节） |

**Phase 4 — EI-8~9 (Crosswalk + Audit + Human Review + Validation)**

| # | 文件名 | 内容 |
|---|---|---|
| 18 | `CER_RMF_EVIDENCE_CROSSWALK_SPEC.md` | 6 种 crosswalk 链接 + mismatch 处理 + link_nature: traceability/consistency（不合并判断） |
| 19 | `REASONING_AUDIT_LEDGER_SPEC.md` | audit_entry 结构 + 每步审计要求 + 可追溯性验证 |
| 20 | `EVIDENCE_INTELLIGENCE_HUMAN_REVIEW_PACKET_SPEC.md` | Tier 1/2/3 触发条件 + decision_options + 人工决策后流转 |
| 21 | `EVIDENCE_INTELLIGENCE_VALIDATION_HARNESS_SPEC.md` | 24 案例定义（8 positive + 8 negative + 8 boundary）+ N1-N8 详细预期 |

### D 类 — 批次计划与验收标准

| # | 文件名 | 内容 | 何时读 |
|---|---|---|---|
| 22 | `CODEX_BATCH_PLAN_DRAFT_EI_CORE.md` | 每个 EI batch 的 PROBLEM/GOAL/BOUNDARY/ACCEPTANCE/STOP_CONDITION。**注意**：此文件是参考，BOUNDARY 以 PHASE_MANIFEST 为准，tests 数量以本指令为准。 | Phase 1-4 实现前对照 |
| 23 | `PRE_PILOT_EI_CORE_VALIDATION_CRITERIA.md` | Phase 5 验收的 6 个 MUST 条件 + V3 生产级验证阻塞项 + CAL-001 重跑标准 | Phase 5 执行前读 |

### E 类 — 证明索引（Phase 0 验证用，Phase 1-5 不读）

| # | 文件名 | 证明什么 |
|---|---|---|
| 24 | `RELEASE_EVIDENCE_PACK_INDEX.md` | V2 Evidence Chain 已实现（5-project calibration + holdout） |
| 25 | `V3_CORE_IMPLEMENTATION_PROOF_INDEX.md` | V3-Core Toolchain 已实现（Batch 7.1-7.6, 165 tests, graph/gates/agents untouched） |
| 26 | `SPIRAL_ARCHITECTURE_IMPLEMENTATION_PROOF_INDEX.md` | Spiral Architecture 已实现（16 criteria, CAL-001 runtime proven） |

### F 类 — Phase 0 产物（Phase 0 重跑时覆盖写入）

| # | 文件名 | 说明 |
|---|---|---|
| 27 | `PHASE_0_EI_CORE_READINESS_REPORT.md` | 上次 Phase 0 的 CCD 就绪报告。重跑时参考但不依赖——Codex 应独立验证。 |

---

## 二、文件读取顺序（按 Phase）

### 开始之前（一次性读完）

```
第 1 步：读 EI_CORE_EXECUTION_FRAMEWORK.md（全部）
第 2 步：读 PHASE_MANIFEST.md（全部，了解全局）
第 3 步：读 CER_RMF_EVIDENCE_INTELLIGENCE_CORE_MASTER_PLAN.md（架构 + 12 Hard Boundaries）
第 4 步：读 REASONING_INPUT_OUTPUT_CONTRACT_SPEC.md（字段字典，实现时对照）
```

### Phase 0 — 重跑 Readiness Check

```
读：EI_CORE_EXECUTION_FRAMEWORK.md §三（Phase 0 详细定义）
读：PHASE_MANIFEST.md §PHASE_0（checklist + hard_stop_conditions）
读：CER_RMF_EVIDENCE_INTELLIGENCE_CORE_MASTER_PLAN.md（确认无 stale 引用）
读：3 个 proof index 文件（确认存在）
```

**注意**：Phase 0 上次 closeout = FAIL_BLOCKING。4 项文档问题已被 CCD 修复（stale "20 案例"→"24 案例"、pipeline 路径固定→problem/goal 格式、manifest spec 计数补齐、PHASE_0_EI_CORE_READINESS_REPORT.md 已复制）。本次重跑预期全部 11 项 PASS。上次的 artifacts 可覆盖写入。

### Phase 1 — EI-1

```
读：EI_CORE_EXECUTION_FRAMEWORK.md §四（Phase 1 详细定义）
读：PHASE_MANIFEST.md §Implementation Phase 1（allowed/forbidden scope + tests + checklist）
读：EVIDENCE_SCORING_MODEL_SPEC.md（六因子公式、tier 映射）
读：REGULATORY_EVIDENCE_ADMISSIBILITY_SPEC.md（16×4 矩阵、条件）
读：SCORING_CALIBRATION_AND_THRESHOLD_POLICY.md（heuristic baseline + calibration mandatory）
实现时对照：REASONING_INPUT_OUTPUT_CONTRACT_SPEC.md（字段名必须对齐）
```

### Phase 2 — EI-2~4

```
读：EI_CORE_EXECUTION_FRAMEWORK.md §五
读：PHASE_MANIFEST.md §Implementation Phase 2
读：DEVICE_CLAIM_REASONING_SPEC.md + CLAIM_CONCLUSION_STRENGTH_SPEC.md（EI-2）
读：ABSENCE_OF_EVIDENCE_REASONING_SPEC.md + EVIDENCE_SYNTHESIS_METHOD_POLICY.md（EI-3）
读：EQUIVALENCE_SIMILARITY_BRIDGING_SPEC.md（EI-4）
实现时对照：I/O Contract
```

### Phase 3 — EI-5~7

```
读：EI_CORE_EXECUTION_FRAMEWORK.md §六
读：PHASE_MANIFEST.md §Implementation Phase 3
读：SOTA_BENCHMARK_SYNTHESIS_SPEC.md（EI-5）
读：BENEFIT_RISK_REASONING_SPEC.md（EI-6）
读：PMCF_GAP_REASONING_SPEC.md（EI-7）
实现时对照：I/O Contract
```

### Phase 4 — EI-8~9

```
读：EI_CORE_EXECUTION_FRAMEWORK.md §七
读：PHASE_MANIFEST.md §Implementation Phase 4
读：CER_RMF_EVIDENCE_CROSSWALK_SPEC.md + REASONING_AUDIT_LEDGER_SPEC.md（EI-8）
读：EVIDENCE_INTELLIGENCE_HUMAN_REVIEW_PACKET_SPEC.md + EVIDENCE_INTELLIGENCE_VALIDATION_HARNESS_SPEC.md（EI-9）
实现时对照：I/O Contract
```

### Phase 5 — Closeout

```
读：EI_CORE_EXECUTION_FRAMEWORK.md §八
读：PHASE_MANIFEST.md §PHASE_PILOT_VALIDATION
读：PRE_PILOT_EI_CORE_VALIDATION_CRITERIA.md
执行：24-case harness
```

---

## 三、每阶段标准 9 步（无例外）

```
Step 1: INTAKE
  读 Framework 当前 Phase § + Manifest 当前 Phase + 该 Phase 全部 Specs
  → 写 artifacts/upgrade_validation/PHASE-X/phase_intake.md

Step 2: STATE
  → 更新 LOOP_STATE.json（current_phase, repair_round=0）

Step 3: IMPLEMENT
  在 allowed_scope 内实现。遵守 forbidden_scope。
  不改 graph.py / gates.py / agents.py。
  实现位置由你根据 repo 实际结构选择。
  所有推理必须是确定性规则，不是 LLM prompt。

Step 4: CHANGED FILES
  → 写 changed_files.txt
  → 写 forbidden_file_diff_check.txt（graph/gates/agents 必须为空 diff）

Step 5: TEST
  → targeted tests → targeted_test_result.txt
  → full regression → full_regression_result.txt
  Baseline 165 tests 必须继续通过。

Step 6: DOWNSTREAM CHECK
  → 写 downstream_consumption_check.txt
  证明输出被后续 phase 消费 OR 标记 staged-only + 声明消费路径

Step 7: CLAUDE AUDIT
  调 Claude CLI 审计。
  输入：
    - Framework 当前 Phase §
    - Manifest 当前 Phase 条目
    - 该 Phase 全部 Spec 内容或路径
    - git diff --stat（against Phase 0 baseline）
    - forbidden_file_diff_check.txt
    - targeted_test_result.txt
    - full_regression_result.txt
    - downstream_consumption_check.txt
    - 上次 closeout 的 unresolved risks（如有）
    - LOOP_STATE.json
  Claude 输出：PASS / PASS_WITH_NONBLOCKING_RISK / FAIL_REPAIRABLE / FAIL_BLOCKING / AUDIT_INCONCLUSIVE

Step 8: REPAIR（如需要）
  FAIL_REPAIRABLE 或 AUDIT_INCONCLUSIVE → 修复 → 回到 Step 4（最多 3 轮）
  3 轮仍失败 → STOP with BLOCKED_OWNER_REVIEW_REQUIRED

Step 9: CLOSEOUT
  PASS 或 PASS_WITH_NONBLOCKING_RISK →
  → 写 phase_closeout.md（含 spec coverage matrix）
  → 更新 LOOP_STATE.json（last_successful_phase）
  → 进入下一 Phase
```

---

## 四、Claude CLI 审计怎么调

**每次审计是独立调用。** 给 Claude CLI 以下完整输入包：

```
审计 Phase [X] — EI Core Upgrade

请审计以下实现，输出判定：PASS / PASS_WITH_NONBLOCKING_RISK / FAIL_REPAIRABLE / FAIL_BLOCKING / AUDIT_INCONCLUSIVE

【Phase 定义】
[粘贴 EI_CORE_EXECUTION_FRAMEWORK.md 当前 Phase 的完整 §]

【Manifest 条目】
[粘贴 PHASE_MANIFEST.md 当前 Phase 的完整条目]

【Specs】
[粘贴该 Phase 全部 spec 文件内容，或指定路径让 Claude 读取]

【变更】
[粘贴 git diff --stat 输出]
[粘贴 forbidden_file_diff_check.txt 内容]

【测试】
[粘贴 targeted_test_result.txt]
[粘贴 full_regression_result.txt]

【下游消费】
[粘贴 downstream_consumption_check.txt]

【上次遗留风险】
[如有，粘贴]

【执行状态】
[粘贴 LOOP_STATE.json]

判定标准：
- PASS: 全部 spec items 实现 + 全部 tests 通过 + 全部 artifacts 存在 + 无 forbidden diff
- PASS_WITH_NONBLOCKING_RISK: 同上，仅有 Class C issues
- FAIL_REPAIRABLE: test 失败 / artifact 缺失 / spec item 遗漏（可修复）
- FAIL_BLOCKING: 评分称为 certification / competitor 证据误用 / 冲突静默平均 / G46 无法消费 / graph|gates|agents 被修改
- AUDIT_INCONCLUSIVE: 信息不足无法判定
```

---

## 五、Failure 速查

| Class | 触发条件 | 处理 |
|---|---|---|
| **A** | graph/gates/agents 被修改、baseline tests 失败、scoring 称为 certification、competitor evidence→subject device claims、冲突静默平均、G46 无法消费且非 staged-only | **立即 STOP。** 写 STOP_REASON 到 LOOP_STATE.json。报告 owner。 |
| **B** | test 失败、artifact 缺失、spec item 遗漏、AUDIT_INCONCLUSIVE | 自动修复 → 重新 audit。最多 3 轮。3 轮仍失败 → STOP。 |
| **C** | 文档改善、非阻塞建议 | 记录到 unresolved risks → 继续 |

---

## 六、全局禁止

- `graph.py` / `gates.py` / `agents.py` 任何修改
- LLM 做推理判断（所有规则必须是确定性计算，不是 prompt-based）
- 事实置信度自动提升
- 冲突静默平均
- 缺失证据 → 声称"安全"或"有效"
- Competitor 证据 → subject device 的 safety/performance 声明
- 评分称为 certification / regulatory-grade / validated
- Broad refactor / formatting sweep / dependency overhaul / repo cleanup
- 跳过 Phase gate
- Phase 5 final audit PASS 前声称"完成"
- Pilot 恢复

---

## 七、最终目标

```
Phase 5 closeout:
  ≥209 tests passed (165 baseline + 44 new)
  24 validation cases: 8/8 positive + 8/8 negative + 8/8 boundary = 100%
  Phase 1-4 closeouts: all present + all PASS
  0 Class A issues
  0 unresolved Class B issues
  graph/gates/agents: 0 lines changed (all phases)
  20-spec coverage matrix: complete
```

---

*CCD 签发：2026-05-13 | v3 — Complete file usage guide*
