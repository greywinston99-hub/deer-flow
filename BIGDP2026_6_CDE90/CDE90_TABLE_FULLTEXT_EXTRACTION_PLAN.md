# CDE90 — Batch N: Table / Figure / Fulltext Extraction

**Target:** Extract clinical facts from born-digital PDF, DOCX, CER tables, and text tables
**Priority:** born-digital first, OCR second

---

## 1. Extraction Sources

| Source | Format | Tool | Priority |
|:---|:---|:---|:--:|
| Born-digital PDF tables | PDF | liteparse / pdfplumber | P0 |
| DOCX clinical tables | DOCX | python-docx | P0 |
| CER embedded tables | PDF/DOCX in project files | liteparse | P0 |
| SOTA evidence tables | PDF in literature | liteparse | P1 |
| Extracted text tables | plain text from abstract/fulltext | text parser | P1 |
| Table footnotes | PDF/DOCX | liteparse | P1 |
| Kaplan-Meier figure detection | PDF images | candidate flag only (no numeric OCR) | P2 — detection ≠ extraction; KM candidate cannot count as source-verified KM fact unless numeric data verified from text/table |

## 2. Extraction Pipeline

For each table:
1. Detect and parse table structure → rows, columns, headers
2. Parse table title → identify what the table contains (safety/efficacy/demographics)
3. Parse table footnotes → extract denominator/analysis set/subgroup context
4. Map table cells to endpoint, arm, timepoint, N
5. Generate clinical facts with `source_table_or_figure` anchor
6. Extract and verify cell-by-cell against source when possible

## 3. Table-to-Fact Mapping Rules

| Table Type | Fact Fields Populated |
|:---|:---|
| Demographics | study_arm, population_label, N |
| Efficacy results | endpoint, fact_type, value, numerator, denominator, statistical_measure, CI, p_value |
| Safety/AE table | endpoint_category=safety, AE count, severity, study_arm |
| Follow-up table | followup_duration, timepoint |

## 4. Extraction Failure Classification

| Failure | Handling |
|:---|:---|
| Table structure unparseable | fact_status=incomplete, extraction_confidence=low |
| Missing headers | flag for human review |
| Merged cells | best-effort resolution, mark confidence=medium |
| Footnote unparseable | denominator=unknown, clinical_use_limitation=denominator_uncertain |
| Image-only table | flag for OCR (not in scope) |

## 5. Acceptance

- [ ] ≥50 table-derived facts
- [ ] ≥10 DOCX table facts
- [ ] ≥10 PDF table facts
- [ ] ≥10 facts with table footnote denominator context
- [ ] 0 table fact without source table anchor
- [ ] Fact status correctly set for incomplete extractions
