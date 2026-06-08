# CER/RMF EVIDENCE CROSSWALK SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## ⚠️ 领域边界保留

**Crosswalk = 可追溯性和一致性，不是合并 CER 和 RMF 判断。**
CER 和 RMF 保持各自独立的评估领域和结论逻辑。Crosswalk 仅表示证据的共用关系和双向引用。

---

## 一、Crosswalk 定义

CER/RMF Crosswalk 记录 CER 中的临床声明和 RMF 中的风险管理元素之间的证据关联关系，确保：
- **可追溯性**：CER 的安全性声明可追溯到 RMF 中对应的 hazard
- **一致性**：CER 和 RMF 引用一致的证据来源
- **不合并**：CER 的受益论证不替代 RMF 的风险评估，反之亦然

---

## 二、六种 Crosswalk 链接类型

| # | CER 元素 | RMF 元素 | 链接方向 | 链接性质 |
|---|---|---|---|---|
| 1 | Safety claim（AE rate） | Hazard identification | CER → RMF | CER 提供 AE 发生率数据，RMF 独立评估 hazard |
| 2 | Risk claim（risk probability） | Risk estimation | CER → RMF | CER 提供风险概率证据，RMF 独立做 risk estimation |
| 3 | Performance claim（success rate） | Risk control verification | CER ← RMF | RMF 定义需要的性能证据类型，CER 提供该证据 |
| 4 | Benefit conclusion | Risk acceptability | CER → RMF | 受益论证作为风险可接受性的输入之一 |
| 5 | PMCF objective | Post-market surveillance | CER → RMF | PMCF gap 信息传递给上市后监控计划 |
| 6 | Risk control measure | CER safety evidence | CER ← RMF | 风险控制措施的存在为 CER 安全性声明提供上下文 |

---

## 三、Crosswalk 数据结构

```text
crosswalk_entry:
  crosswalk_id: str             # CW-###
  cer_claim_id: str             # CLAIM-###
  rmf_hazard_id: str|null       # HAZ-### (nullable if RMF data not available)
  rmf_element_type: str         # hazard_identification / risk_estimation / risk_control / post_market_surveillance
  link_type: str                # cer_supports_rmf / rmf_requires_cer
  link_nature: str              # traceability / consistency
  shared_evidence_ids: [str]    # CER 和 RMF 共用的证据
  link_rationale: str           # 链接理由
  cer_conclusion_relevance: str # CER 结论对 RMF 的意义
  rmf_impact_on_cer: str        # RMF 对 CER 的影响
  domain_boundary_note: str     # "CER 评估 ≠ RMF 评估。此链接仅表示证据共用关系。"
```

---

## 四、Crosswalk 生成流程

```text
Step 1: 收集 CER 端
  从 claim_support_matrix 获取所有声明及其证据

Step 2: 收集 RMF 端（如 RMF 数据可用）
  从 risk_management_file / hazard list 获取 hazard 和 risk controls

Step 3: 匹配
  CER safety claim × RMF hazard（按端点/事件类型语义匹配）
  CER performance claim × RMF risk control（按性能要求匹配）
  CER PMCF gap × RMF post-market surveillance

Step 4: 生成 crosswalk entries
  每条匹配生成一个 crosswalk_entry

Step 5: 标记 mismatch
  如 CER 有 safety claim 但 RMF 无对应 hazard → mismatch flag
  如 RMF 有 risk control 但 CER 无对应 performance evidence → mismatch flag
```

---

## 五、Mismatch 处理

| Mismatch 类型 | 严重度 | 处理 |
|---|---|---|
| CER safety claim 无对应 RMF hazard | HIGH | RMF 可能不完整，标记 review |
| RMF hazard 无对应 CER safety evidence | HIGH | CER 可能缺安全性证据，标记 gap |
| CER performance claim 无对应 RMF risk control | MEDIUM | 一致性检查，标记 review |
| RMF risk control 要求的性能数据在 CER 中缺失 | HIGH | CER/RMF 不一致，标记 gap |
| CER PMCF gap 在 RMF PMS 中无对应 | MEDIUM | 标记为待补充 |

---

## 六、输出

```text
cer_rmf_crosswalk_table:
  crosswalk_entries: [crosswalk_entry]
  mismatch_flags: [{type, severity, description}]
  crosswalk_completeness: str  # complete / partial / incomplete
```

---

## 七、Writer 消费

Writer 不直接输出 crosswalk_table。Crosswalk 用于：
- CER Writer 中引用 RMF 相关风险控制
- 确保 CER 安全性声明与 RMF 一致
- 供人工 reviewer 检查 CER/RMF 一致性

---

## 八、禁止

- ❌ 将 CER 结论直接作为 RMF 的风险接受判定
- ❌ 让 RMF 的风险估计覆盖 CER 的受益论证
- ❌ 创建合并的 CER-RMF 综合评分
- ❌ 在 RMF 数据不可用时假装链接存在
- ❌ 用 Crosswalk 替代独立的 CER 或 RMF 推理

---

*CCD 签发：2026-05-12*
