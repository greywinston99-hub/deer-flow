# CODEX W1 READY ASSESSMENT

> CCD | 2026-05-15

## Verdict

**CODEX_W1_READY。** Gate 1 和 Gate 3 的规格审计已完成。Domain Term Matrix、Evidence-Conclusion Phrase Policy、Contamination Regression Fixtures、Quarantine Policy 均就绪。规则明确，边界清晰，可直接实现。

## Codex W1 精确边界

**要实现什么**：

Gate 1 — Device Identity Body Consistency Gate。在 Writer 生成 CER 完整正文后、CER draft 写入 `02_AI_BASELINE_OUTPUT_FREEZE` 前，执行全文 domain consistency 扫描。输入来自 `device_profile.json` 的 `locked_domain` 字段。查询 `DOMAIN_TERM_MATRIX_V1.md` 获取该 domain 的 `forbidden_terms` 列表和 `exception_contexts` 规则。扫描 Summary、2.1、2.2、3.1-3.8、4.x、5 的全部文本。任一 forbidden_term 在非 exception 上下文中出现 → HARD FAIL。HARD FAIL 时 CER_draft.md 不写入磁盘，而是写入 quarantine 目录并附带 `domain_consistency_fail_report.json`。WARNING（ambiguous term 或 required term match rate < 30%）记录在 gate report 但不阻塞。

Gate 3 — Evidence-to-Conclusion Consistency Gate。在 Writer 生成 Summary/Conclusion 后执行。读取 `claim_support_matrix.json` 中每个 claim 的 `support_level`。读取 `EVIDENCE_CONCLUSION_PHRASE_POLICY.md` 获取该 support_level 对应的禁止措辞列表。对 Summary 和 Conclusions 章做全文扫描。找到禁止措辞 → 向前查找 10 词内否定标记。无否定标记 → HARD FAIL。ALLOWED_USE_BLOCKED 的 claim 当作 INSUFFICIENT 处理。

**不改什么**：
- graph.py / gates.py / agents.py
- EI Core _ei_* 函数
- Writer agent 本身（prompt / template / subagent）
- 已有 gate 逻辑（G1d/G6/G17/G18 等）
- clinical_evidence_fact_table 生成

**验收标准**：
- 用 Cardiac Tissue Stabilizer 的旧报告（已知含 ureteroscope/UAS）做输入 → Gate 1 HARD FAIL，报告不写入 output 目录
- 用已知 evidence-conclusion 矛盾的旧报告 Summary 段落 → Gate 3 HARD FAIL
- 用 CAL-001 报告（domain 正确，但 evidence insufficient）→ Gate 1 PASS，Gate 3 HARD FAIL（因为 Summary 中可能含 forbidden phrases）
- 否定句中的禁止词不触发 Gate 3
- 259 tests 保持通过

**停止条件**：
- 259 tests 不通过 → 停止，修到通过
- Gate 对 domain 正确的报告误杀 → 修 exception context 规则，不降低 forbidden_terms 标准
- Gate 对 domain 错误的报告漏过 → 修 forbidden_terms 列表

## Codex 不做什么

不实现 Gate 2（IFU）、Gate 4（Cleanliness）、Gate 5（New QA）。W1 仅 Gate 1 + Gate 3。

---

*CCD 签发：2026-05-15*
