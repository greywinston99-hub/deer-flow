# V4 — Batch K: Strategy-Specific CER Blueprints

**Target:** P0-4 (Strategy-Specific CER Blueprint)
**Dependencies:** Strategy Router (Batch I) + Strategy Blueprints (`V4_STRATEGY_SPECIFIC_CER_BLUEPRINTS.md`)

---

## 1. Design

### 1.1 Blueprint Engine

**Input:** strategy_route from Batch I + device_profile + claim_ledger

**Output per route:**
```json
{
  "route": "WET | legacy | ...",
  "cer_argument_structure": {
    "section_3_focus": "...",
    "section_4_focus": "...",
    "section_5_focus": "...",
    "section_6_focus": "...",
    "section_7_focus": "..."
  },
  "required_evidence": [...],
  "acceptable_evidence": [...],
  "unacceptable_shortcuts": [...],
  "PMCF_role": "routine | enhanced | critical | not_applicable",
  "BR_GSPR_focus": "...",
  "writer_tone": "factual_moderate | evidence_supported | limited_evidence | pre_clinical_promise",
  "limitation_language": "...",
  "NB_likely_questions": [...],
  "human_gate_triggers": [...]
}
```

### 1.2 Writer Constraints per Route

| Route | Allowed Conclusion Strength | Forbidden Language |
|:---|:---|:---|
| WET | moderate | demonstrates, proves, superior |
| Legacy | moderate | automatically MDR-compliant, grandfathered |
| Own-Data | up to strong (if data quality high) | (most allowed if data quality verified) |
| Equivalence | moderate (limitation: "based on equivalent device data") | direct evidence, demonstrates |
| Literature | limited to moderate | demonstrates, proves, sufficient |
| Innovation | limited or not_supported | safe and effective without clinical data |
| Insufficient | not_supported | any positive conclusion |

### 1.3 Route-Specific Human Gates

| Route | Human Gate Trigger |
|:---|:---|
| WET | Any WET condition borderline |
| Legacy | PMS data insufficient or safety signals |
| Own-Data | Data quality concern flagged |
| Equivalence | Data access uncertain or 3-dim borderline |
| Literature | Evidence level significantly below burden |
| Innovation | Clinical investigation design review |
| Insufficient | Claim narrowing decision |

### 1.4 Integration

- Batch I strategy_route → Batch K blueprint engine
- Blueprint output → CER_REASONING_LEDGER (strategy section)
- Writer constraints → integrated into U6 post-write QA (new detector: route_specific_tone_check)
- Human gate triggers → HC routing

## 2. Tests

- [ ] WET blueprint: requires PMS data, forbids "demonstrates"
- [ ] Legacy blueprint: requires gap analysis, forbids "grandfathered"
- [ ] Own-data blueprint: requires quality assessment
- [ ] Equivalence blueprint: requires 3-dim + data access
- [ ] Literature blueprint: requires systematic search + PMCF plan
- [ ] Innovation blueprint: requires clinical investigation plan
- [ ] Writer tone constraints per route applied correctly
- [ ] Human gate triggers fire on borderline cases

## 3. Acceptance

**Batch K PASS:** All 6 blueprints generate correct output for matched strategy route. Writer constraints per route tested. Human gate triggers correct.
