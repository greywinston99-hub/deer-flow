# Expert CER Execution Checklists

**Source:** 5 份真实 CER 报告分析（帕姆/鱼跃/亚宏/心擎/海杰亚）+ CER V2 工程师反馈
**Purpose:** 可操作的检查清单，每一条都是 NB 审查中已验证的最佳实践

---

## Checklist A: 等效性论证（Equivalence）

### A.1 三步决策法
- [ ] Step 1: 列出所有已上市的同类产品（≥1 个）？否 → 跳过等效性论证，在 §4.2 明确声明
- [ ] Step 2: 是否计划引用该类产品的临床数据？否 → 简化等效性论证，仅做背景对比
- [ ] Step 3: 同类产品可通过三维度比较？否 → 不可作为等效设备；是 → 完成等效性表格

### A.2 三维度必填项
- [ ] Technical: 设计、材料、工作原理、关键性能参数、软件/算法
- [ ] Biological: 人体接触材料、接触类型和持续时间、物质释放
- [ ] Clinical: 预期用途（必须完全相同）、适应症、目标人群、使用部位

### A.3 差异论证
- [ ] 每个差异项都有论证
- [ ] 论证引用标准或测试数据（ISO 10993、台架测试）
- [ ] 预期用途完全一致（等效性核心前提）
- [ ] 等效设备已在目标市场获批

---

## Checklist B: 文献检索（Literature Search）

### B.1 检索协议六要素
- [ ] Research Questions（PICO 格式）
- [ ] 数据库列表及 URL（最低 PubMed + Embase）
- [ ] 完整 Boolean 检索式
- [ ] 检索日期范围 + 执行日期 + 执行人
- [ ] Inclusion / Exclusion Criteria（研究类型、语言、时间、人群）
- [ ] Quality Assessment Tool（RCT→RoB2, 队列→NOS, 病例系列→Maudsley）

### B.2 数据库最低要求
- [ ] PubMed/MEDLINE（100% 必要）
- [ ] Embase（欧洲期刊覆盖，强烈建议）
- [ ] Cochrane Library（系统性综述需求时）
- [ ] ClinicalTrials.gov（灰色文献补充）
- [ ] 通用名检索优先于品牌名

### B.3 检索完整性五重保障
- [ ] PRISMA 流程图（检索→去重→筛选→纳入，每个环节标注数量）
- [ ] 检索式 Annex（每个数据库完整检索式截图）
- [ ] 手工补充检索（3-5 本核心期刊）
- [ ] 引文追溯（backward citation tracking）
- [ ] 灰色文献检索（ClinicalTrials.gov、制造商官网、会议摘要）

---

## Checklist C: 文献评价（Literature Appraisal）

### C.1 三级评价框架
- [ ] 第一层：适用性/贡献度（++ highly suitable / + suitable / - limited / -- not suitable）
- [ ] 第二层：证据等级（Oxford CEBM 1a→5）
- [ ] 第三层：结果评估（Study Design, Sample Size, Key Outcomes, Safety Data, Relevance, Limitations）

### C.2 六因子评分
- [ ] study_design（~30%）：RCT > 队列 > 病例系列 > 个案
- [ ] relevance（~25%）：与本设备/适应症的直接相关度
- [ ] risk_of_bias（~15%）：基于 Cochrane RoB 工具
- [ ] sample_size（~15%）：受试者数量
- [ ] data_completeness（~10%）：端点数据报告质量
- [ ] statistical_rigor（~5%）：p 值、CI、多变量校正

---

## Checklist D: GSPR 分析

### D.1 风险等级决定分析深度
- [ ] Class I/IIa/成熟技术 → 隐性覆盖（按分析维度分节）
- [ ] Class IIb/III/创新技术 → 显性逐条（按 GSPR 条款分节）
- [ ] 心擎模式（独立大章）→ 高风险/MDR 深度响应

### D.2 GSPR → 证据映射链
- [ ] GSPR 1 (Safety & Performance) → Standards + Pre-clinical + Clinical + Literature + Vigilance
- [ ] GSPR 6 (Benefit-Risk) → SOTA benchmarks + Data Quality + Comprehensive Analysis
- [ ] GSPR 8 (Side Effects/Risks) → Safety data + PMS + Vigilance

---

## Checklist E: 正文-Annex 边界

| 内容类型 | 正文 | Annex | 规则 |
|:---|:---|:---|:---|
| 分析结论 | 独占 | — | 结论必须在正文完整呈现 |
| 原始文献列表 | 提及 | 完整 | 正文引用 + Annex 详列 |
| 检索策略细节 | 概述 | 完整 | 正文概述 + Annex 细节 |
| 等效性对比表 | 摘要 | 完整表格 | 正文摘要 + Annex 全表 |
| 警戒数据库原始记录 | 汇总 | 原始检索记录 | 正文汇总 + Annex 原始 |
| 临床调查原始数据 | 摘要 | CRF/数据集 | 正文摘要 + Annex 原始 |
| 标准清单 | 提及 | 完整清单 | 正文提及 + Annex 详列 |

---

## Checklist F: 章节依赖链（刚性依赖）

- [ ] §2 Scope → §3 SOTA（设备规格决定临床背景需求）——刚性
- [ ] §3 SOTA → §4 Evidence（SOTA 为证据分析设定基准）——刚性
- [ ] §4 Evidence → §5 Conclusions（证据推导出结论）——刚性
- [ ] §2 → §4（设备描述为等效性论证基础）——结构依赖
- [ ] Annex → §4（附件数据被正文引用）——数据依赖

---

## Checklist G: T0 关键表（数据锚点）

- [ ] device_profile — 设备身份锚点，错了全错
- [ ] claim_ledger — 定义"什么需要被证明"
- [ ] sota_benchmark_table — 评价本设备的参照系
- [ ] evidence_appraisal_table — 证据权重体系
- [ ] clinical_evidence_fact_table — 所有提取的数值数据
- [ ] claim_support_matrix — CER 论证核心数据结构
- [ ] benefit_risk_ledger — 结论的基石

---

## Checklist H: 检索词策略

- [ ] 通用名/技术名称优先级 > 品牌名
- [ ] 学术文献使用技术名称而非商品名
- [ ] 品牌名变体多，作为补充字段
- [ ] 检索式以 MeSH terms + Free text 组合
- [ ] 至少 PubMed + Embase 双数据库
