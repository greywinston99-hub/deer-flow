# RETRIEVAL TOOL POLICY — CER Authoring V1.0

> Claude Code | 2026-05-15 | Phase 2D

## Active Tools

| Tool | Access Method | Status | Notes |
|------|--------------|--------|-------|
| PubMed E-utilities | Direct API (esearch/efetch/efetch) | ACTIVE | Primary SOTA + device literature source |
| Europe PMC | Direct API + MCP adapter | ACTIVE | Supplementary full-text source |
| PMC Full-text | PubMed E-utilities efetch | ACTIVE | Full-text retrieval for included PMIDs |
| ClinicalTrials.gov | Direct API + MCP adapter | ACTIVE | Trial registry for device clinical data |
| AccessGUDID (FDA) | Direct API | ACTIVE | US device registration lookup |
| EUDAMED Public | Public module web | ACTIVE | EU device registration lookup |

## Unavailable Tools (Subscription/Paywall)

| Tool | Reason | Policy |
|------|--------|--------|
| Embase | Elsevier subscription | Manual export by owner/evaluator |
| ScienceDirect | Elsevier subscription | Manual export by owner/evaluator |
| Cochrane Library | Wiley subscription | Manual export by owner/evaluator |

## MCP Fallback Policy

1. Try MCP adapter first (if available).
2. If MCP unavailable: fall back to direct API call.
3. If both unavailable: record as source_unavailable in search_run_registry.
4. Missing searches must not silently succeed — they must produce explicit gaps.

## Retrieval Completeness

- Target: 200-500 records in retrieved pool (RETRIEVED_RECORD_POOL_TARGET_MIN/MAX)
- Target: 20-40 records in final CER included set (FINAL_CER_INCLUDED_TARGET_MIN/MAX)
- If retrieval is incomplete (MCP gate fail, missing databases): EI outputs marked as provisional
- Provisional: Writer blocked from producing unsupported strong conclusions

## Paywall / Manual Export Policy

1. Paywalled sources identified in search strategy as "requires subscription".
2. Owner/evaluator may manually export PDFs and add to source inventory.
3. Manually added sources go through same evidence appraisal pipeline.
4. Missing paywalled sources recorded as evidence gap, not fabricated.
