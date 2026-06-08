# V3 TOOLCHAIN ARCHITECTURE SPEC

> CCD 签发 | 2026-05-12 | Planning only

## 一、V3 工具链总图

```text
RAW INPUT (01_INITIAL_INPUT_FOR_WRITER)
  ├── PDF/DOCX → Document Parsing Pipeline → structured_text + tables
  ├── Images/Scanned PDF → OCR Fallback → text
  └── External DB → MCP Adapters → clinical_records + trial_data

PARSED OUTPUT
  → Clinical Fact Extraction → clinical_evidence_fact_table
    (fact_id, claim_id, evidence_id, endpoint, value, unit, population, CI, p-value, source_page, source_table, extraction_confidence)

  → Integration with V2 Evidence Model
    (source_anchor updated with page/table reference, fact extraction confidence added to evidence_registry)
```

## 二、核心工具层

| Layer | V3-Core | V3.1+ |
|---|---|---|
| PDF Parsing | PyMuPDF (text + structure) | Docling (AI-enhanced) |
| Table Extraction | PyMuPDF + Camelot | Docling tables |
| DOCX Parsing | python-docx (existing) | — |
| OCR Fallback | Tesseract + pdf2image | — |
| Structured Document (GROBID) | — | GROBID (academic papers) |
| PubMed/PMC | Existing pubmed_fetch MCP | PMC full-text via Entrez |
| Europe PMC | Europe PMC API MCP adapter | — |
| ClinicalTrials.gov | ClinicalTrials.gov API MCP adapter | — |
| openFDA / MAUDE | — | V3.1 safety extension |

## 三、DeerFlow 集成原则

- 外部临床数据库（PubMed/PMC/Europe PMC/ClinicalTrials.gov）→ MCP adapters
- 本地文档解析工具（PyMuPDF/Camelot/Tesseract）→ DeerFlow-native tool adapters/skills（不强制 MCP）
- 所有输出必须写入 SharedAuthoringState → artifacts → gates → lineage
- Fact extraction 不绕过 evidence_registry — fact → evidence link 必须可追溯
- OCR/table 不确定性必须反映在 extraction_confidence 中
- 不允许工具绕过 gate / artifact contract 直接写入 Writer 消费区

## 四、数据流关键约束

```text
PDF text extraction ≠ clinical fact extraction
MCP retrieval ≠ evidence sufficiency
High extraction_confidence ≠ automatically pivotal/supportive
Low extraction_confidence → evidence_role capped at background
```

---

*CCD 签发：2026-05-12*
