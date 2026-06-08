# CDE90 — Current Capability Gap Analysis

**Current Stage 5 Score:** 78
**Target:** 90+

---

## Gap by Dimension

### clinical_fact_registry (current: v2, ~75)

**已有能力：** proportion, mean, N=XXX, source_pmid, E0 eligibility 4 fields, basic endpoint binding, basic population label
**缺口：**
- 数据模型扁平 — study arm / analysis set / timepoint / follow-up 无结构化字段
- 每个 fact 独立存储，无 study-level 上下文
- table/figure source 无锚定
- verification_status 无

**v3 升级：** 每个 fact 出生即携带 study arm / population / analysis set / timepoint / follow-up / source table-or-figure / verification_status

### statistical parser (current: ~70)

**已有能力：** proportion (X%, n/N), mean ± SD, N=XXX, basic HR/RR/OR/CI
**缺口：**
- median/IQR 覆盖有限
- Kaplan-Meier / survival rate / event-free survival 基本未覆盖
- incidence density / rate per patient-year 未覆盖
- between-group difference 未覆盖
- time-to-event 未覆盖
- incomplete fact 处理机制缺失

**v3 升级：** 扩展到 20 种统计类型 + incomplete fact 机制

### table/figure extraction (current: ~30)

**已有能力：** 基本缺失。无 born-digital PDF table extraction
**缺口：** 整个能力维度缺失。这是阶段 5 从 78 上不去的主要原因之一。

**v3 升级：** born-digital PDF + DOCX + text table parsing。≥50 table-derived facts。

### denominator/subgroup/arm (current: ~60)

**已有能力：** basic denominator check (总 N vs 子组 n), percentage recalculation
**缺口：**
- study arm 无建模
- analysis set (ITT/PP/safety/evaluable) 无区分
- per-patient vs per-procedure vs per-device 无区分
- subgroup generalization guard 不完整

**v3 升级：** arm-aware denominator resolver + analysis set validator

### gold validation (current: 0)

**已有能力：** 无 source-verified gold set
**缺口：** 这是算法能力无法自证的主要原因。synthetic tests 不能代替 gold validation。

**v3 升级：** ≥150 source-verified clinical facts gold set

---

## 为什么阶段 5 没有从 V4 提升

V4 重点在策略判断层（strategy router + literature intelligence + CER blueprint + NB explainability），不在数据提取层。V4 成功提升了系统的上游判断力，但底层数据提取能力仍是 V3 水平。这是正确的优先级——先解决"策略对不对"，再解决"数据够不够精"。但现在策略层已就位，数据提取精度成为瓶颈。
