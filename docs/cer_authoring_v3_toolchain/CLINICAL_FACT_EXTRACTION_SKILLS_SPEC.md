# CLINICAL FACT EXTRACTION SKILLS SPEC

> CCD 签发 | 2026-05-12

## Definition

Clinical fact extraction converts parsed document content (text + tables) into structured, source-anchored clinical data points that can be linked to claims, endpoints, and evidence items.

## Fact Table Schema

```text
clinical_evidence_fact_table:
  fact_id: FACT-###
  evidence_id: link to evidence_registry
  candidate_claim_ids: list of potential claim matches (nullable at extraction)
  endpoint_family: safety / effectiveness / complication / procedural_success / hemodynamic / device_integrity / quality_of_life
  endpoint_label: human-readable endpoint name
  value_type: rate / mean / median / OR / RR / HR / count / qualitative
  value_numeric: extracted numeric value
  value_unit: % / mmHg / mL / events / score
  population_n: sample size for this endpoint
  follow_up: duration
  CI_lower / CI_upper: confidence interval
  p_value: statistical significance
  comparator: comparator arm description
  source_page: page number in source document
  source_table: table reference in source document
  source_excerpt: extracted text snippet
  extraction_method: direct_text / table_cell / OCR_recovered / LLM_inferred
  extraction_confidence: high / medium / low / OCR_uncertain
  normalizer_status: raw / normalized / needs_human_review
```

## Extraction Methods

| Method | Confidence | When Used |
|---|---|---|
| direct_text | high | Cleanly extractable from structured text |
| table_cell | high | From parsed table with clear headers |
| OCR_recovered | low | From OCR-fallback text |
| LLM_inferred | medium | AI-extracted from unstructured prose |

## Confidence Rules — Extraction Method + Validators

Confidence is determined by extraction method AND post-extraction validators. Not solely by method.

Validators (all must pass for final confidence = high):
  numeric_sanity: value within clinically plausible range
  unit_consistency: unit matches endpoint expectation
  denominator_numerator_check: n/N consistency
  source_excerpt_cross_check: extracted value matches source text snippet

Final confidence = min(extraction_method_confidence, lowest_validator_confidence):

| Extraction Method | Method Confidence | With All Validators Pass | With ≥1 Validator Fail |
|---|---|---|---|
| direct_text | high | high → eligible for pivotal/supportive | medium → supportive only |
| table_cell | high | high → eligible for pivotal/supportive | medium → supportive only |
| LLM_inferred | medium | medium → supportive only | low → background only |
| OCR_recovered | low | low → background only, human verification required | low → background only |

## Bilingual Extraction

Non-English documents are not ignored:
  - Fact extraction preserves original_excerpt (source language)
  - Field labels normalized to English
  - Values extracted as-is (numeric values language-independent)
  - source_language tagged per fact
  - No auto-translation as source replacement
  - If translation is needed → human_review_queue with TRANSLATION_NEEDED flag

## Integration with V2

- Each fact links to evidence_id and claim_id
- Fact confidence aggregated into evidence_registry.appraisal fields
- Facts do NOT bypass evidence_registry or G42
- Low-confidence facts → evidence role capped at background

---

*CCD 签发：2026-05-12*
