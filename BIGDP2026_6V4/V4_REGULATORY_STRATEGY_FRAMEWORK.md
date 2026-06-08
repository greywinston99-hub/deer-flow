# V4 — Regulatory Strategy Framework

**Purpose:** Define all CER strategy routes, evidence burden factors, and decision logic.

---

## 1. Strategy Routes

### Route 1 — WET (Well-Established Technology)

**触发条件：** ALL 6 conditions must be met
1. Device technology is well-established and stable
2. Low risk (Class I/IIa typically; Class IIb only with strong justification)
3. State of the art is stable
4. PMS/PMCF data sufficient (≥2–3 years of post-market data)
5. Benefit-risk is clearly acceptable
6. Intended purpose is narrow and well-defined

**WET borderline rule:** Class IIb, implantable, active, long-term use, or severe AE devices → human_gate_required even if 6 conditions appear met. WET is NOT an automatic pass.

**证据要求：** Lower clinical evidence level acceptable. Literature review must demonstrate SOTA stability. PMS data must be sufficient.
**不可接受的 shortcut：** Assuming WET without PMS data review. Assuming WET for implantable/high-risk without explicit justification. WET borderline without human gate.

### Route 2 — Legacy Device

**触发条件：** Device previously CE-marked under MDD/AIMDD
**关键原则：** Legacy does NOT automatically equal MDR sufficient clinical evidence. Must demonstrate:
- Clinical evidence from pre-MDR period remains valid
- PMS/PMCF data since market introduction supports continued safety/performance
- No significant safety signals emerged
- State of the art has not substantially changed

**证据要求：** Pre-MDR clinical data + post-market surveillance data. Gap analysis between MDD and MDR requirements.
**不可接受的 shortcut：** Claiming legacy = sufficient without PMS data review.

### Route 3 — Own Clinical Data Primary

**触发条件：** Manufacturer holds substantial own clinical data from clinical investigations, PMS, PMCF, complaints, vigilance.
**关键原则：** Strategy focus shifts from external literature to own data quality.
**证据要求：** Clinical investigation data quality assessment. PMS/PMCF data completeness. Complaints/vigilance trend analysis.
**不可接受的 shortcut：** Using own data without quality assessment. Ignoring external SOTA.

### Route 4 — Equivalence-Supported

**触发条件：** Equivalent device identified with sufficient data access.
**关键原则：** Technical/biological/clinical 3-dim comparison required. Data access contract required.
**证据要求：** Full 3-dim comparison. Differences impact analysis. Equivalent device clinical evidence package.
**不可接受的 shortcut：** Claiming equivalence without data access. Using equivalent evidence as direct proof.

### Route 5 — Literature-Primary

**触发条件：** No equivalent device. No substantial own data. No WET claim.
**关键原则：** All clinical support from published literature + own pre-clinical data.
**证据要求：** Comprehensive systematic literature review. SOTA benchmark derivation. PMCF plan for residual uncertainty.
**不可接受的 shortcut：** Selective literature citation. Missing comparator benchmark.

### Route 6 — Innovation / Novel Device

**触发条件：** Novel technology. No predicate. No established comparator. Unclear risk profile.
**关键原则：** Full clinical investigation likely required. CER = justification for clinical investigation design + PMCF plan.
**证据要求：** Pre-clinical data. Literature on similar/analogous technologies. Clinical investigation plan.
**不可接受的 shortcut：** Claiming sufficient evidence without clinical investigation.

### Route 7 — Insufficient Evidence

**触发条件：** Evidence gap cannot be closed by literature, equivalence, or PMS.
**关键原则：** Cannot issue positive CER conclusion.
**证据要求：** Clear identification of evidence gaps. Recommendation for clinical investigation or PMCF study.
**不可接受的 shortcut：** PMCF cannot rescue unsupported core claim.

---

## 2. Strategy Route Decision Table

| Factor | WET | Legacy | Own-Data | Equivalence | Literature | Innovation | Insufficient |
|:---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| MDR Class I/IIa | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| MDR Class IIb | ⚠️ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| MDR Class III | ❌ | ⚠️ | ✅ | ✅ | ⚠️ | ❌ | ✅ |
| Implantable | ❌ | ⚠️ | ✅ | ✅ | ⚠️ | ❌ | ✅ |
| WET established | ✅ | — | — | — | — | ❌ | — |
| Equivalent identified | — | — | — | ✅ | ❌ | ❌ | — |
| Own data sufficient | — | — | ✅ | — | ❌ | ❌ | ❌ |
| Novel technology | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| High residual risk | ❌ | ❌ | ⚠️ | ⚠️ | ❌ | ❌ | ✅ |

---

## 3. Strategy Router: Double-Layer Output

Route classification and sufficiency decision are SEPARATE layers. A legacy device with insufficient evidence is `strategy_context_route = legacy, sufficiency_decision = insufficient`, NOT `route = insufficient_evidence`.

**Layer 1 — Strategy Context Route:** What regulatory strategy scenario does this product belong to?

**Layer 2 — Sufficiency Decision:** Within that scenario, is evidence sufficient?

```json
{
  "strategy_context_route": "WET | legacy | own_data_primary | equivalence | literature_primary | innovation",
  "route_confidence": "high | medium | low",
  "sufficiency_decision": "sufficient | partially_sufficient | insufficient | cannot_support",
  "final_CER_strategy": "legacy_with_gap | WET_supported | equivalence_limited | literature_primary_with_PMCF | innovation_CI_required",
  "alternative_routes_rejected": ["equivalence (no equivalent identified)", "WET (Class IIb borderline)"],
  "required_next_action": "proceed | claim_narrowing | PMCF | clinical_investigation | human_gate"
}
```

## 4. Evidence Burden Factors (with Hard Overrides)

Scoring provides initial estimate but hard overrides take precedence.

**Hard Override 1:** Unsupported core clinical claim → `cannot_support` regardless of score.
**Hard Override 2:** Equivalence without data access → route blocked, not scored.
**Hard Override 3:** WET without PMS/PMCF data review → route blocked, not scored.
**Hard Override 4:** Innovation without clinical investigation plan → `insufficient` regardless of score.

Every burden output must include: `evidence_burden_rationale`, `score_drivers`, `manual_override_required` (boolean).

## 5. Evidence Burden Factors

| Factor | Weight | Impact |
|:---|:--:|:---|
| MDR class (I→III) | HIGH | Class III requires strongest evidence |
| Implantable / invasive / active | HIGH | Implantable requires longitudinal data |
| WET status | HIGH | WET reduces burden if conditions met |
| Legacy status | MEDIUM | Legacy does not automatically reduce burden |
| Novelty | HIGH | Novel increases burden significantly |
| Risk profile | HIGH | Higher risk = higher burden |
| Claim strength | MEDIUM | Strong claims require strong evidence |
| Own data availability | HIGH | Own data may shift strategy |
| SOTA stability | MEDIUM | Unstable SOTA increases burden |
| Alternative treatment risk | LOW | Higher risk alternatives may lower bar |
| Vulnerable population | HIGH | Increases burden |
| AE severity | HIGH | Severe AE requires strong safety data |

---

## 6. Legacy Route: MDR Gap Analysis Matrix

Legacy is not a route label — it requires structured gap analysis. Required artifact: `LEGACY_MDR_GAP_ANALYSIS_MATRIX`.

| Dimension | Assessment |
|:---|:---|
| Pre-MDR evidence sources | What clinical data existed under MDD? |
| MDR Article 61 / Annex XIV gap | What new MDR requirements are unmet? |
| GSPR gap | Which GSPR clauses lack current evidence? |
| SOTA change | Has state of the art substantially changed? |
| PMS coverage period | How many years of PMS data exist? |
| PMCF coverage | Has PMCF been conducted? Results? |
| Complaint/vigilance trend | Any safety signals emerged? |
| Equivalent data available | Can equivalent device data fill gaps? |
| IFU/intended purpose change | Has IFU changed since MDD certification? |
| Risk profile change | Has risk profile changed? |
| Old clinical claims still valid | Are original claims still supportable? |
| Residual gap | What remains unaddressed? |
| Required action | claim_narrowing / PMCF / clinical_investigation / human_gate |

## 7. Own-Data Route: Data Quality Score

`own_data_exists ≠ own_data_sufficient`. Required: `OWN_DATA_QUALITY_SCORE`.

| Dimension | Scoring |
|:---|:---|
| data_source_type | clinical_investigation(3) / PMCF(2) / PMS(2) / complaint(1) / other(0) |
| sample_size adequacy | adequate(3) / borderline(1) / inadequate(0) |
| follow_up adequacy | adequate(3) / borderline(1) / inadequate(0) |
| endpoint_alignment | full(3) / partial(1) / none(0) |
| population_match | full(3) / partial(1) / none(0) |
| data_completeness | ≥90%(3) / 70-89%(1) / <70%(0) |
| bias_risk | low(3) / moderate(1) / high(0) |
| AE_capture | systematic(3) / partial(1) / absent(0) |
| complaint/vigilance_linkage | linked(2) / unlinked(0) |
| representativeness | representative(3) / partial(1) / unknown(0) |

Score ≥24 → high; 15–23 → moderate; 8–14 → low; <8 → unusable.

## 8. PMCF / Clinical Investigation Decision Points

| Scenario | PMCF? | Clinical Investigation? |
|:---|:--:|:--:|
| All claims supported by evidence | PMCF for ongoing surveillance | No |
| Residual uncertainty | PMCF to close specific gaps | No |
| Core claim unsupported | PMCF NOT sufficient | Yes, or claim narrowing |
| Novel high-risk device | PMCF + Clinical Investigation | Yes |
| WET with strong PMS | Routine PMCF | No |
| Legacy with safety signals | Enhanced PMCF | Possibly |
