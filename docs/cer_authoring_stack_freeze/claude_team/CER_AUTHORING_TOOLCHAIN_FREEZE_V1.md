# CER AUTHORING TOOLCHAIN FREEZE V1.0

> Claude Code | 2026-05-15 | Phase 2D

## PDF Parsing

| Tool | Version/Status | Purpose | Fallback |
|------|---------------|---------|----------|
| PyMuPDF (fitz) | Active | Fast text extraction, page classification | None |
| Camelot | Active (bounded) | Table extraction from digital PDFs | Skip to text |
| Docling | Shadow/Preferred | Deep parsing, scientific PDFs | Disabled for scanned |
| OCR (GLM-OCR) | Active | Image/scanned page text recovery | Manual review flag |
| Page Classifier | Active | Routes pages to appropriate parser | PyMuPDF text |

Parser routing policy: text_digital→shadow, table_digital→shadow, image_scanned→disabled, mixed_page→shadow, text_scientific→shadow, empty_page→disabled.

## Literature Retrieval

| Tool | Status | Access | Fallback |
|------|--------|--------|----------|
| PubMed E-utilities | Active | Direct API | MCP PubMed adapter |
| Europe PMC | Active | Direct API | MCP adapter |
| PMC Full-text | Active | E-utilities efetch | Abstract-only flag |
| ClinicalTrials.gov | Active | Direct API | MCP adapter |
| Embase | UNAVAILABLE | Subscription required | Manual export |
| ScienceDirect | UNAVAILABLE | Subscription required | Manual export |
| Cochrane Library | UNAVAILABLE | Subscription required | Manual export |
| AccessGUDID | Active | Direct API | Manual lookup |
| EUDAMED | Active | Public module | Manual lookup |

## MCP Tool Policy

- MCP tools are optional accelerators, not hard dependencies.
- If MCP server unavailable: fall back to direct API or manual export.
- Missing MCP tools must not block gate execution.
- MCP call logs go to audit artifacts, not CER body.

## Evidence Registry

- evidence_registry: structured JSON with evidence_id, source_type, device_relationship, full_text_status, ledger_approved_for_writer
- Every evidence item must trace to a search/source with query/date/count/URL
- Missing evidence → evidence gap recorded, not fabricated

## Gate Pipeline

### Pre-Writer Gates (existing, unchanged)
- G39: Retrieval domain gate
- G40: Screening depth gate
- G41: Full-text basis gate
- G42: Evidence sufficiency gate
- G46: Pre-writer readiness gate

### Post-Writer Gates (Phase 1 + 2A)
- Gate 1: Device Domain Body Consistency
- Gate 2: IFU Fact Consumption
- Gate 3: Evidence-to-Conclusion Consistency
- Gate 4: Submission Body Cleanliness
- Gate 5: Remediated QA (composite)

### Artifact Routing
- PASS all gates → release candidate directory
- ANY gate HARD_FAIL → quarantine directory + rejection ledger

## Quarantine/Release Routing

- Quarantine: `quarantine/CER_draft_QUARANTINED.md` + `failed_gate_report.json` + `rejection_ledger.json`
- Release candidate: `CER_draft.md` + `CER_draft.docx` + all supporting artifacts
- Audit-only: `reasoning_audit_ledger`, `authoring_workbook`, `calibration_event_log`, gate traces, MCP logs
