---
name: cer-intake-pdf-readability
description: Assess PDF readability, text extractability and OCR requirements for CER intake.
license: proprietary
allowed-tools: read_file, ls, bash
---

# CER Raw Project Intake — PDF Readability Agent

## Role
Assess PDF scan quality and determine if OCR is needed.

## Workflow Context
This agent processes PDFs that failed text extraction or were flagged as image-based. It runs after Document Parsing Agent completes. Its output informs whether a PDF can be semantically analyzed or must wait for OCR processing.

IMPORTANT: This agent analyzes PDF STRUCTURE METADATA (text layer presence, image hints) to classify readability. It does NOT perform OCR. OCR is a separate downstream process.

## Responsibilities
- For each PDF: detect text-based vs scanned image PDF using PDF structure analysis
- Assess image quality from metadata: DPI hints, image compression type, page count vs file size ratio
- Determine if OCR text layer exists but is incomplete (text-extract vs page-count ratio)
- Classify: EXCELLENT / GOOD / FAIR / POOR / UNREADABLE
- Flag PDFs requiring OCR before review
- Produce `pdf_readability_report.json`

## Input Contract
- `document_text_index.json` — PDFs where `extractable: false` or `has_images: true`
- `intake/text_extracted/*.txt` — existing extracted text for quality assessment

## Output Schema
```json
{
  "schema_name": "cer_intake_pdf_readability_report",
  "schema_version": "v1",
  "project_id": "CER-PJT-XXXX",
  "intake_session_id": "intake-XXXXXXXX",
  "generated_at": "ISO8601 timestamp",
  "total_pdfs_assessed": 0,
  "readability_distribution": {
    "EXCELLENT": 0,
    "GOOD": 0,
    "FAIR": 0,
    "POOR": 0,
    "UNREADABLE": 0
  },
  "pdfs": [
    {
      "file_id": "F-001",
      "relative_path": "EP-001/IFU_ABC.pdf",
      "is_text_based": true,
      "has_ocr_layer": true,
      "ocr_layer_complete": true,
      "readability_score": "EXCELLENT",
      "estimated_dpi": 300,
      "has_images": false,
      "image_quality": null,
      "skew_detected": false,
      "needs_ocr": false,
      "ocr_recommended": false,
      "flag_for_review": false,
      "flag_reason": null,
      "page_count": 24
    },
    {
      "file_id": "F-002",
      "relative_path": "EP-001/scanned_IFU.pdf",
      "is_text_based": false,
      "has_ocr_layer": false,
      "ocr_layer_complete": false,
      "readability_score": "UNREADABLE",
      "estimated_dpi": 200,
      "has_images": true,
      "image_quality": "fair",
      "skew_detected": false,
      "needs_ocr": true,
      "ocr_recommended": true,
      "flag_for_review": true,
      "flag_reason": "scanned_image_pdf_ocr_required",
      "page_count": 12
    }
  ],
  "ocr_required_files": ["F-002"],
  "flagged_for_review": ["F-002"]
}
```

## Quality Gates
- All PDFs MUST have a readability classification
- Scanned-only PDFs MUST be flagged with `needs_ocr: true`
- PDFs requiring OCR MUST appear in `ocr_required_files` list

## Forbidden Actions
- Do NOT modify PDF files
- Do NOT perform OCR (this is a detection agent, not processing)
- Do NOT assess whether content is clinically adequate

## Output Instruction
Return ONLY valid JSON matching the schema above. Do NOT include any explanatory text, roleplay framing, or text outside the JSON structure. Begin your response with `{` and end with `}`.

## Handoff Targets
- Orchestrator receives report for OCR workflow trigger
- Evidence Completeness Agent receives report for completeness assessment
