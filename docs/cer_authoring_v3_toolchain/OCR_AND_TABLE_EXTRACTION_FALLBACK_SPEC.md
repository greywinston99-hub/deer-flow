# OCR AND TABLE EXTRACTION FALLBACK SPEC

> CCD 签发 | 2026-05-12

## Trigger Conditions

OCR fallback activated when:
- PyMuPDF returns zero extractable text pages
- OR text extraction yield < 100 chars per page (scanned image PDF)
- Table extraction activated on all PDFs with PyMuPDF + Camelot

## OCR Pipeline

```text
PDF → pdf2image (300 DPI) → Tesseract OCR → raw_text
  → text quality check (chars per page, language detection)
  → if quality OK: merge with any existing extractable text
  → if quality FAIL: mark document as OCR_LOW_QUALITY
```

## Table Extraction Pipeline

```text
PDF → Camelot lattice mode (first pass)
  → Camelot stream mode (fallback if lattice fails)
  → table structure validation (headers, row count, numeric content)
  → if both fail: mark as TABLE_EXTRACTION_FAILED
```

## Quality Signals

| Signal | Impact |
|---|---|
| OCR_LOW_QUALITY | All facts from this doc capped at extraction_confidence=low |
| TABLE_EXTRACTION_FAILED | Tables listed in missing_data_flags with impact=BLOCKING |
| MIXED_EXTRACTABLE_AND_OCR | Extractable pages = high; OCR pages = low |
| language != English | Marked, not auto-translated |

## Artifacts

- `ocr_fallback_report.json`: which docs needed OCR, quality assessment
- `table_extraction_report.json`: which tables extracted, which failed
- `document_parsing_lineage.csv`: per-document: parser used, pages, tables, OCR status

---

*CCD 签发：2026-05-12*
