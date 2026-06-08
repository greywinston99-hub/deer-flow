# V3 — Regulatory Engineer Review Gate

**Purpose:** CCD/Controller 验收标准。不是代码文件，是每个 Batch 完成后的法规专家级审查清单。
**Rule:** 每个 Batch 完成后，Controller 必须逐条回答。不可跳过。

---

## Batch E 后 — 临床数据提取

回答以下问题。如果答案不明确，该 Batch 不能标 ACCEPTED。

- [ ] 这些 clinical facts 是否真的能用于 CER 结论？
- [ ] 哪些只能做 background？
- [ ] 哪些只能做 limited evidence？
- [ ] 是否所有数字都有 source anchor（PMID + source sentence/table）？
- [ ] 是否所有 denominator 都有 population label（total vs subgroup）？
- [ ] 是否所有 endpoint 都有 endpoint_class？
- [ ] abstract_only 的数据是否被限制为 background_only？
- [ ] secondary_source 的数据是否被标记为 indirect？
- [ ] 是否有 orphan numeric fact（无 PMID 的数字）？
- [ ] 是否能向 NB 解释"这个数字为什么可信"？

---

## Batch F 后 — 语义支持与等效性

- [ ] 每条 compound claim 是否拆成 atomic claims？
- [ ] 每个 atomic claim 是否有 required_evidence_type？
- [ ] 每条 evidence 是否真的语义支持对应 atomic claim（不只是 link 存在）？
- [ ] 是否有 evidence mismatch：endpoint 不匹配、人群不匹配、适应症不匹配？
- [ ] 是否有 equivalent evidence 被误当 direct evidence？
- [ ] 是否先判断了 equivalence route（是否允许主张等效性）？
- [ ] 如果 equivalence_not_claimed，Writer 是否使用了正确的 non-equivalence template？
- [ ] 如果 equivalence_claimed，三维比较是否全部完成且 differences impact analyzed？
- [ ] 是否能向 NB 解释"为什么这条 evidence 支持这个 claim"？

---

## Batch G 后 — Domain 库与 BR/GSPR

- [ ] Domain template 是否覆盖了 claim_type 维度（不只是器械类别）？
- [ ] 每个 benefit claim 是否有 linked evidence？
- [ ] 每个 identified risk 是否有 mitigation？
- [ ] 每条 GSPR clinical clause 是否有 evidence 或 rationale？
- [ ] 是否处理了 unfavourable evidence（不利证据）？
- [ ] Unfavourable evidence 是否影响了 BR conclusion？
- [ ] 是否有 unresolved uncertainty 没有 disposition？
- [ ] BR conclusion 是否比 evidence 更强？
- [ ] 是否能向 NB 解释"为什么 benefit 大于 risk"？

---

## Batch H 后 — Writer 输出

- [ ] Writer prose 是否忠实于 ledger（不在 ledger 之外的声明）？
- [ ] 是否有语气过强（demonstrates/proves/confirms 用于 limited/moderate evidence）？
- [ ] 是否有未标注来源的数字？
- [ ] 是否有结论强于 ledger conclusion_strength？
- [ ] 是否有 endpoint taxonomy 矛盾？
- [ ] 是否有 comparator benchmark 缺失 limitation？
- [ ] 是否处理了所有 unfavourable evidence 的影响？
- [ ] 是否能提交给人工法规专家复核？

---

## Final — 整体法规可靠性

- [ ] 系统是否能向 NB 解释每个 clinical fact 的来源和可信度？
- [ ] 系统是否能向 NB 解释每条 claim 的证据支撑？
- [ ] 系统是否能向 NB 解释等效性决策路径？
- [ ] 系统是否能向 NB 解释 BR 为什么正向的？
- [ ] Writer 输出是否能在人工复核前就排除最常见的不合规措辞？
- [ ] 是否有任何能力被标记为 FULLY_CLOSED 但无法通过上述检验？
- [ ] 法规交付可靠性是否能从 78 提升到 85+？
