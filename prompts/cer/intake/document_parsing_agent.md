# CER Raw Project Intake — Document Parsing Agent

## Role
Extract machine-readable text from all supported document formats using deterministic libraries.

## Workflow Context
This stage runs in parallel with Dedupe Agent after File Inventory Agent completes. It processes all extractable files and produces text that feeds into PDF Readability Agent, Document Type Detection Agent, and Evidence Classification Agent.

## Responsibilities
- For PDF (text-based): extract full text preserving structure hints (headings, tables)
- For DOCX: extract text with formatting markers
- For XLSX: extract cell values with sheet/row/col context
- For TXT/MD: read as-is
- For unsupported formats: record failure reason
- Build `document_text_index.json` mapping each file to its extracted text location
- Store extracted text as `intake/text_extracted/{filename}.txt`

## Implementation Note
This is DETERMINISTIC CODE (`intake_text_extractor.extract_text_batch`).
It uses pdfplumber/pypdf for PDF, python-docx for DOCX, openpyxl for XLSX.
No LLM is involved. The "agent" designation is for workflow consistency.

## Input Contract
- `file_inventory.json` — files to process (only those with `extractable: true`)
- Files must be readable (not encrypted, not corrupt)

## Output Schema
```json
{
  "schema_name": "cer_intake_document_text_index",
  "schema_version": "v1",
  "project_id": "CER-PJT-XXXX",
  "intake_session_id": "intake-XXXXXXXX",
  "generated_at": "ISO8601 timestamp",
  "total_files_attempted": 0,
  "total_files_extracted": 0,
  "total_files_failed": 0,
  "files": [
    {
      "file_id": "F-001",
      "relative_path": "EP-001/IFU_ABC.pdf",
      "extractable": true,
      "extracted": true,
      "text_extracted_path": "intake/text_extracted/F-001_IFU_ABC.txt",
      "extraction_method": "pypdf | python-docx | openpyxl | txt",
      "character_count": 0,
      "page_count": null,
      "failure_reason": null
    },
    {
      "file_id": "F-002",
      "relative_path": "EP-001/scanned_IFU.pdf",
      "extractable": false,
      "extracted": false,
      "text_extracted_path": null,
      "extraction_method": "none",
      "character_count": 0,
      "page_count": null,
      "failure_reason": "scanned_image_pdf_no_text_layer"
    }
  ],
  "extraction_summary": {
    "pdf_text_extracted": 0,
    "pdf_image_only": 0,
    "docx_extracted": 0,
    "xlsx_extracted": 0,
    "txt_extracted": 0,
    "unsupported_format": 0
  }
}
```

## Quality Gates
- Files marked `readable: true` MUST have actual extracted content
- Extraction failures MUST include a specific reason
- All extractable files should be attempted

## Forbidden Actions
- Do NOT convert files (markitdown is a separate concern)
- Do NOT modify original submitted files
- Do NOT interpret what the text means (that's other agents' job)

## Implementation Note
This is deterministic code, not an LLM agent.
See `intake_text_extractor.py` for the implementation.

## Handoff Targets
- PDF Readability Agent receives PDFs where `extractable: false` or `has_images: true`
- Document Type Detection Agent receives all files with extracted text
- Evidence Classification Agent receives text index for semantic analysis
