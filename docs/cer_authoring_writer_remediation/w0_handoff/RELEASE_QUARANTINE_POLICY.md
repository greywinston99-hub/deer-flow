# RELEASE QUARANTINE POLICY

> CCD | 2026-05-15

## 规则

Gate fail 的 CER draft 不进入 release / final / customer-facing 目录。Gate fail 的 CER draft 写入 quarantine 子目录（`02_AI_BASELINE_OUTPUT_FREEZE/quarantine/`），附带 `failed_gate_report.json`。

Gate 1 HARD FAIL → 报告移至 quarantine。Gate 3 HARD FAIL → 报告移至 quarantine。Gate 2/4/5 HARD FAIL → 报告移至 quarantine。

PASS 全部 gate → 报告正常写入 `02_AI_BASELINE_OUTPUT_FREEZE/CER_draft.md`。

Quarantined 报告目录中自动生成 `rejection_ledger.md`，记录 fail reason、failing gate、contaminated sections、if applicable terms found。

Audit artifacts（reasoning_audit_ledger、gate_closure_report、benchmark score、MCP call logs、internal execution context）不进 CER body。这些文件独立存放在 artifact 目录中，Writer 不引用。

---

*CCD 签发：2026-05-15*
