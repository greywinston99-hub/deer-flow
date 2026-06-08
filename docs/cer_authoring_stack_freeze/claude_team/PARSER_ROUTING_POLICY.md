# PARSER ROUTING POLICY — CER Authoring V1.0

> Claude Code | 2026-05-15 | Phase 2D

## Page Classification → Parser Routing

| Page Type | Parser | Rationale |
|-----------|--------|-----------|
| text_digital | Docling (shadow) | Best quality for born-digital PDFs |
| table_digital | Docling (shadow) + Camelot | Docling for structure, Camelot for bounded tables |
| image_scanned | Disabled (Docling) | GLM-OCR handles scanned pages separately |
| mixed_page | Docling (shadow) | Handles mixed content better |
| text_scientific | Docling (shadow) | Scientific paper structure preservation |
| empty_page | Disabled | Skip blank pages |

## Camelot Bounded Behavior

- Only applied to table_digital pages
- Page timeout: 10 seconds per page (CER_PDF_CAMELOT_PAGE_TIMEOUT_SECONDS)
- If Camelot fails or times out: fall back to PyMuPDF text extraction
- No unbounded Camelot processing (performance guard)

## Docling Shadow/Preferred Policy

- Docling runs in "shadow" mode for supported page types
- "Shadow": Docling processes pages but PyMuPDF text is primary output; Docling output supplements
- "Preferred": Docling output is primary; PyMuPDF is fallback
- "Disabled": Docling not invoked for this page type
- Routing override: CER_DOCLING_ROUTING env var (JSON map)

## OCR Policy

- GLM-OCR used for image_scanned pages and image extraction from mixed pages
- Provider: zhipu_bigmodel (via BIGMODEL_API_KEY or ZHIPUAI_API_KEY)
- OCR results marked with confidence tags (OCR_uncertain, OCR_recovered)
- OCR-only evidence marked as low confidence in clinical fact extraction

## PDF Engine Failure Cache

- Failed parse attempts cached by (file_hash, page_num, engine, reason)
- Prevents repeated failures on same page with same engine
- Shifts to fallback parser on cache hit
