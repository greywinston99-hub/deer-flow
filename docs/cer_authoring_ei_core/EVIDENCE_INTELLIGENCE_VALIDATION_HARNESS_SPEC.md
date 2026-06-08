# EVIDENCE INTELLIGENCE VALIDATION HARNESS SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## 一、验证维度

| 维度 | 说明 | 案例数 |
|---|---|---|
| **正向验证** | 理想输入 → 预期正向输出 | ≥8 |
| **负向验证** | 不足输入 → 正确降级 | ≥8 |
| **对手验证** | 边界/冲突/矛盾输入 → 正确处理 | ≥8 |
| **回归验证** | 已有 165 tests 继续通过 | 165 |

---

## 二、八个必含的负向/对手验证案例

### N1: 强声明 + 弱证据

| 项目 | 内容 |
|---|---|
| **输入** | claim_type=safety_clinical, evidence 仅有 competitor_device + low quality |
| **预期行为** | claim_support_level = INSUFFICIENT, conclusion_strength = INSUFFICIENT |
| **验证点** | 不生成肯定性声明, forbidden_phrases 包含所有肯定措辞 |

### N2: 竞品证据误用

| 项目 | 内容 |
|---|---|
| **输入** | claim_type=performance_clinical, 全部 evidence 为 competitor_device |
| **预期行为** | Admissibility → NOT_ADMISSIBLE, 证据被排除出声明证据池 |
| **验证点** | matching_evidence_count = 0, 不引用竞品数据支撑 subject device 性能 |

### N3: 端点语义不匹配

| 项目 | 内容 |
|---|---|
| **输入** | fact endpoint_label="血压", claim endpoint="心输出量", mapping_confidence=unmatched |
| **预期行为** | fact 不链接到 claim, endpoint_cluster 不同 |
| **验证点** | candidate_claim_ids 不含该 claim, semantic_endpoint_mapping 标记 unmatched |

### N4: OCR-低分 pivot 事实

| 项目 | 内容 |
|---|---|
| **输入** | extraction_confidence=OCR_uncertain 的 fact 关联到 primary evidence |
| **预期行为** | fact_role_cap = background, evidence_quality_tier 被降级 |
| **验证点** | evidence_role 被 capped 到 background, 该 evidence 不进入 STRONG/MODERATE 判定 |

### N5: 静默冲突平均

| 项目 | 内容 |
|---|---|
| **输入** | 研究 A: success_rate=95%, 研究 B: success_rate=60%, 同 endpoint_cluster |
| **预期行为** | CRITICAL DIRECTIONAL 冲突被标记, evidence_conflict_report 有 entry |
| **验证点** | 不输出平均值, synthesis_method = "none" for this cluster, conflict_id 存在 |

### N6: 缺失 subject device 临床数据

| 项目 | 内容 |
|---|---|
| **输入** | 仅有 literature_pubmed_sota + similar_device_literature, 无 subject_device 类型证据 |
| **预期行为** | 所有 subject device claims → INSUFFICIENT, Controlled Compromise 触发 |
| **验证点** | claim_support_level = INSUFFICIENT for safety/performance claims, pre_writer_readiness = BLOCKED |

### N7: CER/RMF 不匹配

| 项目 | 内容 |
|---|---|
| **输入** | CER safety claim 有 AE rate evidence, RMF 对应 hazard 无 evidence |
| **预期行为** | Crosswalk 标记 HIGH mismatch, 不合并判断 |
| **验证点** | crosswalk mismatch flag 存在, link_nature = consistency, domain_boundary_note 存在 |

### N8: PMCF 触发链

| 项目 | 内容 |
|---|---|
| **输入** | follow_up=6月, sample_size=20, single-arm study, implantable device |
| **预期行为** | 3 gaps triggered: long_term_data (high), rare_event (high), comparator_gap (medium) |
| **验证点** | 全部 3 个 gap 在 pmcf_gap_register 中, gap_severity 分级正确 |

---

## 三、正向验证案例（8 个）

| # | 场景 | 预期 |
|---|---|---|
| P1 | subject_device clinical investigation + high quality → safety claim | STRONG support |
| P2 | subject_device + equivalent (equivalence成立) → performance claim | MODERATE support |
| P3 | ≥3 可比研究 + 同质 → SOTA benchmark | benchmark_confidence = high |
| P4 | ≥2 subject_device + acceptable+ quality → BR favorable | favorable, br_confidence ≥ medium |
| P5 | subject_device PMS → safety_post_market claim | MODERATE support |
| P6 | subject_device test → performance_technical claim | MODERATE support |
| P7 | previous_gen with improvement data → clinical context | MODERATE support |
| P8 | complete evidence → audit_ledger 全链路 trace | 每条结论可追溯到 fact |

---

## 四、边界验证案例（8 个）

| # | 场景 | 预期 |
|---|---|---|
| B1 | 混合 subject + similar + competitor → SOTA | subject 为主, similar/competitor 标注限制 |
| B2 | 部分缺失数据 → claim MODERATE + missing gaps | missing_evidence_flags 列出缺失 |
| B3 | equivalence 论证 → 技术等效成立但临床不成立 | equivalent → 降级为 similar |
| B4 | 非关键端点 HIGH conflict → conclusion CAUTIOUS | CAUTIOUS, 冲突标记 |
| B5 | sample_size 边界 (n=29 vs n=30) → quality tier | n=29 → marginal, n=30 → acceptable |
| B6 | 1 个 high-quality + 1 个 low-quality → synthesis | narrative synthesis, low-quality 排除 |
| B7 | CT.gov NO_RESULTS_AVAILABLE → no fact | evidence 保留, fact 不创建 |
| B8 | bilingual fact → TRANSLATION_NEEDED → HRQ | HRQ entry 存在, 推理不阻塞 |

---

## 五、验证执行

### 5.1 执行流程

```text
Step 1: 构造测试输入（fact_table + evidence_registry + claims）
Step 2: 运行 Intelligence Core 推理链
Step 3: 检查每个验证点的实际输出 vs 预期输出
Step 4: 检查 audit_ledger 完整性
Step 5: 检查 human_review_packet 触发正确性
Step 6: 检查已有 165 tests 全部通过
```

### 5.2 验收标准

| 指标 | 门槛 |
|---|---|
| 正向案例通过率 | 100%（8/8） |
| 负向/对手案例通过率 | 100%（8/8） |
| 边界案例通过率 | 100%（8/8） |
| 回归测试通过率 | 100%（165/165） |

---

## 六、禁止

- ❌ 仅用正向案例验证
- ❌ 负向案例通过 mock/stub 假通过
- ❌ 跳过 audit_ledger 完整性检查
- ❌ 验收前不检查 regression tests

---

*CCD 签发：2026-05-12*
