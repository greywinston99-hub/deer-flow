# V3 CORE VS V3.1 TOOL BOUNDARY

> CCD 签发 | 2026-05-12

## V3-Core (required before pilot resume)

| Category | Tool | Purpose |
|---|---|---|
| PDF parsing | PyMuPDF | Primary text + structure extraction |
| Table extraction | Camelot | Table detection + cell extraction |
| OCR fallback | Tesseract + pdf2image | Scanned PDF text recovery |
| PubMed/PMC | Existing + PMC full-text adapter | Literature retrieval + OA full-text |
| Europe PMC | New MCP adapter | Supplementary literature source |
| ClinicalTrials.gov | New MCP adapter | Trial records + results |
| Clinical fact extraction | New DeerFlow pipeline layer | Structured fact extraction from parsed docs |
| Semantic endpoint mapping | New DeerFlow pipeline layer | Endpoint family classification + claim matching |
| Quantitative normalization | New DeerFlow pipeline layer | Unit/value/statistical normalization + validators |
| Evidence conflict detection | New DeerFlow pipeline layer | Cross-study result comparison + severity flagging |
| ClinicalTrials.gov fact mapping | MCP adapter extension | Trial results → clinical_evidence_fact_table |
| Bilingual extraction | Fact extraction extension | Non-English → English labels + original excerpt + TRANSLATION_NEEDED flag |
| Human review queue | New state/artifact | Low-confidence fact adjudication |

## V3.1+ (post-pilot, when evidence demands)

| Category | Tool | Trigger Condition |
|---|---|---|
| Docling | AI-enhanced PDF/table understanding | When PyMuPDF+Camelot extraction quality proves insufficient on real pilot data |
| GROBID | Academic paper structure parsing | When academic paper volume justifies dedicated tool |
| openFDA / MAUDE | Device adverse event data | When safety claims require MAUDE/vigilance data beyond existing vigilance search |
| EUDAMED | EU device registry | When equivalence/similar-device claims need official registry data |
| WHO ICTRP | Trial registry supplement | When ClinicalTrials.gov coverage insufficient for device class |

## Boundary Rule

V3.1 tools are NOT blocked — they are deferred until evidence from pilot shows the V3-Core tools are insufficient for a specific claim type or data need. Adding tools without demonstrated need = premature optimization.

---

*CCD 签发：2026-05-12*
