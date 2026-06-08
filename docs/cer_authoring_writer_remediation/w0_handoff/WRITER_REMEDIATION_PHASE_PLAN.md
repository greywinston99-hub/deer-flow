# WRITER REMEDIATION PHASE PLAN

> CCD | 2026-05-15

## W1 — Gate 1 + Gate 3

**目标**：阻止 domain 串线报告产出。阻止证据不足时 Writer 输出肯定性结论。

**输入**：`device_profile.json`, `DOMAIN_TERM_MATRIX_V1.md`, `claim_support_matrix.json`, `EVIDENCE_CONCLUSION_PHRASE_POLICY.md`

**允许修改范围**：Gate 1 scanner + Gate 3 scanner in pipeline。Gate evaluation function。Writer output post-processing。Artifact export logic（quarantine routing）。

**禁止修改范围**：graph.py / gates.py / agents.py。EI Core _ei_*。Writer agent prompt/template/subagent。Existing gate logic。

**Targeted tests**：F1 cardiac stabilizer → HARD FAIL (ureteroscope)。F2 plasma electrode → HARD FAIL (UAS)。F3 evidence mismatch → HARD FAIL (support+INSUFFICIENT)。F4 negation → PASS。Domain-correct report → PASS。

**Full regression**：259 tests。graph/gates/agents zero diff。

**Acceptance**：Gate 1 catches domain contamination。Gate 3 catches evidence-conclusion mismatch。Negation sentences pass。No false positives on clean reports。

**Stop condition**：Gate misses contaminated report or blocks clean report → stop, fix rules, retest。

**Closeout files**：`W1_PHASE_CLOSEOUT.md`, `W1_GATE_TEST_REPORT.md`

## W2 — Gate 2 + Gate 4

**目标**：填入 IFU 数据。消除内部语言泄漏。**依赖 W1 通过。**

**输入**：`document_structured_content` (IFU parsed text), `clinical_evidence_fact_table.xlsx`, 11 banned strings list

**允许修改范围**：IFU-to-template field mapping in pipeline。Body cleanliness scanner。Writer 2.1 generation logic。

**禁止修改范围**：graph.py / gates.py / agents.py。EI Core _ei_*。

**Acceptance**：IFU 存在 → 2.1 不再输出 "Not extracted"。CER body 无 banned strings。

**Closeout files**：`W2_PHASE_CLOSEOUT.md`

## W3 — Gate 5 (QA Replacement)

**目标**：替换当前 QA gate。**依赖 W1+W2 通过。**

**允许修改范围**：QA gate evaluation logic。QA output schema。

**Acceptance**：New QA FAILs on contaminated report。New QA PASSes on clean report。No "score 100 with findings empty" allowed。

## W4 — Quarantine Routing + Regression

**目标**：Gate-failed 报告不进 release。Fixtures 验证。**依赖 W1-W3 通过。**

**允许修改范围**：Artifact export routing。Quarantine directory logic。Regression fixture test harness。

**Acceptance**：HARD FAIL → report in quarantine/。Fixture tests all verify expected behavior。

## W5 — Regeneration + Audit

**目标**：重新生成三个 pilot CER。**依赖 W1-W4 通过。**

**允许修改范围**：Nothing new。Only re-run pilots with new gates active。

**Acceptance**：Three reports pass all gates。No domain contamination。No language leakage。No evidence-conclusion mismatch。IFU data populated。

---

*CCD 签发：2026-05-15*
