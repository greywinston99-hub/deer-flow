# CER WRITER GATE SPEC AUDIT

> CCD | 2026-05-15 | W0 Gate Specification — Before Codex Implementation

---

## Gate 1: Device Identity Body Consistency Gate

**执行时机**：Writer 生成 CER 正文完成后，CER draft 导出前。

**输入**：
- CER body full text（所有 Markdown section）
- `device_profile.json` → `locked_domain`
- `DOMAIN_TERM_MATRIX_V1.md` → 该 domain 的 `forbidden_terms`、`ambiguous_terms`、`required_terms`、`exception_contexts`

**检查逻辑**：
1. 对 SUMMARY、2.1、2.2、3.1、3.2、3.3、3.4、3.5、3.6、3.7、3.8、4.1-4.7、5 逐段扫描
2. 每个 `forbidden_term` 出现时，检查前后 50 字符是否匹配 `exception_context`（`excluded`、`not applicable`、`differs from`、`unlike`、`in contrast to`）
3. 非例外上下文 → HARD FAIL。记录：section、term、surrounding_text
4. 第一个 HARD FAIL 即可停止
5. 无 HARD FAIL 时，检查 `ambiguous_terms` 出现率，记录为 WARNING
6. 检查 `required_terms` 匹配率，< 30% 记录为 WARNING

**输出**：`domain_consistency_scan.json`。HARD FAIL 时附带 `CER_draft` 不写入 output 目录，写入 quarantine。

**失败条件**：任一 `forbidden_term` 在非例外上下文出现。

**例外条件**：句子包含 exclusion marker 且 forbidden_term 在对比/排除语义中。

---

## Gate 3: Evidence-to-Conclusion Consistency Gate

**执行时机**：Writer 生成 Summary 和 Conclusions 章后，CER draft 导出前。

**输入**：
- Summary 全文、Conclusions 全文
- `claim_support_matrix.json` → 每个 claim 的 `support_level`
- `EVIDENCE_CONCLUSION_PHRASE_POLICY.md` → 该 support_level 的 `forbidden_phrases`

**检查逻辑**：
1. 对每个 claim，从 `claim_support_matrix` 读取 `support_level`
2. 对照 Policy 获取该 level 的 `forbidden_phrases`
3. 对 Summary 和 Conclusions 做全文扫描
4. 扫到 `forbidden_phrase` → 向前查 10 词内是否含否定标记（`not`、`no`、`cannot`、`fails to`、`insufficient to`）→ 有则 PASS，无则 HARD FAIL
5. `ALLOWED_USE_BLOCKED` 的 claim 按 INSUFFICIENT 处理

**输出**：`evidence_conclusion_consistency_scan.json`。HARD FAIL 时 CER draft 不写入。

**失败条件**：`forbidden_phrase` 在非否定上下文中出现。Writer 对 INSUFFICIENT claim 写了 `support`。

**例外条件**：否定句。句子结构为 `[否定词] [动词] [禁止词]`。

---

## Gate 2: IFU Fact Consumption Gate（W2 实现）

**问题**：Writer 2.1 节全部显示 `Not extracted from IFU source text`，但 IFU 文本已存在于 `document_structured_content` 中。

**检查逻辑**：Writer 生成 2.1 后，扫描 `Not extracted from IFU source text`。如果 IFU 文件存在于项目输入中，此字符串 → GATE FAIL。Writer 应从 `document_structured_content` 中 `source_type = IFU` 的数据按字段类型映射读取。

---

## Gate 4: Submission Body Cleanliness Gate（W2 实现）

**问题**：内部系统语言泄漏到 NB 提交文档。

**检查逻辑**：CER body 全文扫描 11 个 banned strings。任一出现 → HARD FAIL。这些信息只能存在于 `reasoning_audit_ledger` 或独立 audit artifact 中。

---

## Gate 5: New QA Gate（W3 实现，替换 Annex J）

**问题**：当前 QA gate 只检查结构完整性，不检查 domain/content 一致性，给出 false pass。

**新 QA 检查项**：domain 一致性、forbidden terms、evidence-conclusion 一致性、internal language leakage、IFU placeholder 残留。不再允许 findings empty / score 100。

---

*CCD 签发：2026-05-15*
