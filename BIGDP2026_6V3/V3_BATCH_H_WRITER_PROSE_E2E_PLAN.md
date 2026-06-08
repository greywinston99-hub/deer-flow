# V3 — Batch H: Writer Prose QA + E2E Validation

**Target:** Upgrade 6 (Post-Write CER Prose QA)
**Stage:** S12 (Writer output), Final validation
**Current Score:** S12: 97 → 95 (quality hardening)

---

## 1. Problem

G46 和 CER_INPUT_PACKAGE 包级约束很强——Writer 在包级别被阻止产生无证据的声明。但 Writer 散文级自动审查缺失：

- Writer 可能在段落中使用比 conclusion_strength 更强的措辞
- Writer 可能产生无 PMID 锚定的数值
- Writer 可能在散文中混用 denominator
- Writer 可能将 device abandonment 误写为 AE
- Writer 可能省略 fallback benchmark 的 limitation 声明
- Writer 可能过度声称 PMCF 解决了不确定性

## 2. Design

### 2.1 Post-Write CER Prose QA Detectors

| Detector | Check |
|:---|:---|
| conclusion_overstatement | Prose claims "demonstrates superior efficacy" but ledger says `limited` |
| unsupported_positive_claim | Positive claim sentence without evidence_id in ledger |
| no_source_numeric | Numeric value in prose without PMID or source locator |
| denominator_misuse | Prose says "87.5% (70/80)" but context implies N=216 study |
| endpoint_taxonomy_contradiction | Prose labels "device abandonment" as "adverse event" but endpoint classifier says `treatment_failure` |
| missing_benchmark_limitation | Comparator data used without CI or limitation statement |
| pmcf_overclaim | "PMCF will resolve this uncertainty" for unsupported core claim |
| sota_prose_consistency | Prose says "13 articles" but SOTA accounting says different numbers |
| regulatory_language_tone（NEW）| Prose uses "demonstrates / proves / confirms / superior / safe and effective" without matching ledger conclusion_strength |

### 2.1a Regulatory Language Tone Checker（NEW）

**法规问题：** NB 退回报告常因语气和结论强度不合规，而非单句错误。

Tone-to-strength mapping:

| Ledger conclusion_strength | Allowed language | Forbidden language |
|:---|:---|:---|
| `limited` | may indicate, suggests, supports with limitations, preliminary evidence | demonstrates, proves, confirms, establishes, superior, safe and effective |
| `moderate` | supports, is consistent with, provides evidence for | demonstrates, proves, establishes, superior |
| `strong` | demonstrates, provides strong evidence, confirms | (most terms allowed if direct evidence + no major uncertainty) |
| `not_supported` | (claim must not appear as positive statement) | any positive language |

**集成：** `post_write_cer_qa.py` 第 9 个 detector。匹配 prose 中的结论性措辞对照 ledger conclusion_strength。

### 2.2 Integration

**Pre-write (已有):** G46 + CER_INPUT_PACKAGE validator — 不改，继承 V2。

**Post-write (新增):** `post_write_cer_qa.py` — 独立模块，读入 CER prose + CER_INPUT_PACKAGE + ledgers，输出 QA report with per-detector findings。集成到 Writer skill preflight 或作为独立 validation step。

**Writer output levels per v4 policy:**
- Level 1 (current-run output) → FULLY_CLOSED possible
- Level 2 (historical CER) → DERIVED_VALIDATION
- Level 3 (synthetic prose) → SYNTHETIC_ONLY

## 3. Required Assets

| Asset | Status | Level Available |
|:---|:---|:---|
| D2 CER originals | PARTIAL | Level 2 (historical) |
| D3 Writer outputs | PARTIAL | Level 2 (before/after) |
| Current-run Writer output | NOT_AVAILABLE | Level 1 blocked without E2E run |

**V3 最可能使用 Level 2（historical CER text）进行 DERIVED_VALIDATION。**

## 4. Tests

- [ ] Conclusion overstatement detected in "demonstrates superiority" vs `limited`
- [ ] Unsupported positive claim → FLAG
- [ ] No-source numeric → FAIL
- [ ] McKee-style denominator misuse in prose → FAIL
- [ ] "Device abandonment" written as AE → FAIL
- [ ] Missing benchmark limitation → FLAG
- [ ] PMCF overclaim → FLAG
- [ ] SOTA prose numbers vs accounting mismatch → FAIL
- [ ] Clean prose with all constraints met → PASS

## 5. Validation Criteria

**Batch H PASS:**
- [ ] All post-write QA tests pass
- [ ] QA report generated for at least 1 representative CER text
- [ ] All 8 detectors produce output (not stubs)
- [ ] Integration path documented (Writer skill or standalone)
- [ ] E2E or artifact-level validation completed
- [ ] Holdout project validation if available

## 6. Score Impact

| Score Area | Current | Target |
|:---|:--:|:--:|
| Writer semantic consistency | 4/6 (Level 2 + historical) | 5/6 |
| Real project / holdout validation | 2/4 | 3/4 |
| S12 Stage | 97 | 95 (quality) |
