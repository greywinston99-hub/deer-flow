# CLINICALTRIALS_GOV FACT MAPPING SPEC

> CCD 签发 | 2026-05-12 | V3-Core

## Problem

ClinicalTrials.gov records currently only enter as screening records. Trial results (outcome measures, enrollment, adverse events) must produce clinical_evidence_fact_table entries.

## Trial Record → Fact Mapping

| Trial Record Field | → Fact Field |
|---|---|
| NCT number | source_anchor |
| Brief title / official title | evidence title |
| Enrollment (actual) | population_n |
| Primary outcome measure + result | fact (endpoint, value, unit) |
| Secondary outcome measure + result | fact (endpoint, value, unit) |
| Serious adverse events (count/rate) | fact (safety endpoint) |
| Other adverse events (count/rate) | fact (safety endpoint) |
| Study type / phase | study_design |
| Completion date | follow_up context |

## Result Extraction

Trial results may be in:
- Structured results section (tabular) → direct extraction (high confidence)
- Free-text results → LLM_inferred (medium confidence)
- No results posted → mark as NO_RESULTS_AVAILABLE

## Evidence Registry Entry

Each trial with results creates one evidence_registry entry:
- source_type = clinical_trial_record
- source_anchor = NCT number
- device_relationship determined by: device/intervention name, technology, intended use, model/manufacturer signals
  (NOT sponsor match alone. NOT device class alone.)
- relationship_rationale: why this relationship was assigned
- relationship_confidence: high / medium / low

---

*CCD 签发：2026-05-12*
