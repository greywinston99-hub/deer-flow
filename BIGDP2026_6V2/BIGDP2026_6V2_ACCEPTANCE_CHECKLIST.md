# BIGDP2026.6V_2 — Acceptance Checklist

**Purpose:** Hard acceptance checklist. No item is PASS until verified with code + test + runtime evidence.
**States:** ☐ NOT_CHECKED | ✅ PASS | ❌ FAIL | ⏭️ DEFERRED

---

## Section A0: Asset Readiness Gate

**CRITICAL: No Batch B code work begins until ALL Core Required Assets are READY.**

### Core Required Assets (ALL must be READY)

- [ ] A0.1 Engineer Feedback Pack — 10 类问题的原始反馈文档 + 正确值标注
- [ ] A0.2 Real Project Pack — 至少 2 个真实 CER 项目完整输入（含 iTClamp 类）
- [ ] A0.3 Full-text / Clinical Data Pack — PMID availability mapping + 已获得全文 PDF
- [ ] A0.4 Manual Search Gold Set — 工程师手动检索完整记录（检索词、命中数、筛选过程）
- [ ] A0.5 Denominator Gold Labels — 正确 denominator 分配 per data point
- [ ] A0.6 SOTA Accounting Gold Ledger — 正确 SOTA 数字 + 推导路径
- [ ] A0.7 Minimal Regulatory Core — MDR Annex XIV §1-§6 + MEDDEV 2.7/1 Rev.4 + ISO 14155:2020
- [ ] A0.8 Minimal Endpoint / AE Expert Labels — 至少覆盖 DC-6 相关的 endpoint semantic classification labels

### Supplementary Assets (READY before Batch C)

- [ ] A0.9 Extended Regulatory Pack — MDCG 2020-5/6/13, ISO 14971, IMDRF AE codes
- [ ] A0.10 Full Expert Labels — claim classification, evidence support, conclusion strength labels
- [ ] A0.11 NB Feedback Pack — NB 审核意见（如可用）
- [ ] A0.12 Final Accepted Files — 已验收 CER 最终版本（用于回归基线）

### Asset Readiness Summary

| Asset | Priority | Status |
|:---|:---|:---|
| A0.1 Engineer Feedback Pack | **Core** | ☐ |
| A0.2 Real Project Pack | **Core** | ☐ |
| A0.3 Full-text / Clinical Data Pack | **Core** | ☐ |
| A0.4 Manual Search Gold Set | **Core** | ☐ |
| A0.5 Denominator Gold Labels | **Core** | ☐ |
| A0.6 SOTA Accounting Gold Ledger | **Core** | ☐ |
| A0.7 Minimal Regulatory Core | **Core** | ☐ |
| A0.8 Minimal Endpoint / AE Expert Labels | **Core** | ☐ |
| A0.9 Extended Regulatory Pack | Supplementary | ☐ |
| A0.10 Full Expert Labels | Supplementary | ☐ |
| A0.11 NB Feedback Pack | Supplementary | ☐ |
| A0.12 Final Accepted Files | Supplementary | ☐ |

---

## Section E1: Retrieval Recall

- [ ] E1.1 `RETRIEVAL_AUDIT_TRAIL` artifact exists and is populated per search round
- [ ] E1.2 Each search records: query_string, database, date_executed, total_hits, humans_filter_applied
- [ ] E1.3 `G_RETRIEVAL_AUDIT` gate exists — BLOCKED when query_string is empty or search not recorded
- [ ] E1.4 Recall measurement: system retrieval vs manual gold set comparison
- [ ] E1.5 Recall < 50% → REWORK with query expansion suggestion
- [ ] E1.6 `fixture_retrieval_recall_gap.json` exists and semantic test passes
- [ ] E1.7 PRISMA flow diagram can be generated from `RETRIEVAL_AUDIT_TRAIL`

## Section E2: Retrieval Reproducibility

- [ ] E2.1 Search query strings included in `CER_INPUT_PACKAGE.json`
- [ ] E2.2 Writer (Claude Code) cites search strategy with exact query strings
- [ ] E2.3 NB auditor can reproduce search from package alone
- [ ] E2.4 `fixture_missing_query_string.json` → G_RETRIEVAL_AUDIT BLOCKED
- [ ] E2.5 `prisma_reproducibility.py` check passes on dry-run

## Section E3: Literature Screening

- [ ] E3.1 `SCREENING_RULE_ENGINE` enforces: N<10 → EXCLUDE (case_report_insufficient)
- [ ] E3.2 `SCREENING_RULE_ENGINE` enforces: animal/cadaver/in-vitro → EXCLUDE
- [ ] E3.3 `SCREENING_RULE_ENGINE` enforces: time_range unspecified → REWORK
- [ ] E3.4 Every exclusion has reason_code
- [ ] E3.5 `G_SCREENING` gate exists
- [ ] E3.6 `fixture_screening_n_lt_10.json` → EXCLUDE with reason_code
- [ ] E3.7 Screening decisions visible in human gate card at HC-04

## Section E4: PMID Data Traceability

- [ ] E4.1 Every clinical data point in package has `source_pmid` field
- [ ] E4.2 Every clinical data point has `abstract_verified` flag (true/false)
- [ ] E4.3 `DATA_TRACEABILITY_VALIDATOR` rejects orphan data (data without PMID)
- [ ] E4.4 `G46` data-traceability condition: BLOCKED if any claim uses orphan data
- [ ] E4.5 `fixture_orphan_data_no_pmid.json` → G46 BLOCKED
- [ ] E4.6 `PMID_ANCHOR` rule in EXPERT_REASONING_RULEBOOK

## Section E5: Full-Text Availability

- [ ] E5.1 Every evidence entry has `fulltext_status`: obtained / abstract_only / unobtainable
- [ ] E5.2 `abstract_only` evidence: `confidence = low`, cannot source numerical data
- [ ] E5.3 `G_FULLTEXT_BASIS` gate: BLOCKED if pivotal evidence is abstract_only with generated numerical data
- [ ] E5.4 `fixture_abstract_only_generates_data.json` → G46 BLOCKED or data flagged
- [ ] E5.5 Fulltext_status visible in evidence_registry export

## Section E6: Endpoint Semantics

- [ ] E6.1 `ENDPOINT_SEMANTIC_CLASSIFIER` exists: classifies as AE / treatment_failure / inadequate_hemostasis / other
- [ ] E6.2 "Device abandonment → alternative therapy" classified as treatment_failure, NOT AE
- [ ] E6.3 "Inadequate hemostasis" classified as efficacy endpoint, NOT safety AE
- [ ] E6.4 `G_ENDPOINT_SEMANTICS` gate exists
- [ ] E6.5 `fixture_device_abandonment_as_ae.json` → reclassified correctly
- [ ] E6.6 Classification rules derived from ISO 14155 terminology and expert labels
- [ ] E6.7 Endpoint classification visible in CER_REASONING_LEDGER

## Section E7: Comparator Benchmark Completeness

- [ ] E7.1 Every endpoint has comparator benchmark data (if available in literature)
- [ ] E7.2 Every rate has Wilson 95% CI calculated
- [ ] E7.3 Missing comparator → explicit limitation statement, not silent omission
- [ ] E7.4 `fixture_missing_comparator_benchmark.json` → G46 REWORK with limitation
- [ ] E7.5 BENCHMARK_DERIVATION_TRACE includes comparator data sources

## Section E8: Cross-Chapter Consistency

- [ ] E8.1 `CROSS_CHAPTER_CONSISTENCY_CHECKER` exists
- [ ] E8.2 Same endpoint in multiple chapters → values must match
- [ ] E8.3 Mismatch → Writer semantic QA gate BLOCKED
- [ ] E8.4 `fixture_endpoint_count_mismatch.json` → consistency check fails
- [ ] E8.5 Each endpoint value cites source section

## Section E9: SOTA Accounting Consistency

- [ ] E9.1 `SOTA_ACCOUNTING_CONSISTENCY_CHECKER` exists
- [ ] E9.2 article_count = screening output included_count
- [ ] E9.3 evidence_count = appraisal output appraised_count
- [ ] E9.4 Mismatch → G_SOTA_ACCOUNTING BLOCKED
- [ ] E9.5 `fixture_sota_accounting_mismatch.json` → BLOCKED
- [ ] E9.6 SOTA report generated numbers cross-validated against source nodes

## Section E10: Denominator / Subgroup

- [ ] E10.1 `DENOMINATOR_VALIDATOR` exists
- [ ] E10.2 Each rate has: numerator, denominator, population (total / subgroup name)
- [ ] E10.3 Denominator ≠ study reported total N → BLOCKED or corrected with explicit note
- [ ] E10.4 `G_DENOMINATOR` gate exists
- [ ] E10.5 `fixture_denominator_subgroup_mixup.json` → BLOCKED
- [ ] E10.6 Subgroup analysis correctly separated from total population analysis

## Section G: Global Regression Lock

- [ ] G.1 All BIGDP2026.6 tests still pass (500/500)
- [ ] G.2 All new V_2 tests pass
- [ ] G.3 End-to-end dry-run on at least 1 real project (not the training project)
- [ ] G.4 10 defect classes verified: no recurrence in dry-run output
- [ ] G.5 Controller review signed off
- [ ] G.6 PHASE_STATUS.md updated to ACCEPTED

---

## Summary

| Section | Items | PASS | FAIL | DEFERRED |
|:---|:---:|:---:|:---:|:---|
| A0: Asset Readiness Gate | 12 | 0 | 0 | 0 |
| E1: Retrieval Recall | 7 | 0 | 0 | 0 |
| E2: Retrieval Reproducibility | 5 | 0 | 0 | 0 |
| E3: Literature Screening | 7 | 0 | 0 | 0 |
| E4: PMID Data Traceability | 6 | 0 | 0 | 0 |
| E5: Full-Text Availability | 5 | 0 | 0 | 0 |
| E6: Endpoint Semantics | 7 | 0 | 0 | 0 |
| E7: Comparator Benchmark | 5 | 0 | 0 | 0 |
| E8: Cross-Chapter Consistency | 5 | 0 | 0 | 0 |
| E9: SOTA Accounting | 6 | 0 | 0 | 0 |
| E10: Denominator/Subgroup | 6 | 0 | 0 | 0 |
| G: Global Regression Lock | 6 | 0 | 0 | 0 |
| **TOTAL** | **77** | **0** | **0** | **0** |
