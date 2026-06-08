# ABSENCE OF EVIDENCE REASONING SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## 一、核心原则

这是推理核心的中心组件——缺失证据推理贯穿所有下游模块（Claim Reasoning、SOTA、BR、PMCF）。

**核心原则**：
- 「没有证据」≠「没有风险」
- 「没有证据」≠「安全有效」
- 缺失证据 → 结论降级，不是否定结论
- 缺失证据 ≠ 搜索失败——必须区分缺失的类别

---

## 二、七种缺失证据类别

| # | 类别 | 定义 | 示例 | 结论影响 |
|---|---|---|---|---|
| 1 | **not_searched** | 未检索该源类型 | PMS 数据库未查询 | 不可声称全面检索 |
| 2 | **searched_not_found** | 检索了但零命中 | PubMed 检索零结果 | 可声称「未发现已发表文献」 |
| 3 | **found_but_low_quality** | 检索命中但质量不可接受 | OCR 低分的扫描文档 | 证据存在但不可采信 → background |
| 4 | **found_but_indirect** | 检索命中但不直接 | 相似设备数据但无 subject device 数据 | 有限使用（similar device rules） |
| 5 | **no_results** | 记录存在但无结果数据 | CT.gov 注册但 NO_RESULTS_AVAILABLE | 元数据可用但不产生 fact |
| 6 | **missing_endpoint** | 有 evidence 但缺特定端点 | 有安全性数据但无有效性数据 | 部分支持，缺失端点降级 |
| 7 | **conflicting** | 有多条证据但方向矛盾 | 研究 A 获益 vs 研究 B 危害 | CRITICAL 冲突 → 阻塞 |

---

## 三、各类别的推理规则

### 3.1 not_searched（未检索）

| 维度 | 规则 |
|---|---|
| **可以说什么** | 「[源类型] 未在本 CER 中系统检索」 |
| **不能说什么** | 「已检索所有相关数据库」/ 「文献检索全面」 |
| **结论强度上限** | CAUTIOUS（不可声称全面性） |
| **PMCF 触发** | 如该源类型为 required_source_profile 的一部分 → gap_severity = high |
| **Human Review** | Tier 2（标记限制） |

### 3.2 searched_not_found（检索了未找到）

| 维度 | 规则 |
|---|---|
| **可以说什么** | 「在 [数据库] 中未检索到 [端点/设备] 的已发表文献」 |
| **不能说什么** | 「没有证据表明存在风险」（absence of evidence ≠ evidence of absence） |
| **结论强度上限** | CAUTIOUS（不可声称安全或有效） |
| **PMCF 触发** | PMCF gap triggered：需通过其他方式获取数据 |
| **Human Review** | Tier 2（标记限制） |

### 3.3 found_but_low_quality（找到了但质量低）

| 维度 | 规则 |
|---|---|
| **可以说什么** | 「已识别的证据质量不足以支持可靠结论」/ 「[来源] 的数据因 [原因] 仅作为背景信息」 |
| **不能说什么** | 不得引用该证据的数值作为肯定性声明的支撑 |
| **结论强度上限** | INSUFFICIENT（如仅此证据）或 CAUTIOUS（如有其他证据） |
| **PMCF 触发** | Gap triggered：需要更高质量的数据 |
| **Human Review** | Tier 1 自动（降级到 background） |

### 3.4 found_but_indirect（找到了但不直接）

| 维度 | 规则 |
|---|---|
| **可以说什么** | 「[相似/等效设备] 的临床数据表明 [端点] 在可比人群中表现为 [范围]」+ 必须引用限制 |
| **不能说什么** | 不得声称 subject device 与相似设备有相同的安全性/性能 |
| **结论强度上限** | CAUTIOUS |
| **PMCF 触发** | Gap triggered：需要 subject device 直接数据 |
| **Human Review** | Tier 2（如用于关键声明） |

### 3.5 no_results（有记录无结果）

| 维度 | 规则 |
|---|---|
| **可以说什么** | 「[NCT 号] 在 ClinicalTrials.gov 注册，但未发布结果」 |
| **不能说什么** | 不得引用未发布结果的研究数据 |
| **结论强度上限** | 不影响（该记录不用于支撑声明） |
| **PMCF 触发** | 可能：未完成的试验 → follow-up gap |
| **Human Review** | Tier 1（自动标记） |

### 3.6 missing_endpoint（有 evidence 但缺端点）

| 维度 | 规则 |
|---|---|
| **可以说什么** | 「当前证据提供了安全性数据，但不包含 [缺失端点] 的数据」 |
| **不能说什么** | 不得对该端点做肯定性结论 |
| **结论强度上限** | 对缺失端点：INSUFFICIENT；对已有端点：按实际证据 |
| **PMCF 触发** | Gap triggered：缺失端点 → PMCF objective |
| **Human Review** | Tier 2（缺失非关键端点）/ Tier 3（缺失安全关键端点） |

### 3.7 conflicting（冲突）

| 维度 | 规则 |
|---|---|
| **可以说什么** | 「[研究 A] 报告 [结果 A]，而 [研究 B] 报告 [结果 B]」→ 描述分歧，不选边 |
| **不能说什么** | 不得静默平均两方结果 / 不得选择性引用一方 |
| **结论强度上限** | CRITICAL → INSUFFICIENT（阻塞）；HIGH → CAUTIOUS |
| **PMCF 触发** | Gap triggered：冲突需更多数据解决 |
| **Human Review** | CRITICAL → Tier 3 阻塞；HIGH → Tier 2 标记 |

---

## 四、跨类别推理规则

### 4.1 多类别组合

同一 claim 可能同时存在多种缺失：
- 有 searched_not_found（文献）+ missing_endpoint（端点）= 两者分别处理
- 有 found_but_low_quality + found_but_indirect = 最严格的限制生效

### 4.2 结论强度取最低

当 claim 有 ≥2 种 evidence 状态时：`claim_conclusion_strength = min(各 evidence 的 conclusion_strength)`

---

## 五、禁止

- ❌ 将 not_searched 当作 searched_not_found
- ❌ 将 found_but_low_quality 当作 found_acceptable
- ❌ 将 found_but_indirect 当作 subject device direct evidence
- ❌ 将 no_results 当作 evidence of safety/performance
- ❌ 在 conflicting 未解决时静默平均
- ❌ 声称「无证据表明风险存在」当作肯定性安全结论

---

*CCD 签发：2026-05-12*
