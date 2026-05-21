# S-INIT-01: Source File Classification

- **Type**: Few-shot
- **Step**: Initialize (Step 1)
- **Batch**: P2
- **Agent**: authoring-intake-profile-claim-agent

## Input
- `uploaded_files`: list of file paths/names
- File MIME types and content samples

## Output
- `source_inventory` with `document_type` field tagged per file

## Decision Logic
1. Check filename for keywords: "ifu" / "instruction" → IFU; "rmf" / "risk" → RMF; "pms" / "pmcf" → PMS; "cer" → previous CER
2. If filename ambiguous, sample first 500 chars of text content
3. Chinese filename: detect encoding, extract English equivalent
4. Scanned PDF: flag `is_scanned_pdf=true`, trigger OCR path
5. Confidence < 0.9 → mark for human review

## Checks
- All uploaded files have a `document_type` assignment
- No file left as "unknown" without human review flag
- Scanned PDFs have `ocr_confidence` recorded
