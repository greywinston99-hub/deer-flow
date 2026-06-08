# V4 — Batch I: Regulatory Strategy Router

**Target:** P0-1 (Clinical Evaluation Strategy Router) + P0-2 (Evidence Burden & Sufficiency Engine)
**Dependencies:** Regulatory Strategy Framework (`V4_REGULATORY_STRATEGY_FRAMEWORK.md`)

---

## 1. Design

### 1.1 Strategy Route Decision Engine

**Input:** device_profile, intended_purpose, mdr_class, implantable_flag, WET_indicators, legacy_status, own_data_availability, equivalent_identified, novelty_flags, risk_profile, claim_ledger

**Output:**
```json
{
  "strategy_route": "WET | legacy | own_data_primary | equivalence | literature_primary | innovation | insufficient_evidence",
  "route_rationale": "为什么选这条路",
  "evidence_burden_level": "low | moderate | high | very_high",
  "required_evidence_sources": ["PMS_data", "clinical_investigation", ...],
  "PMCF_need": "routine | enhanced | critical | not_applicable",
  "clinical_investigation_need": "required | recommended | not_required",
  "writer_conclusion_constraints": "strong_allowed | moderate_only | limited_only | not_supported"
}
```

### 1.2 Route Decision Logic (Double-Layer)

**Layer 1 — Strategy Context Route** (what scenario?):
1. Novel device, no predicate, unclear risk? → `innovation`
2. All 6 WET conditions met? → `WET` (borderline → human_gate)
3. Equivalent device identified + data access? → `equivalence`
4. Substantial own clinical data? → `own_data_primary`
5. Previously CE-marked under MDD/AIMDD? → `legacy`
6. Otherwise → `literature_primary`

**Layer 2 — Sufficiency Decision** (is evidence enough?):
- `sufficient`: evidence meets burden for route
- `partially_sufficient`: gaps exist but PMCF may close
- `insufficient`: PMCF alone insufficient; need CI or claim narrowing
- `cannot_support`: core claim unsupported regardless of route

**Final strategy** = Layer 1 + Layer 2 combined (e.g., `legacy_with_gap`, `WET_supported`).

**Hard Overrides (take precedence over scoring):**
- Unsupported core clinical claim → `cannot_support`
- Equivalence without data access → route blocked
- WET without PMS/PMCF data → route blocked
- Innovation without CI plan → `insufficient`

### 1.3 Evidence Burden Engine

Compute `evidence_burden_level` from weighted factors:
- MDR class (I=1, IIa=2, IIb=3, III=4) × 2
- Implantable (+2), Invasive (+1), Active (+1)
- Novelty (+3), WET (−3)
- High risk profile (+2)
- Vulnerable population (+2)
- Strong claims (+1)

Score ≤5 → low; 6–10 → moderate; 11–15 → high; ≥16 → very_high.

### 1.4 Sufficiency Decision

Compare `evidence_burden_level` to actual available evidence:
- available_evidence_level ≥ required → `sufficient`
- available_evidence_level = required−1 → `partially_sufficient` → PMCF recommended
- available_evidence_level < required−1 → `insufficient` → PMCF NOT sufficient; clinical investigation or claim narrowing

## 2. Tests

- [ ] All 7 routes triggerable from fixture data
- [ ] WET route blocked when any 6-condition fails
- [ ] Legacy route requires PMS data review
- [ ] Equivalence route requires data access + 3-dim
- [ ] Innovation route → clinical investigation recommended
- [ ] Insufficient evidence route → PMCF cannot rescue
- [ ] Evidence burden score matches expected for Class III implantable
- [ ] Strategy route visible in CER_REASONING_LEDGER

## 3. Acceptance

**Batch I PASS:** Strategy router generates correct route for ≥5 fixture scenarios. Evidence burden engine produces plausible level. Route rationale is traceable to specific factors.
