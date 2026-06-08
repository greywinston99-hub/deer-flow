# V4 — Batch J: Literature Intelligence V2

**Target:** P0-3 (Literature Intelligence V2)
**Dependencies:** Literature Intelligence Requirements (`V4_LITERATURE_INTELLIGENCE_REQUIREMENTS.md`)

---

## 1. Design

### 1.1 Article Role Classifier

**Input per article:** study_design, sample_size, population_match, endpoint_match, device_match, indication_match, fulltext_basis, evidence_tier

**Output:**
```json
{
  "article_role": "direct_device_evidence | equivalent_device_evidence | ... | excluded",
  "role_confidence": "high | medium | low",
  "role_rationale": "为什么分配这个角色",
  "data_use_eligibility": {
    "benchmark_eligible": true/false,
    "claim_support_eligible": true/false,
    "BR_GSPR_eligible": true/false,
    "background_eligible": true/false,
    "limitations": [...]
  }
}
```

### 1.2 Article-Level Appraisal

Per article:
- Oxford CEBM level (1a–5)
- Risk of bias (low/moderate/high)
- Applicability (direct/indirect/not_applicable)
- Follow-up adequacy
- Sample size adequacy

### 1.3 Role Assignment Rules

| Condition | Role |
|:---|:---|
| device_match = subject_device AND fulltext_basis = obtained | `direct_device_evidence` |
| device_match = equivalent_device AND data_access = confirmed | `equivalent_device_evidence` |
| device_match = similar AND endpoint_match ≥ partial | `similar_device_context` |
| population/indication match AND comparator endpoint | `comparator_benchmark` |
| population/indication match AND alternative therapy | `alternative_treatment` |
| general SOTA, no specific device data | `background_sota` |
| AE/safety report, recall, safety alert | `safety_signal` |
| N<10 OR animal/in-vitro OR no_population_match | `excluded` |

### 1.4 Integration with V3

- Article role classifier feeds into V3's clinical_fact_registry_v2 (adds `article_role` field)
- Evidence eligibility feeds into V3's E0 eligibility layer
- Benchmark eligibility feeds into V3's comparator benchmark checker
- Excluded articles tracked in PRISMA flow

## 2. Tests

- [ ] Subject device clinical investigation → `direct_device_evidence`
- [ ] Equivalent device data with access → `equivalent_device_evidence`
- [ ] Tourniquet efficacy study → `comparator_benchmark`
- [ ] Epidemiology review → `background_sota`
- [ ] N=2 case report → `excluded`
- [ ] Abstract-only with numerical claim → limitation applied
- [ ] Animal study → `excluded` from clinical evidence
- [ ] Role classifier output visible in evidence_registry

## 3. Acceptance

**Batch J PASS:** Classifier correctly roles ≥10 articles from fixtures. At least 1 article per role type. Excluded articles correctly categorized. Eligibility flags correct.
