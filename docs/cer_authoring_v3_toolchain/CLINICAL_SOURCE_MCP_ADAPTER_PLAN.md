# CLINICAL SOURCE MCP ADAPTER PLAN

> CCD 签发 | 2026-05-12

## Current State

PubMed fetch/fetch_abstracts/verify_citation → existing MCP tools in deer-flow.
All other external clinical sources → not integrated.

## V3-Core MCP Adapters

| Source | API | Data Retrieved | V3 Priority |
|---|---|---|---|
| NCBI PubMed | E-utilities (existing) | Abstracts, metadata | Existing — keep |
| NCBI PMC | E-utilities efetch | Full-text XML (OA subset) | **V3-Core: new adapter** |
| Europe PMC | REST API | Abstracts + full-text links + grants | **V3-Core: new adapter** |
| ClinicalTrials.gov | REST API v2 | Trial records, results, locations | **V3-Core: new adapter** |

## V3.1+ (post-pilot)

| Source | Purpose |
|---|---|
| openFDA | Device adverse events, recalls (MAUDE substitute) |
| EUDAMED | European device registry |
| WHO ICTRP | Trial registry supplement |

## MCP Adapter Pattern

Each adapter:
- Input: query terms, filters (date, study type, status)
- Output: structured records in deer-flow native format (≠ raw API response)
- Each record carries: source_db, record_id, retrieval_timestamp, query_signature
- Adapter does NOT perform appraisal — that's evidence_appraisal pipeline

## Integration with Evidence Pipeline

```text
MCP Adapter → records → screening → evidence_registry
Same screening/appraisal pipeline as PubMed literature.
source_type = literature_<source_db>.
```

---

*CCD 签发：2026-05-12*
