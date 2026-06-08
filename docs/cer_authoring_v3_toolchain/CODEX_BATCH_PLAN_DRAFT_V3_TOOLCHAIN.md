# CODEX BATCH PLAN DRAFT — V3 TOOLCHAIN

> CCD 签发 | 2026-05-12 | Draft — not yet authorized

## Batch 7.1 — PDF/DOCX Parsing + Table Extraction

Problem: 71-86% of evidence is abstract-only. PDF full-texts in 01_ folder not structurally parsed. No table extraction.

Goal: PyMuPDF primary parser + Camelot table extraction. Structured output per document.

Boundary: Not clinical fact extraction. Not appraisal. Existing pipeline unchanged. 138+ tests pass.

## Batch 7.2 — OCR Fallback + Document Parsing Lineage

Problem: Scanned PDFs produce zero text.

Goal: Tesseract + pdf2image fallback. OCR quality signals. Lineage tracking per document.

Boundary: OCR only when PyMuPDF fails. Quality signals → fact confidence. No auto-translation.

## Batch 7.3 — Clinical Source MCP Adapters

Problem: Only PubMed is integrated. No PMC full-text, Europe PMC, ClinicalTrials.gov.

Goal: PMC efetch adapter + Europe PMC REST adapter + ClinicalTrials.gov REST adapter. MCP-native.

Boundary: Retrieval only. No appraisal. Records enter same screening pipeline as PubMed.

## Batch 7.4 — Clinical Fact Extraction

Problem: Parsed document content not converted to structured clinical data points.

Goal: Clinical fact extraction from parsed text + tables. clinical_evidence_fact_table schema. Confidence-gated (method + validators). Linked to evidence_id + claim_id. Bilingual extraction with source language preservation.

Boundary: Facts enrich evidence, don't replace it. Low-confidence facts → background only.

## Batch 7.5 — Semantic Endpoint Mapping + Quantitative Normalization + Conflict Detection

Problem: Endpoints not semantically mapped. Values not normalized. Conflicting evidence not detected.

Goal: Semantic endpoint family classification. Quantitative normalization (unit, format, statistics). Evidence conflict detection (directional, magnitude, statistical). ClinicalTrials.gov trial record → fact mapping.

Boundary: Normalization failures → human review. CRITICAL conflicts cap evidence role.

## Batch 7.6 — Fact Layer Integration + Human Review Queue

Problem: Facts not consumed by G42. Human review path missing for low-confidence facts.

Goal: Fact confidence → G42 signal. Human review queue for low-confidence facts. Writer can reference fact-anchored quantitative claims.

Boundary: No automated fact promotion. Human_verified → high confidence only after human confirms.

## Batch 7.7 — Integration Validation (CCD-managed)

V3-Core toolchain validation on CAL-001 + 1 new document type. Fact extraction quality assessment. Pilot resume decision.

---

*CCD 签发：2026-05-12 | Draft — not yet authorized*
