# FACT LAYER INTEGRATION WITH V2 SPEC

> CCD 签发 | 2026-05-12

## How Facts Connect to V2 Evidence Model

```text
Document → Parse → clinical_evidence_fact_table
  → each fact links to evidence_id (existing evidence_registry entry)
  → fact confidence + extraction method feeds into:
      evidence_registry.appraisal (extraction_quality signal)
      evidence_registry.missing_data_flags (table/fact gaps)
  → facts do NOT create new evidence_registry entries directly
  → facts enrich existing entries with structured clinical data
```

## G42 Impact

Fact availability changes G42 behavior:
- Claim with endpoint → fact exists with high confidence → stronger sufficiency signal
- Claim with endpoint → fact exists with low confidence → evidence role capped (no pivotal)
- Claim with endpoint → no fact extracted → existing appraisal applies

## Writer Impact

Writer can reference facts for quantitative claims:
- "The 30-day success rate was 92.3% (95% CI: 87.1-95.8, n=156)"
- Each numeric statement must be fact-anchored (fact_id reference)
- Facts subject to same allowed-use rules as evidence

## Human Review Queue

Low-confidence facts (OCR_recovered, extraction_confidence=low) → human review queue:
- `human_review_queue.json`: fact_id, evidence_id, claim_id, source_page, extraction_method, reason
- Human reviewer can: confirm / correct / reject the fact
- Corrected facts re-enter pipeline with extraction_confidence=human_verified (high)

---

*CCD 签发：2026-05-12*
