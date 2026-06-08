# EVIDENCE-CONCLUSION PHRASE POLICY

> CCD | 2026-05-15 | Authoritative for Gate 3

## 核心规则

Writer 的 Summary 和 Conclusions 章中，每个 claim 的描述措辞必须与其在 `claim_support_matrix` 中的 `support_level` 和 `max_conclusion_strength` 一致。不一致即为 Gate 3 HARD FAIL。

## 四级强度定义

### INSUFFICIENT

**可写**：
- `current evidence is insufficient to conclude`
- `cannot be determined from available data`
- `further clinical evidence is required`
- `claim held pending additional data`
- `no conclusion can be drawn at this stage`
- `evidence does not support a conclusion`

**禁止写**：
- `clinical data support`（含任何变体：supports / supporting / supported / in support of）
- `demonstrate` / `demonstrates` / `demonstrated`
- `confirm` / `confirms` / `confirmed`
- `consistent with`
- `favourable` / `favorable`
- `partial support` / `partially support`
- `the evidence suggests`
- `the data indicate`（含 indicates / indicating）
- `acceptable` / `adequate` / `sufficient`
- 任何肯定性 benefit-risk 表述

### CAUTIOUS

**可写**：
- `limited evidence suggests`
- `preliminary data indicate`
- `may be associated with`
- `observational data hint at`
- `further confirmation is required`
- 必须附带具体的 limitation 说明

**禁止写**：
- `demonstrate` / `confirm` / `prove`
- `strong` / `robust` / `conclusive`
- `clearly` / `definitively`
- `fully support`
- `establish` / `established`

### MODERATE

**可写**：
- `evidence supports`
- `clinical data indicate`
- `studies demonstrate`
- `consistent with`
- `acceptable benefit-risk profile`

**禁止写**：
- `strongly support`
- `conclusively`
- `definitively`
- `without uncertainty`

### STRONG

**可写**：
- `strongly support`
- `confirm`
- `demonstrate with high confidence`
- `robust evidence`
- `well-established`

**禁止写**：无特殊禁止——STRONG 是最宽松级别。

## 否定句处理

关键规则：否定句中的禁止词不受 Gate 3 限制。

示例：
- `evidence does NOT support` → **不触发** Gate 3（即使在 INSUFFICIENT 下）
- `cannot be considered as sufficient` → **不触发**
- `does not demonstrate` → **不触发**

检测逻辑：扫到禁止词后，向前查找 10 个词以内是否存在否定标记（`not` / `no` / `cannot` / `does not` / `does not` / `insufficient to` / `fails to`）。存在否定标记 → 不触发。不存在 → HARD FAIL。

## ALLOWED_USE_BLOCKED 处理

如果 claim 在 `allowed_claim_types` 中被标记为 `ALLOWED_USE_BLOCKED`：
- 该 claim 在 Summary / Conclusion 中不得被描述为「被任何证据支持的」
- 只能写 `not supported by available evidence` / `clinical data do not support this claim` / `evidence does not meet admissibility criteria`
- Writer 将其当作 INSUFFICIENT 处理

## Gate 3 扫描范围

- Summary（§1）全文
- Conclusions（§5）全文
- Device Under Evaluation（§4）中的 claim-specific 结论段

不扫描以下章节中的 claim 描述（这些是分析过程，不是最终结论）：§3 Clinical Background / SOTA。但如果 §3 中出现了「supports claim C-xx」且 claim C-xx 的 support_level = INSUFFICIENT，触发 WARNING。

## 与 Writer 的关系

Gate 3 不修改 Writer 生成的文本。它是 Writer 输出后的验证器。HARD FAIL 时 Writer 输出被拒绝，CER draft 不写入。WARNING 时记录位置但 CER draft 仍可输出。

---

*CCD 签发：2026-05-15*
