# V3 — Batch F: Semantic Support + Equivalence

**Target:** Upgrade 2 (Semantic Claim-Evidence Validator) + Upgrade 3 (Equivalence Runtime Gate)
**Stages:** S7 (equivalence), S8 (claim-evidence), G43/G46
**Current Scores:** S7: 70 → 80, S8: 82 → 88
**Execution Order:** F0 (atomic claims) → F1 (equivalence route) → F2 (semantic validator) → F3 (equivalence gate)

---

## F0 — Atomic Claim Decomposition（NEW）

**法规问题：** "The device is safe and effective for rapid hemorrhage control in emergency settings" 不是一条 claim——至少包含 safety、effectiveness、hemorrhage control、emergency context 四条。

语义支持验证前，必须先把复合 claim 拆成 atomic claims。

| Field | Values |
|:---|:---|
| atomic_claim_id | unique per decomposed claim |
| claim_dimension | safety / performance / clinical_benefit / usability / indication / population / comparator / BR |
| required_evidence_type | direct_clinical / indirect_supporting / equivalent_device / manufacturer_bench / PMS / expert_consensus |
| required_endpoint | 该 atomic claim 需要的 endpoint 类型 |
| minimum_support_strength | strong / moderate / limited / contextual_only |

**集成：** Claim decomposition node 在 claim_decomposition (S2) 之后、G43 之前。G43 对每个 atomic claim 单独验证语义支持。CER_REASONING_LEDGER 记录每 atomic claim 的支持结论。

**Tests:**
- [ ] Compound claim "safe and effective" → decomposed to ≥2 atomic claims
- [ ] Safety claim requires safety endpoint evidence
- [ ] Population claim requires population-match evidence
- [ ] Each atomic claim has required_evidence_type non-null

## F1 — Equivalence Route Decision（NEW）

**法规问题：** 本项目是否允许主张 equivalence？

在检查三维比较之前，先判断 equivalence route。

| Value | Meaning |
|:---|:---|
| equivalence_claimed | 允许且已主张 |
| equivalence_not_claimed | 不主张等效性（literature-based CER） |
| equivalence_supporting_only | 等效设备仅作背景/参考 |
| equivalence_for_context_only | 等效设备仅用于 SOTA context |
| equivalence_not_allowed | 法规/合同/数据禁止主张等效性 |
| human_gate_required | 需要人工判断 |

**集成：** `gates.py` 中 G_EQUIVALENCE 的第一层检查。如果 route = equivalence_not_claimed，跳过三维比较检查，Writer 使用 non-equivalence template。如果 route = human_gate_required，触发 HC。

## F2 — Semantic Claim-Evidence Validator

**Semantic Support (S8/G43):** G43 消费 CER_REASONING_LEDGER 并验证 evidence_support_type，但主要验证链接存在（"claim has evidence_id"），不验证语义支持（"evidence actually supports the claim"）。

**Equivalence (S7):** EQV-01~03 规则在 Rulebook/YAML 中定义，但 runtime 无强制执行。Equivalent evidence 可被误写为 direct evidence，三维比较检测不完整。

## 2. Design

### 2.1 Semantic Support Validator

对每个 claim-evidence 链接验证：

| Check | Fail Condition |
|:---|:---|
| endpoint_match | Evidence endpoint ≠ claim endpoint |
| population_match | Evidence population ≠ claim target population |
| indication_match | Evidence indication ≠ device indication |
| device_match | Evidence device ≠ subject or equivalent device |
| directness | indirect evidence used as direct proof without limitation |
| support_strength | weak evidence (N<10, case report) supports strong conclusion |
| contradiction | Evidence contradicts claim direction |

**Integration:** G43 扩展。现有 G43 验证 link 存在 + evidence_support_type；新增 semantic_support_validator 作为 G43 子检查。G46 消费 G43 结果。

### 2.2 Equivalence Runtime Gate

| Check | Fail Condition |
|:---|:---|
| 3-dim technical | Technical characteristics differ without analysis |
| 3-dim biological | Biological safety differs without justification |
| 3-dim clinical | Clinical performance differs without clinical impact statement |
| differences impact | Differences exist but impact analysis missing |
| data access | High-risk context + no data access → HUMAN_GATE |
| vigilance | Vigilance/safety differences not addressed |
| no-equivalence path | Equivalence not claimed → writer must use non-equivalence template |
| evidence limitation | Equivalent evidence must not be written as direct proof |

**Integration:** `gates.py` 新 gate G_EQUIVALENCE，在 `_node_equivalence_analysis` 之后、G46 之前。EQV Rulebook 规则在 runtime 被导入。

## 3. Required Assets

| Asset | Status | Impact if missing |
|:---|:---|:---|
| C3 claim-evidence support | PARTIAL | Semantic validator calibration needs claim-evidence pairs; can derive from accepted CER |
| EQV Rulebook | READY | Sufficient for structural equivalence checks |
| 等效性分析文件 | PARTIAL | Impact analysis depth limited |

## 4. Tests

**Semantic validator:**
- [ ] Endpoint mismatch → FAIL
- [ ] Population mismatch without limitation → FAIL
- [ ] Indirect evidence as direct → FAIL
- [ ] Weak evidence (N=2 case report) → strong conclusion → FAIL
- [ ] Contradictory evidence → FLAG
- [ ] Valid direct evidence → PASS

**Equivalence gate:**
- [ ] Missing 3-dim comparison → REWORK
- [ ] Differences without impact analysis → FAIL
- [ ] Equivalent evidence written as direct → FAIL
- [ ] No-equivalence path accepted → PASS (different template)
- [ ] High-risk + no data access → HUMAN_GATE
- [ ] Valid equivalence with full analysis → PASS

## 5. Validation Criteria

**Batch F PASS:**
- [ ] All semantic validator tests pass
- [ ] All equivalence gate tests pass
- [ ] G43 semantic extension wired into G46
- [ ] G_EQUIVALENCE wired after equivalence_analysis
- [ ] No regression in baseline tests
- [ ] EQV Rulebook rules imported at runtime (grep confirmation)

## 6. Score Impact

| Score Area | Current (capped) | Target |
|:---|:--:|:--:|
| Claim-evidence semantic support | 5/6 (heuristic) | 6/6 (derived validation if C3 PARTIAL→READY) |
| S7 Stage | 70 | 80 |
| S8 Stage | 82 | 88 |
