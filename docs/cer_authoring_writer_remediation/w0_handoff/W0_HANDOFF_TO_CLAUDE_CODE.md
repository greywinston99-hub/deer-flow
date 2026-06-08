# W0 HANDOFF — FROM CCD TO CLAUDE CODE

> CCD | 2026-05-15 | Implementation handoff

## Current Status Labels

```
CER_DRAFT_GENERATION_HARD_FAIL
REPORTS_QUARANTINED
QA_GATE_FALSE_PASS_CONFIRMED
PILOT_NOT_AUTHORIZED
SYSTEMIC_REMEDIATION_REQUIRED
```

## Problem Summary

Three pilot projects (启灏 plasma electrode, 米道斯 cardiac stabilizer, 永新 imaging software) completed strict-v7 runs. Gate-level results were acceptable (0-2 failures per project). But CER draft audit revealed 8 systemic generation defects:

1. Device identity contamination — cardiac stabilizer report contains urology/ureteroscope text
2. Clinical domain cross-wiring — SOTA chapters describe wrong clinical fields
3. Template cross-contamination — UAS/guidewire/ureteroscope text from CAL-001 template appears in all reports
4. Evidence matrix vs body conclusion conflict — matrix says INSUFFICIENT, body says "partially support"
5. IFU source facts not consumed — Writer outputs "Not extracted from IFU" despite 58 facts extracted
6. Internal system language leakage — "Claude/DeerFlow", "score: 100", "not_allowed" in CER body
7. Submission body / audit artifact mixed — workbook trace data in NB-facing document
8. QA gate false pass — Annex J gave score 100 to domain-contaminated reports

## Layers NOT Affected

These layers are verified functional and are not part of this remediation:
- PDF parsing pipeline (depth-aware router, bounded Camelot, page classifier, Docling shadow)
- Clinical fact extraction (58 facts from IFU/RMF/SOTA sources)
- EI Core reasoning (scoring, claim support, BR, PMCF, audit ledger, HRQ, gate signals)
- G46 bridge (Writer blocking logic)
- Gate routing (G6/G17/G18 fixes verified)
- 259 tests all passing
- graph.py / gates.py / agents.py zero diff across all phases

## Contaminated Draft Paths

```
/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_01启灏/02_AI_BASELINE_OUTPUT_FREEZE/CER_draft.md
/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/02_AI_BASELINE_OUTPUT_FREEZE/CER_draft.md
/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_03 永新-软件/02_AI_BASELINE_OUTPUT_FREEZE/CER_draft.md
```

## Input Artifact Paths (Claude Code will read from here)

```
Each project's 02_AI_BASELINE_OUTPUT_FREEZE contains:
- device_profile.json → locked_domain for Gate 1
- claim_support_matrix.json → support_level for Gate 3
- writer_conclusion_constraints.json → forbidden_phrases for Gate 3
- clinical_evidence_fact_table.xlsx → IFU facts for Gate 2
- document_structured_content (in state/pipeline) → IFU parsed text for Gate 2
- CER_draft.md → current contaminated output for regression testing
```

## Test Baseline

```
259 tests passing
Run: backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
Work directory: /Users/winstonwei/Documents/Playground/deer-flow
```

## Forbidden Files

```
graph.py / gates.py / agents.py — zero diff required
```

## Repair Phases (Claude Code to execute)

W1 — Device Identity Body Consistency Gate + Evidence-to-Conclusion Consistency Gate
W2 — IFU Fact Consumption Gate + Submission Body Cleanliness Gate
W3 — QA Gate Replacement / Hardening
W4 — Release / Quarantine Routing + Regression Fixtures
W5 — Regenerate contaminated pilot reports + audit summary

## Acceptance per Phase

W1: Gate 1 HARD FAILs on cardiac stabilizer report (contains ureteroscope). Gate 3 HARD FAILs on evidence-conclusion mismatch. Negation sentences do NOT trigger Gate 3. 259 tests pass.
W2: IFU present → 2.1 no longer outputs "Not extracted from IFU". 11 banned strings absent from CER body.
W3: New QA gate FAILs on domain-contaminated reports, PASSes on domain-correct reports.
W4: Gate-failed reports written to quarantine/ not output/. Regression fixtures verified.
W5: Three pilot reports regenerated, pass all gates, no domain contamination, no language leakage.

## Hard Stop Conditions

- 259 tests fail at any point
- graph.py / gates.py / agents.py modified
- EI Core _ei_* functions modified
- Gate gives false NEGATIVE (lets contaminated report through)
- Any phase closeout missing

## Final Deliverables

- 6 new/updated gates in pipeline
- Regenerated CER drafts for three pilots (domain-correct, evidence-consistent, clean)
- Per-phase closeout files
- Audit summary

## Implementation Notes

Claude Code is the implementer. CCD is controller (audits closeouts, does not implement). Codex is NOT the implementer for this batch. Owner authorizes final release.

---

*CCD 签发：2026-05-15*
