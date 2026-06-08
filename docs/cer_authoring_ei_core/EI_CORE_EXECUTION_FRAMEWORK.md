# EI CORE EXECUTION FRAMEWORK

> CCD 签发 | 2026-05-13 | Authoritative — Codex + Claude CLI Audit Contract

## 一、执行总图

```text
Phase 0: Readiness Check (不改代码)
  → Phase 1: EI-1 (Evidence Scoring + Admissibility)
  → Phase 2: EI-2~4 (Claim Reasoning + Absence + Synthesis + Bridging)
  → Phase 3: EI-5~7 (SOTA + BR + PMCF)
  → Phase 4: EI-8~9 (Crosswalk + Audit Ledger + Human Review + Validation Harness)
  → Phase 5: Full Regression + Closeout
```

每阶段是硬门控。Phase 0 PASS 才授权 Phase 1。每阶段 closeout 为 PASS 或 PASS_WITH_NONBLOCKING_RISK 才进入下一阶段。不得跳过。不得并行。

---

## 二、角色分工

| 角色 | 职责 | 限制 |
|---|---|---|
| **Codex** | 实现。读 spec → 写代码 → 跑测试 → 写 artifacts → 调 Claude audit → 修复 Class B → closeout | 不改 graph/gates/agents。不做 broad refactor。不跳过 phase gate。 |
| **Claude CLI** | 审计。读 manifest + spec + diff + test output → 分类判定 PASS/FAIL_REPAIRABLE/FAIL_BLOCKING | 不实现。不改代码。不扩大 scope。不输出代码。 |
| **CCD (Controller)** | 审阅 closeout。判定 phase gate。授权下一阶段。处理 Class A STOP。 | 不实现。不修改 Codex 或 Claude 的输出。 |

---

## 三、Phase 0 — Readiness Check

### 目标

不改代码。验证所有 EI Core 资产就绪。任一失败即 STOP。

### 必须验证

| # | Check | 证据 |
|---|---|---|
| P0-1 | `CER_RMF_EVIDENCE_INTELLIGENCE_CORE_MASTER_PLAN.md` 存在且无 stale 引用 | 无 17/19 spec 引用，无 220 tests 引用，无 pipeline/state/artifacts 路径固定 |
| P0-2 | `PHASE_MANIFEST.md` 存在且 owner-approved | Phase Manifest 定义全部 phase |
| P0-3 | 20 EI Core spec files 全部存在 | 20 个 spec 文件名与 Master Plan §九一致 |
| P0-4 | `RELEASE_EVIDENCE_PACK_INDEX.md` 存在 | V2 证明 |
| P0-5 | `V3_CORE_IMPLEMENTATION_PROOF_INDEX.md` 存在且与 repo 事实一致 | V3-Core Batch 7.1-7.6 证明 |
| P0-6 | `SPIRAL_ARCHITECTURE_IMPLEMENTATION_PROOF_INDEX.md` 存在 | Spiral Architecture 证明 |
| P0-7 | Baseline 165 tests 全部通过 | `pytest -q` → 165 passed, 0 failed |
| P0-8 | graph.py / gates.py / agents.py 未修改 | `git diff` against baseline |
| P0-9 | G42/G46/pre_writer_readiness 可消费 EI outputs 或 manifest 标记 staged-only | PHASE_MANIFEST §Staged-Only Outputs Registry |
| P0-10 | Validation counts 同步：24 cases (8+8+8)，≥209 tests total | 跨 Master Plan, Codex Batch, Pre-Pilot, Validation Harness 一致 |
| P0-11 | PHASE_MANIFEST 包含 5 阶段（Phase 0-5）分组 | Phase 0 → Phase 1 (EI-1) → Phase 2 (EI-2~4) → Phase 3 (EI-5~7) → Phase 4 (EI-8~9) → Phase 5 (Validation) |

### Phase 0 Artifacts

写入 `artifacts/upgrade_validation/PHASE-0/`：
- `phase_intake.md` — 本阶段输入摘要
- `BASELINE_GIT_STATUS.txt` — `git status` 输出
- `BASELINE_DIFF.patch` — `git diff` 输出
- `changed_files.txt` — Phase 0 中创建/修改的文件
- `forbidden_file_diff_check.txt` — graph/gates/agents 零 diff 确认
- `readiness_check_result.txt` — P0-1 到 P0-11 逐项结果
- `proof_index_check.txt` — 三个证明索引存在性确认
- `route_integration_check.txt` — G42/G46 staged-only 确认
- `full_regression_result.txt` — `pytest -q` 输出
- `claude_audit_round_1.md` — Claude CLI 审计报告
- `LOOP_STATE.json` — 执行状态
- `phase_closeout.md` — 包含 readiness matrix

### Phase 0 Closeout 判定

| 结果 | 条件 | 下一动作 |
|---|---|---|
| **PASS** | 全部 P0-1 ~ P0-11 通过 | 授权 Phase 1 |
| **PASS_WITH_NONBLOCKING_RISK** | 仅 Class C issues | 授权 Phase 1，记录 risks |
| **FAIL_BLOCKING** | 任一 P0-x 失败 | STOP。报告 owner。不进入 Phase 1。 |

---

## 四、Phase 1 — EI-1 (Evidence Scoring + Admissibility)

### 依赖
Phase 0 PASS

### Specs
- `EVIDENCE_SCORING_MODEL_SPEC.md`
- `REGULATORY_EVIDENCE_ADMISSIBILITY_SPEC.md`
- `SCORING_CALIBRATION_AND_THRESHOLD_POLICY.md`

### Allowed Scope
六因子证据评分、监管可采信性矩阵、provisional 阈值。确定性规则，非 LLM。

### Forbidden Scope
graph.py / gates.py / agents.py。将评分称为 certification。将阈值硬编码为 stable。broad refactor。

### 输出（写入 state）
- evidence_registry 扩展：`evidence_strength_score`, `evidence_quality_tier`, `score_calibration_status`, `calibration_required`, `admissibility_level`, `admissibility_rationale`

### Downstream 消费证明
这些输出标记为 **staged-only**。Phase 2 (Claim Reasoning) 将消费它们。Phase 1 closeout 必须声明消费路径。

### Tests (6 new)
- subject RCT → excellent tier + ADMISSIBLE
- competitor → ≤marginal + NOT_ADMISSIBLE for safety
- data quality boundaries (n=29 vs n=30)
- factor weight sum = 1.0
- admissibility CONDITIONAL with condition check
- calibration_required = true, score_calibration_status = provisional

### Phase 1 Artifacts

写入 `artifacts/upgrade_validation/PHASE-1/`：
- `phase_intake.md`
- `changed_files.txt`
- `forbidden_file_diff_check.txt`
- `targeted_test_result.txt`
- `full_regression_result.txt`
- `downstream_consumption_check.txt`
- `claude_audit_round_<n>.md`
- `LOOP_STATE.json`
- `phase_closeout.md`（含 spec coverage matrix）

---

## 五、Phase 2 — EI-2~4 (Claim Reasoning + Absence + Synthesis + Bridging)

### 依赖
Phase 1 PASS

### Specs
- `DEVICE_CLAIM_REASONING_SPEC.md`
- `CLAIM_CONCLUSION_STRENGTH_SPEC.md`
- `ABSENCE_OF_EVIDENCE_REASONING_SPEC.md`
- `EVIDENCE_SYNTHESIS_METHOD_POLICY.md`
- `EQUIVALENCE_SIMILARITY_BRIDGING_SPEC.md`

### Allowed Scope
Required source profiles + override rules (downgrade→gap 耦合)。7 类缺失证据推理。三种合成方法选择。四种设备关系桥接推理。

### Forbidden Scope
graph.py / gates.py / agents.py。降级不产生 gap/limitation/PMCF/cap。Competitor 证据桥接到 subject device claims。缺失证据→声称"安全"。冲突静默平均。

### 输出
- `claim_support_matrix`
- `writer_conclusion_constraints`
- evidence_registry 扩展：`absence_category`, `absence_reasoning_output`, `bridging_assessment`
- `synthesis_method_selections`

### Downstream 消费
staged-only。Phase 3 (SOTA/BR/PMCF) 消费 claim_support。Phase 4 gate bridge 消费 conclusion_constraints。

### Tests (16 new: 6+6+4)
EI-2: 6 tests。EI-3: 6 tests。EI-4: 4 tests。

---

## 六、Phase 3 — EI-5~7 (SOTA + BR + PMCF)

### 依赖
Phase 2 PASS

### Specs
- `SOTA_BENCHMARK_SYNTHESIS_SPEC.md`
- `BENEFIT_RISK_REASONING_SPEC.md`
- `PMCF_GAP_REASONING_SPEC.md`

### Allowed Scope
5 维度可比性 SOTA 基准。BR 推理 + 不确定性折价。6 种 PMCF gap 触发 + 严重度。

### Forbidden Scope
graph.py / gates.py / agents.py。无可比性检查的 benchmark。BR 证据不足时声称 favorable。自动填充 PMCF 细节。

### 输出
- `sota_benchmark_table`（含 excluded_studies, comparability_assessment）
- `benefit_risk_conclusion`
- `pmcf_gap_register`

### Downstream 消费
staged-only。Phase 4/5 gate bridge 消费。Writer 通过 conclusion constraints 消费。

### Tests (12 new: 4+4+4)

---

## 七、Phase 4 — EI-8~9 (Crosswalk + Audit + Human Review + Validation)

### 依赖
Phase 3 PASS

### Specs
- `CER_RMF_EVIDENCE_CROSSWALK_SPEC.md`
- `REASONING_AUDIT_LEDGER_SPEC.md`
- `EVIDENCE_INTELLIGENCE_HUMAN_REVIEW_PACKET_SPEC.md`
- `EVIDENCE_INTELLIGENCE_VALIDATION_HARNESS_SPEC.md`

### Allowed Scope
CER/RMF crosswalk (可追溯性+一致性)。推理审计台账（全链路 trace）。Tier 1/2/3 人工审查包。24-case 验证框架。**Gate signal bridge** (`_build_ei_gate_signals()` per Option C)：将 EI outputs 转换为 G46 可读信号。

### Forbidden Scope
graph.py / gates.py / agents.py。合并 CER/RMF 判断。Tier 3 不阻塞。审计缺少源头 trace。

### 输出
- `cer_rmf_crosswalk_table`
- `reasoning_audit_ledger`
- `human_review_packet`
- Gate signals → G46

### Downstream 消费
Gate signals → G46 必须在此阶段证明可消费。如不可 → FAIL_BLOCKING。

### Tests (10 new: 4+6)

---

## 八、Phase 5 — Validation Harness + Full Closeout

### 依赖
Phase 4 PASS

### 必须验证
- 24-case harness 完整执行（8 positive + 8 negative + 8 boundary）
- 全部 8 个负向/对手案例 (N1-N8) 通过
- Full regression ≥209 tests 通过
- 全部 Phase 1-4 closeouts present
- 全部 Class B issues closed 或 owner-reviewed
- 仅 Class C risks 剩余
- 无 forbidden file diff
- 全部 operational EI output claims 有 downstream consumption proof

### 不做
不声称完成（除非 Phase 5 final audit PASS）。不合并 Phase 0-4 的文档。不启动 pilot。

### Phase 5 Artifacts

写入 `artifacts/upgrade_validation/PHASE-5/`：
- 全部 Phase 1-4 closeout 汇总
- 24-case harness 执行报告
- Full regression 最终结果
- Spec coverage matrix（跨全部 20 spec）
- Final Claude audit

---

## 九、Claude CLI Audit Contract

### 审计输入

每次 audit，Claude CLI 接收：
- 当前 phase 的 manifest 条目
- 相关 spec 文件路径
- `git diff --stat` against Phase 0 baseline
- `git diff --name-only` against Phase 0 baseline
- forbidden file diff check
- targeted test output
- full regression output
- artifact list
- downstream consumption proof 或 staged-only labels
- unresolved prior risks
- 当前 `LOOP_STATE.json`

### 审计输出

| 判定 | 含义 | 处理 |
|---|---|---|
| **PASS** | 全部 spec items 实现，全部 tests 通过，全部 artifacts 存在，无 forbidden diff | Phase closeout → 下一阶段 |
| **PASS_WITH_NONBLOCKING_RISK** | 同上，但有 Class C issues（文档改善、可选增强） | 记录 Class C → Phase closeout → 下一阶段 |
| **FAIL_REPAIRABLE** | 有可修复问题（test 失败、artifact 缺失、spec item 遗漏） | Class B → 最多 3 轮修复 → 重新 audit |
| **FAIL_BLOCKING** | Class A 问题（forbidden file 修改、评分称为 certification、competitor 证据误用、冲突静默平均、G46 无法消费） | STOP → 报告 owner |
| **AUDIT_INCONCLUSIVE** | Claude 无法做出明确判定（输入不完整、歧义） | Class B → 补充信息 → 最多 3 轮 |

### 不得
- Claude CLI 不得实现代码
- Claude CLI 不得修改文件
- Claude CLI 不得扩大 audit scope
- Claude CLI 不得输出代码建议

---

## 十、Failure Classes

### Class A — HARD STOP（不可修复，立即停止）

- pre-implementation baseline tests fail
- forbidden files modified (graph/gates/agents)
- evidence_registry bypass
- Writer boundary bypass
- scoring treated as certification
- competitor/similar evidence misuse (bridged to subject device claims)
- critical conflict silently averaged
- EI outputs cannot reach gates/downstream AND not marked staged-only

**处理**：立即 STOP。写 `STOP_REASON`。报告 owner。不进入下一阶段。

### Class B — REPAIR REQUIRED（可修复，最多 3 轮）

- post-implementation targeted test failure
- full regression failure
- spec item missing
- test coverage incomplete
- audit checklist incomplete
- artifact missing
- AUDIT_INCONCLUSIVE

**处理**：修复 → 重新 audit。最多 3 轮。3 轮仍失败 → STOP with `BLOCKED_OWNER_REVIEW_REQUIRED`。

### Class C — CARRY-FORWARD（记录但不阻塞）

- documentation improvement
- nonblocking audit note
- optional enhancement outside current phase

**处理**：写入 unresolved risks → phase closeout → 进入下一阶段。

---

## 十一、LOOP_STATE.json Schema

```json
{
  "execution_id": "EI_CORE_2026-05-13",
  "last_successful_phase": "PHASE_0",
  "current_phase": "PHASE_1",
  "current_repair_round": 0,
  "max_repair_rounds": 3,
  "stop_reason": null,
  "resume_command": "Continue from PHASE_1 with Claude audit round 1",
  "baseline_commit": "<git rev-parse HEAD>",
  "baseline_test_count": 165,
  "phases_completed": ["PHASE_0"],
  "unresolved_class_c_risks": [],
  "last_updated": "2026-05-13T00:00:00Z"
}
```

---

## 十二、每阶段标准流程

```text
1. Read: manifest, specs, prior phase closeout, unresolved risks
   → Write phase_intake.md
2. Update LOOP_STATE.json
3. Implement (allowed scope only)
4. Write changed_files.txt (vs Phase 0 baseline)
5. Write forbidden_file_diff_check.txt (graph/gates/agents MUST be empty)
6. Run targeted tests → targeted_test_result.txt
7. Run full regression → full_regression_result.txt
8. Prove downstream consumption or mark staged-only → downstream_consumption_check.txt
9. Run Claude CLI audit → claude_audit_round_<n>.md
10. If FAIL_REPAIRABLE or AUDIT_INCONCLUSIVE:
    Repair → goto 4 (max 3 rounds)
11. If PASS or PASS_WITH_NONBLOCKING_RISK:
    Write phase_closeout.md (含 spec coverage matrix)
12. STOP. Await owner authorization for next phase.
```

---

## 十三、Spec Coverage Matrix (per phase_closeout.md)

```text
| spec_file | spec_item | implemented | test_name | artifact | audit_result | unresolved_risk |
|---|---|---|---|---|---|---|
每个 phase 的 closeout 必须包含此矩阵，覆盖该 phase 的全部 spec items。
```

---

## 十四、全局禁止

- graph.py / gates.py / agents.py 修改
- LLM-based 推理（所有规则确定性）
- 事实置信度自动提升
- 冲突静默平均
- 缺失证据→声称安全/有效
- Competitor 证据→subject device claims
- 评分为 certification / regulatory-grade
- Pilot 恢复
- Broad refactor / formatting sweep / dependency overhaul

---

## 十五、资产索引

所有文件位于：
```
/Users/winstonwei/Documents/Playground/deer-flow/docs/cer_authoring_ei_core/
```

| 类型 | 文件 |
|---|---|
| **Master Plan** | `CER_RMF_EVIDENCE_INTELLIGENCE_CORE_MASTER_PLAN.md` |
| **Phase Manifest** | `PHASE_MANIFEST.md` |
| **Execution Framework** | `EI_CORE_EXECUTION_FRAMEWORK.md`（本文件） |
| **Codex Batch Plan** | `CODEX_BATCH_PLAN_DRAFT_EI_CORE.md` |
| **Pre-Pilot Criteria** | `PRE_PILOT_EI_CORE_VALIDATION_CRITERIA.md` |
| **20 EI Core Specs** | `CLINICAL_FACT_LAYER_FINAL_SCOPE.md` 等 20 文件 |
| **Proof Indexes** | `RELEASE_EVIDENCE_PACK_INDEX.md`, `V3_CORE_IMPLEMENTATION_PROOF_INDEX.md`, `SPIRAL_ARCHITECTURE_IMPLEMENTATION_PROOF_INDEX.md` |
| **I/O Contract** | `REASONING_INPUT_OUTPUT_CONTRACT_SPEC.md` |

---

*CCD 签发：2026-05-13 | Codex Execution + Claude CLI Audit Contract*
