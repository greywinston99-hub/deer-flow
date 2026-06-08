# V3 — Batch G: Endpoint/Benchmark Domain Library + BR/GSPR Crosswalk

**Target:** Upgrade 4 (Endpoint/Benchmark Domain Library) + Upgrade 5 (BR/GSPR Substantive Crosswalk)
**Stages:** S6 (endpoint/benchmark), S10 (BR/GSPR), S12 (Writer limitation)
**Current Scores:** S6: 80 → 85, S10: 78 → 85

---

## G0 — Domain Template: Dual-Axis Design（UPDATED）

**法规问题：** 真实 CER 不是只按器械类别判断 endpoint，还按 claim 类型判断。

Domain template 从单轴（domain）升级为双轴（domain × claim_type）：

| Domain | claim_type | Expected Endpoints | Comparator | Benchmark Format |
|:---|:---|:---|:---|:---|
| hemostasis | safety | skin injury, device abandonment, infection | tourniquet, sutures | rate + CI |
| hemostasis | performance | time to hemostasis, hemostasis success rate | manual compression | rate + CI or mean ± SD |
| hemostasis | usability | ease of use score, device failure rate | alternative device | rate + CI |
| ablation | safety | thermal injury, pain, infection | surgery | rate + CI |
| ablation | performance | ablation success, recurrence rate | alternative ablation | rate + CI |
| implant | safety | loosening, fracture, infection, revision | alternative implant | rate + CI / KM |
| implant | clinical_benefit | functional score, ROM, pain score, mobility | non-operative | mean ± SD |
| cardiovascular | safety | thrombosis, bleeding, stroke, infection | alternative device | KM / HR + CI |
| cardiovascular | clinical_benefit | hemodynamic improvement, survival | medical mgmt | KM / HR + CI |

**集成：** `config/cer/endpoint_domain_templates.yaml` — domain × claim_type 矩阵。Endpoint classifier 消费双轴模板。

## G1 — Endpoint/Benchmark Domain Library

**Domain Library (S6):** 8-class endpoint semantic classifier 已有，90 endpoint labels 已吸收。但分类器依赖关键词匹配；domain template 仅 2 个（cardiac_pfa, urology_nephroscope）；新 domain 的 endpoint 期望集合、common misclassification、comparator benchmark 格式均缺失。

**BR/GSPR (S10):** G44/G45 已接入 G46。但 benefit_risk_ledger 可能空洞（benefit 无 evidence 链接、risk 无 mitigation 映射）；BR 结论 strength 无 validator；GSPR clinical clause 到 evidence 的映射无形式化。

## 2. Design

### 2.1 Endpoint Domain Template Library

为优先领域创建 domain template：

| Domain | Safety Endpoints | Performance Endpoints | Comparator | Benchmark Format |
|:---|:---|:---|:---|:---|
| hemostasis/wound closure | hemostasis rate, wound dehiscence, skin injury, device abandonment | time to hemostasis, ease of use | tourniquet, sutures, staples | rate + CI |
| ablation | thermal injury, pain, infection | ablation success rate, recurrence rate | surgery, other ablation | rate + CI |
| implant/orthopaedic | loosening, fracture, infection, revision | functional score, ROM, fusion rate | alternative implant, non-operative | rate + CI / mean ± SD |
| cardiovascular support | thrombosis, bleeding, stroke, infection | hemodynamic improvement, survival | alternative device, medical mgmt | KM / HR + CI |
| surgical instrument | tissue damage, bleeding, infection | procedural success, time | alternative instrument | rate + CI |

**Integration:** `config/cer/endpoint_domain_templates.yaml` — 外部 YAML，runtime 加载。Endpoint classifier 消费 domain template 进行上下文分类（不仅关键词）。

### G2.2 BR/GSPR Substantive Crosswalk

**benefit_to_evidence_crosswalk:** 每个 benefit claim → linked evidence → evidence strength → conclusion_allowed_strength

**risk_to_mitigation_crosswalk:** 每个 identified risk → risk control measure → residual risk → linked evidence or rationale

**GSPR_clinical_clause_to_evidence_matrix:** 每个适用 GSPR clinical clause → evidence coverage → gap → PMCF/limitation

**unresolved_uncertainty_register:** 所有 unresolved uncertainty → disposition (PMCF / labeling / risk_control / human_decision)

**unfavourable_evidence_register（NEW）：** CER 不能只收集正面证据。必须显式处理不利证据。

| Field | Description |
|:---|:---|
| unfavourable_evidence_id | unique ID |
| related_claim | 该不利证据影响哪个 claim |
| risk_or_benefit_impacted | 影响 risk 判断还是 benefit 判断 |
| severity | 不利证据的严重程度 |
| frequency | 不利证据的出现频率 |
| whether_contradicts_claim | 是否与 claim 直接矛盾 |
| mitigation_or_limitation | 如何缓解或限制 |
| impact_on_BR_conclusion | 对 BR 结论的影响 |

**BR conclusion strength validator:** BR conclusion_strength 不能超过 supporting evidence 的最高 strength，且必须考虑 unfavourable evidence 的影响。

## 3. Required Assets

| Asset | Status | Impact |
|:---|:---|:---|
| C1 endpoint labels | PARTIAL | Domain template 可用 endpoint classifier heuristic 生成；expert labels 提升准确性 |
| C2 comparator benchmark | PARTIAL | Comparator format 可用文献数据推断 |
| B4/B5/C3 data | PARTIAL | BR crosswalk 可用现有 ledgers 推导 |

## 4. Tests

**Domain library:**
- [ ] Domain template loads from YAML at runtime
- [ ] Endpoint classifier consumes domain template
- [ ] Unknown domain → generic fallback with limitation
- [ ] Domain template endpoint taxonomy contradiction → FLAG

**BR crosswalk:**
- [ ] Benefit without evidence → FAIL
- [ ] Risk without mitigation → REWORK
- [ ] GSPR clinical clause without evidence → REWORK
- [ ] BR conclusion stronger than evidence → FAIL
- [ ] Unresolved uncertainty without disposition → REWORK
- [ ] Valid crosswalk with complete mapping → PASS

## 5. Validation Criteria

**Batch G PASS:**
- [ ] ≥5 domain templates populated (hemostasis + ablation + 3 more)
- [ ] Domain template YAML loads at runtime
- [ ] All BR crosswalk tests pass
- [ ] GSPR clinical clause matrix populated from IFU/GSPR source
- [ ] Unresolved uncertainty register integrated into G46
- [ ] No regression

## 6. Score Impact

| Score Area | Current | Target |
|:---|:--:|:--:|
| Endpoint semantic correctness | 7/10 (heuristic) | 8/10 |
| Comparator benchmark completeness | 6/8 (heuristic) | 7/8 |
| S6 Stage | 80 | 85 |
| S10 Stage | 78 | 85 |
