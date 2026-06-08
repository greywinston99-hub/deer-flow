# PRE-PILOT EI CORE VALIDATION CRITERIA

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## 约束

**在 Evidence Intelligence Core 全部实现并通过以下全部验证标准之前，Pilot 继续暂停。**

---

## 一、测试覆盖标准

| 指标 | 门槛 |
|---|---|
| EI-1 ~ EI-9 全部批次测试通过 | 100%（预估 ≥209 tests total） |
| 已有 165 tests 回归通过 | 100% |
| 验证框架 24 案例全部通过 | 100%（8 正向 + 8 负向/对手 + 8 边界） |

---

## 二、功能正确性标准

| # | 标准 | 验证方式 |
|---|---|---|
| F1 | Evidence scoring correctly rates subject_device RCT as excellent | 正向测试 P1 |
| F2 | Evidence scoring correctly rates competitor_device as marginal/insufficient | 负向测试 N2 |
| F3 | Claim support correctly identifies INSUFFICIENT when no subject device evidence | 负向测试 N6 |
| F4 | Admissibility correctly rejects competitor device for safety claims | 负向测试 N2 |
| F5 | Absence of evidence correctly distinguishes 7 categories | 边界测试 B2 |
| F6 | CRITICAL conflict correctly blocks conclusions | 负向测试 N1, N5 |
| F7 | SOTA benchmark correctly computes with ≥3 studies | 正向测试 P3 |
| F8 | BR correctly outputs unfavorable when evidence insufficient | 负向测试 (BR insufficient_evidence) |
| F9 | PMCF gaps correctly triggered by multiple conditions | 负向测试 N8 |
| F10 | CER/RMF crosswalk correctly flags mismatches | 负向测试 N7 |

---

## 三、降级正确性标准

| # | 标准 | 验证方式 |
|---|---|---|
| D1 | Strong claim + weak evidence → INSUFFICIENT (not silent completion) | N1 |
| D2 | Competitor evidence misuse → NOT_ADMISSIBLE (not used for claims) | N2 |
| D3 | OCR-low pivotal fact → capped at background | N4 |
| D4 | Silent conflict averaging → prevented (conflict flagged, no average) | N5 |
| D5 | Missing subject device data → Controlled Compromise triggered | N6 |
| D6 | Endpoint semantic mismatch → fact not linked to claim | N3 |

---

## 四、边界保持标准

| # | 标准 | 验证方式 |
|---|---|---|
| B1 | graph.py 零变化 | git diff |
| B2 | gates.py 零变化 | git diff |
| B3 | agents.py 零变化 | git diff |
| B4 | Evidence scoring never called "certification" or "regulatory grade" | code search |
| B5 | No auto-promotion of fact confidence | code search for auto_promote |
| B6 | CER/RMF crosswalk does not merge judgments | code + test N7 |
| B7 | SOTA/BR/PMCF use independent confidence metrics | code review |
| B8 | Human review correctly tiered (Tier 1 auto, Tier 2 flag, Tier 3 block) | F9 test |

---

## 五、人工审查标准

| # | 标准 | 验证方式 |
|---|---|---|
| H1 | human_review_packet.json 结构完整 | EI-9 测试 |
| H2 | Tier 3 packets have decision_required = true | EI-9 测试 |
| H3 | Tier 1 events are auto-handled, not in packet | EI-9 测试 |
| H4 | Each packet has decision_options | EI-9 测试 |

---

## 六、CAL-001 重跑标准

Intelligence Core 实现后，在 CAL-001 上重跑：

| # | 标准 |
|---|---|
| R1 | CAL-001 完整 authoring run 不崩溃 |
| R2 | evidence_strength_score 对 CAL-001 的每条 evidence 合理（不出现全部 excellent 或全部 insufficient） |
| R3 | claim_support_matrix 输出完整（每个 claim 有 support_level） |
| R4 | sota_benchmark_table 有合理的 benchmark_confidence 分布 |
| R5 | benefit_risk_conclusion 输出完整 |
| R6 | pmcf_gap_register 合理识别 CAL-001 的 data gaps |
| R7 | reasoning_audit_ledger 每条结论可追溯到 fact |
| R8 | human_review_packet 正确分层（不该阻塞的不阻塞） |
| R9 | Controlled Compromise 不意外触发（CAL-001 应有足够证据） |

---

## 七、Go / No-Go 决策矩阵

| 条件 | 权重 | 状态 |
|---|---|---|
| 全部 209+ tests 通过 | MUST | ☐ |
| 24 验证案例全部通过 | MUST | ☐ |
| graph/gates/agents 零变化 | MUST | ☐ |
| CAL-001 重跑全部 R1-R9 通过 | MUST | ☐ |
| 降级正确性 6/6 | MUST | ☐ |
| 边界保持 8/8 | MUST | ☐ |

**全部 MUST 条件满足 → Pilot 可恢复。任何 MUST 不满足 → Pilot 继续暂停。**

---

*CCD 签发：2026-05-12*
