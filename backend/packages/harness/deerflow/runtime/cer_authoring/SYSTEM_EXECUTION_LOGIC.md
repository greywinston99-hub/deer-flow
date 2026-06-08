# DeerFlow CER Authoring — 系统执行逻辑全貌

> 导出时间: 2026-05-25 | 220 tests | main @ 92ceedc5

---

## 一、42-Node DAG 全流程

```
initialize ─── 清点源文件(138), Lead Agent 理解任务
    ↓
input_gate ─── 检查 IFU + LLM provider 可用性
    ↓
device_profile ─── [HC-01] IFU → 设备画像(12字段) + ifu_working_document_status
    ↓
claim_decomposition ─── [HC-02] Claim Ledger 生成 + 证据源路由
    ↓
pico_derivation ─── PICO 框架(每个claim → Population/Intervention/Comparison/Outcome)
    ↓
methodology_review ─── CEP 方法论审核
    ↓
sota_search ─── [HC-03] PubMed 61,287 → 去重 → SOTA benchmark matrix
    ↓              sota_endpoint_selection_ledger
retrieval_domain_gate ─── 检索域污染检测
    ↓
device_equivalence_search ─── 等同器械检索(FDA 510k等)
    ↓
literature_screening ─── 标题摘要筛选 + PRISMA flow
    ↓
screening_depth_gate ─── 筛选深度门控
    ↓
evidence_appraisal ─── [HC-04] 6-factor + binary inclusion + MDCG level
    ↓
fulltext_basis_gate ─── 全文获取率检查
    ↓
endpoint_extraction ─── [HC-05] 从文献提取终点指标(4要素)
    ↓              sota_benchmark_reasoning_trace
sota_endpoint_gate ─── G_SOTA_REASONING (reasoning chain完整性)
    ↓
pre_g42 ─── Claim-Evidence 候选矩阵
    ↓
evidence_sufficiency_gate (G42) ─── 13 Pattern 诊断
    ├─ PASS → claim_evidence_matrix
    └─ REWORK → query_expansion → sota_search (螺旋)
         rework_gate_counter++ (max 5轮)
         Round 2: MeSH展开 + 引文追踪
         Round 3: 灰色文献 + 注册库
         Round 4: 终点替换 + 等效路径
         Round 5 → 强制放行
    ↓
claim_evidence_matrix ─── 声明×证据矩阵 + ifu_cer_alignment_ledger
    ↓                         + sota_benchmark_to_claim_alignment
claim_evidence_gate ─── G_IFU_WORKING_DOCUMENT
    ↓
gap_pmcf ─── 证据缺口 → PMCF 建议
    ↓
sota_clinical_context ─── SOTA 临床背景注入
    ↓
claim_sota_alignment ─── [HC-06] Claim-SOTA 对齐验证
    ↓
device_profile_iteration ─── 设备画像迭代
    ↓
vigilance_search ─── FDA MAUDE/MHRA/BfArM 警戒检索
    ↓
equivalence_analysis ─── 等效性 3D 对比(技术/生物/临床)
    ↓
risk_gspr_mapping ─── 风险 × GSPR 映射 + 心擎 Risk Matrix
    ↓
evidence_review_gates ─── 证据审查门控
    ↓
writer_synthesis ─── Claim Evidence 综合
    ↓
benefit_risk_ledger ─── 获益-风险台账
    ↓
br_justified_gate ─── BR 合理性门控
    ↓
alignment_matrix ─── 对齐矩阵
    ↓
alignment_gate ─── 对齐门控
    ↓
pre_writer_readiness_gate ─── G46: Writer 就绪(9 conditions)
    ↓
controlled_compromise ─── 受控妥协(不可修复时)
    ↓
cer_writing ─── 确定性模板生成9章 + Annex A-O
    ↓              LLM 逐章精炼(Summary/SOTA/Device/Conclusions/GSPR)
    ↓              ifu_update_recommendation_ledger
human_style_review ─── 人工 CER 模板对照
    ↓
nb_precheck ─── NB 预检(BSI/TUV_SUD 特异性)
    ↓
workbook ─── 工作簿组装
    ↓
gates ─── 61 gates 全量运行
    ↓
self_inspection ─── 系统自检报告
    ↓
export ─── [HC-07] DOCX + XLSX(60+) + PRISMA + IFU feedback report
```

---

## 二、7 个人工确认门 (Human Confirmation Interrupts)

| # | 节点 | 确认内容 | 优先级 |
|:---:|:---|:---|:---:|
| HC-01 | device_profile | Device Profile: name/type/purpose/mode/site | CRITICAL |
| HC-02 | claim_decomposition | Claim Ledger: 增删改 | CRITICAL |
| HC-03 | sota_search | SOTA 检索策略: 数据库/检索词 | HIGH |
| HC-04 | evidence_appraisal | 证据评分抽样 | MEDIUM |
| HC-05 | endpoint_extraction | 终点指标确认 | HIGH |
| HC-06 | claim_sota_alignment | Claim-SOTA 对齐结果 | HIGH |
| HC-07 | export | CER 终稿: Summary/Conclusions/GSPR | HIGH |

---

## 三、61 Gates 全量清单

### 管道 Gate (43)

| Gate | 位置 | 功能 |
|:---|:---|:---|
| G1b | input_gate | IFU 存在性 + Source Inventory |
| G1d | input_gate | LLM Provider 可用性 |
| G2 | device_profile | Device Profile 完整性 |
| G5 | claim_decomposition | Claim Ledger 完整 |
| G7 | sota_endpoint_gate | SOTA-to-4.7 使用 |
| G8 | evidence_appraisal | 评分驱动权重 |
| G12 | sota_endpoint_gate | Oxford-to-conclusion |
| G14 | sota_endpoint_gate | SOTA endpoint derivation |
| G19 | fulltext_basis_gate | 全文获取率 |
| G30 | sota_endpoint_gate | SOTA benchmark 可推导性 |
| G42 | evidence_sufficiency_gate | 13-Pattern 证据充分性诊断 |
| G46 | pre_writer_readiness_gate | Writer 就绪 (9 conditions) |
| G_ARG_01 | pre_writer_readiness_gate | 论证质量 |
| G_ARG_02 | pre_writer_readiness_gate | Claim-SOTA 对齐 |
| G_CEP | pre_writer_readiness_gate | CEP 存在性 |
| G_DP_STATE | gates | 46 DP 缺陷模式 state 验证 |
| G_IFU_WORKING_DOCUMENT | claim_evidence_gate | IFU working document 状态 |
| G_SOTA_REASONING | sota_endpoint_gate | SOTA 推理链完整性 |
| ... | ... | (其余 25 个管道 gate) |

### Writer Gate (6)

| Gate | 功能 |
|:---|:---|
| W1 | 域一致性 |
| W2 | 证据消费 |
| W3 | 结论强度 |
| W4 | 正文清洁度(banned strings) |
| W5 | 表格密度 |
| W6 | 附件完整性 |

### 风格 Gate (8, G39 内)

| 检测 | 规则 |
|:---|:---|
| 被动语态比率 | §2: 15-25%, §4.7: 10-20%, §5: <15% |
| 句长逐章约束 | §2: 22-32, §5: <20, §4: 25-30 |
| Hedging/Certainty 平衡 | 确定性:模糊限定 ≤ 3:1 |
| 段落要素完整性 | GSPR: 5要素, 文献: 6要素, 结论: 3要素 |
| 数值精度 | 单位/p值方法/CI双边界 |
| 等效性措辞 | Substantially equivalent / Not equivalent |
| PRISMA | Mermaid 流程图 + 表格 |
| Annex 密度 | 3-5 表/10页 |

### DP Gate (10, G_DP_STATE 内)

| DP | 检测 |
|:---|:---|
| DP-005 | claim_without_sota |
| DP-006 | g42_insufficient |
| DP-008 | no_rmf_for_warning |
| DP-012 | pool_below_threshold |
| DP-014 | missing_3d_comparison |
| DP-015 | gspr_without_evidence |
| DP-016 | pmcf_before_alternatives |
| DP-034 | annex_body_inconsistency |
| DP-035 | dependency_chain_broken |
| DP-037 | gspr_traceability_gap |

---

## 四、6 个新 Artifact (IFU + SOTA Reasoning Upgrade)

### IFU (3)

| Artifact | Schema | 生成时机 |
|:---|:---|:---|
| `ifu_working_document_status` | 12 fields × {value, confidence, maturity_status, needs_update} | device_profile 后 |
| `ifu_cer_alignment_ledger` | alignment_status: aligned/missing_in_ifu/overclaimed_in_ifu/unsupported/needs_human_review | claim_evidence_matrix 后 |
| `ifu_update_recommendation_ledger` | 6 recommendation_type: add_clinical_benefit/narrow_claim_scope/clarify_intended_purpose/add_warning/align_with_rmf/remove_unsupported | cer_writing 后 |

### SOTA (3)

| Artifact | Schema | 生成时机 |
|:---|:---|:---|
| `sota_benchmark_reasoning_trace` | 20+ fields: clinical_question/why_this_endpoint/source_articles/synthesis_method/CI/heterogeneity/allowed_conclusion_strength/forbidden_wording | endpoint_extraction 后 |
| `sota_endpoint_selection_ledger` | selected/rejected + clinical/regulatory/claim/risk relevance + evidence_availability | sota_search 后 |
| `sota_benchmark_to_claim_alignment` | supports/partially_supports/contextual_only/does_not_support + allowed_wording | claim_evidence_matrix 后 |

---

## 五、螺旋检索闭环

```
G42: 证据充分性诊断
  ├─ PASS ────────────────────→ claim_evidence_matrix
  └─ REWORK_REQUIRED ──→ query_expansion
                            ↓
                          rework_gate_counter++
                            ↓
                          Round 2: MeSH 展开 + 引文追踪 + 邻接数据库
                          Round 3: 灰色文献 + 注册库 + 厂商数据
                          Round 4: 终点替换 + 临床等价替代 + 等效路径
                          Round 5: PMCF 边界接受 → 强制放行
```

**rework_gate_counter >= 5 时**: 三个路由函数 (`_route_after_evidence_sufficiency_gate`, `_route_after_sota_endpoint_gate`, `_route_after_claim_evidence_gate`) 全部返回 forward 路径，不再循环。

---

## 六、Artifact Output (Export 阶段)

### DOCX
- `CER_draft.docx` — 完整 CER 报告(封面+TOC+9章+Annex A-O+页脚)
- `search_protocol_and_results.docx` — 检索协议
- `gap_pmcf_recommendations.docx` — PMCF 建议
- `nb_precheck_report.docx` — NB 预检

### XLSX (60+)
- `CER_Workbook.xlsx` — 合并工作簿(50+ sheets)
- `source_inventory.xlsx`, `evidence_appraisal_table.xlsx`, `sota_benchmark_matrix.xlsx`, ...

### MD/JSON
- `CER_draft.md` — Markdown 版本
- `prisma_flow_diagram.md` — PRISMA Mermaid 流程图
- 6 个 IFU/SOTA reasoning artifacts
- `final_gate_closure_report.json`
- `writer_quality_report.json`

---

## 七、LLM Agent 模型路由

| Agent | 模型 | 用途 |
|:---|:---|:---|
| cer-authoring-lead-agent | kimi-k2.6-api (父模型) | 任务编排、门控决策 |
| authoring-intake-profile-claim-agent | inherit | IFU 提取、声明分解 |
| authoring-methodology-sota-agent | inherit | SOTA 检索策略、PICO |
| authoring-evidence-agent | inherit | 文献筛选、证据评价、端点提取 |
| authoring-risk-equivalence-gspr-agent | inherit | 等效性、警戒、风险/GSPR |
| authoring-cer-writer-agent | DeepSeek V4 Pro | CER 章节撰写、LLM 精炼 |
| authoring-qa-review-agent | inherit | 跨章一致性审查 |

---

## 八、Key State Keys

| State Key | 生成节点 | 消费节点 |
|:---|:---|:---|
| `source_inventory` | initialize | input_gate, device_profile |
| `device_profile` | device_profile | claim_decomposition, cer_writing |
| `claim_ledger` | claim_decomposition | pico, sota, evidence, writer |
| `sota_benchmark_matrix` | sota_search | sota_endpoint_gate, cer_writing |
| `evidence_registry` | evidence_appraisal | endpoint, G42, writer |
| `claim_evidence_matrix` | claim_evidence_matrix | G42, writer, gates |
| `benefit_risk_ledger` | benefit_risk_ledger | br_justified_gate, writer |
| `risk_trace_matrix` | risk_gspr_mapping | gates, writer |
| `cer_chapter_drafts` | cer_writing | gates, export |
| `rework_gate_counter` | query_expansion | 3 个 rework route functions |
| `ifu_working_document_status` | device_profile | G_IFU, writer |
| `sota_benchmark_reasoning_trace` | endpoint_extraction | G_SOTA, writer |
