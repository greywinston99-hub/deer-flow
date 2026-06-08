# PDF DOCUMENT PARSING TOOL EVALUATION

> CCD 签发 | 2026-05-12

## Evaluation Matrix

| Tool | Text Extraction | Table Extraction | Structure (sections) | OCR | DeerFlow Integration | V3 Recommendation |
|---|---|---|---|---|---|---|
| PyMuPDF (fitz) | ★★★★★ Fast, high quality | ★★★☆☆ Basic table detection | ★★★☆☆ Heading heuristics | — | Python lib, no server | **V3-Core: primary PDF parser** |
| Camelot | — | ★★★★☆ Lattice + Stream modes | — | — | Python lib, works with PyMuPDF | **V3-Core: table extraction** |
| python-docx (existing) | ★★★★★ DOCX native | ★★★☆☆ Basic tables | ★★★☆☆ Style-based | — | Already integrated | **Keep existing** |
| Tesseract + pdf2image | — | — | — | ★★★☆☆ Good for printed text | Subprocess, requires install | **V3-Core: OCR fallback** |
| Docling (IBM) | ★★★★☆ AI-enhanced | ★★★★★ AI table understanding | ★★★★☆ Document structure model | — | New dependency, heavier | **V3.1+: when AI enhancement needed** |
| GROBID | ★★★★☆ Academic papers | ★★★☆☆ | ★★★★★ TEI XML output | — | Server process, academic focus | **V3.1+: academic papers only** |

## V3-Core Stack Decision

```text
Primary PDF (digital/vector):  PyMuPDF (text) + Camelot (tables)
Fallback OCR (scanned/image):  Tesseract + pdf2image
DOCX:                          python-docx (unchanged)

Coverage:
  PyMuPDF+Camelot: digital/vector PDFs ✅ | Scanned/image PDFs ⚠️ limited
  OCR-recovered tables: extraction_confidence=low → background only unless human_verified

Rationale:
  - PyMuPDF: fastest, most reliable text extraction. Python native. No server.
  - Camelot: best open-source table extraction. Works with PyMuPDF page objects.
  - Tesseract: required only as fallback (scanned PDFs). Not primary path.
  - Docling/GROBID: V3.1+. Trigger-based escalation if PyMuPDF+Camelot fails on key tables or
    scientific structure extraction is insufficient.
```

## Trigger-Based Escalation (V3.1 tools)

| Trigger | Tool | When |
|---|---|---|
| Key table not extractable by Camelot (lattice+stream both fail) | Docling tables | Evaluate earlier |
| Scientific paper structure (IMRAD) not recovered by PyMuPDF | GROBID | Evaluate earlier |
| Multiple documents from same project need AI-enhanced extraction | Docling | Batch evaluate |

## Integration Pattern

```text
PyMuPDF extract → structured_text (paragraphs, headings)
Camelot extract → tables (rows, headers, page number)
  → unified document_structured_content
  → Clinical Fact Extraction reads from this
```

---

*CCD 签发：2026-05-12*
