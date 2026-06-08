# V4 — Acceptance Checklist

**States:** ☐ NOT_CHECKED | ✅ PASS | ❌ FAIL | ⏭️ DEFERRED
**Evidence required per item:** code | test | runtime | asset | regulatory_decision

---

## Batch I — Strategy Router

- [ ] I.1 Strategy route decision engine implemented (7 routes)
- [ ] I.2 WET 6-condition check implemented
- [ ] I.3 Legacy route: requires PMS data review before passing
- [ ] I.4 Own-data route: requires data quality assessment
- [ ] I.5 Equivalence route: requires data access + 3-dim
- [ ] I.6 Literature-primary route: requires systematic search evidence
- [ ] I.7 Innovation route: requires clinical investigation recommendation
- [ ] I.8 Insufficient evidence: PMCF cannot rescue; requires claim narrowing or CI
- [ ] I.9 Evidence burden engine: weighted factor scoring
- [ ] I.10 Sufficiency decision: gap detection + PMCF/CI recommendation
- [ ] I.11 Route rationale traceable to specific device/product factors
- [ ] I.12 Route visible in CER_REASONING_LEDGER
- [ ] I.13 All Batch I tests pass
- [ ] I.14 Baseline regression pass
- [ ] I.15 Strategy context route and sufficiency decision are separate layers
- [ ] I.16 WET 6-condition check (not 5); borderline → human gate
- [ ] I.17 Legacy MDR gap matrix generated if legacy route selected
- [ ] I.18 Own-data route includes own data quality score
- [ ] I.19 Hard override rules take precedence over scoring

## Batch J — Literature Intelligence

- [ ] J.1 Article role classifier: 8 roles
- [ ] J.2 direct_device_evidence correctly assigned
- [ ] J.3 equivalent_device_evidence correctly assigned
- [ ] J.4 comparator_benchmark correctly assigned
- [ ] J.5 background_sota correctly assigned
- [ ] J.6 safety_signal correctly assigned
- [ ] J.7 excluded correctly assigned (N<10, animal, in-vitro, no match)
- [ ] J.8 Data-use eligibility: benchmark/claim/BR/background
- [ ] J.9 Article-level appraisal: CEBM level, bias, applicability
- [ ] J.10 Role classifier feeds clinical_fact_registry_v2 (article_role field)
- [ ] J.11 Eligibility feeds E0 layer
- [ ] J.12 Excluded articles tracked in PRISMA flow
- [ ] J.13 All Batch J tests pass
- [ ] J.14 Baseline regression pass
- [ ] J.15 Primary + secondary article roles supported
- [ ] J.16 Data-point-level literature role assignment implemented
- [ ] J.17 Role conflict resolution (excluded article data used → FLAG)

## Batch K — CER Blueprints

- [ ] K.1 Blueprint engine: generates route-specific CER structure
- [ ] K.2 WET blueprint: PMS data required, forbids "demonstrates"
- [ ] K.3 Legacy blueprint: gap analysis, forbids "grandfathered"
- [ ] K.4 Own-data blueprint: quality assessment required
- [ ] K.5 Equivalence blueprint: 3-dim + data access
- [ ] K.6 Literature-primary blueprint: systematic search + PMCF
- [ ] K.7 Innovation/insufficient blueprint: CI plan required
- [ ] K.8 Writer tone constraints per route
- [ ] K.9 Forbidden language list per route
- [ ] K.10 Human gate triggers per route
- [ ] K.11 Blueprint output in CER_REASONING_LEDGER
- [ ] K.12 Writer constraints integrated into U6 post-write QA
- [ ] K.13 All Batch K tests pass
- [ ] K.14 Baseline regression pass

## Batch L — NB Explainability + Validation

- [ ] L.1 NB_EXPLAINABILITY_PACKET.json generated
- [ ] L.2 Strategy rationale: factors considered, alternatives rejected
- [ ] L.3 Evidence sufficiency rationale: burden vs available
- [ ] L.4 Literature role rationale: per-article justification
- [ ] L.5 Equivalence rationale: 3-dim + impact analysis
- [ ] L.6 WET/legacy rationale: condition check results
- [ ] L.7 PMCF rationale: why PMCF or why not
- [ ] L.8 BR/GSPR rationale: benefit evidence + risk mitigation
- [ ] L.9 Writer constraint rationale: why strength limited
- [ ] L.10 Each decision traceable to regulatory reference + evidence source
- [ ] L.11 ≥2 real project dry-runs with different strategy routes
- [ ] L.12 Submission readiness check passes
- [ ] L.13 All Batch L tests pass
- [ ] L.14 Baseline regression pass
- [ ] L.15 NB packet includes likely NB challenges and system responses per blueprint
- [ ] L.16 At least one dry-run packet reviewed for NB explainability completeness

## Regulatory Principles

- [ ] R.1 MDR prioritized over MEDDEV where they conflict
- [ ] R.2 Legacy ≠ automatic MDR sufficient
- [ ] R.3 WET requires ALL 6 conditions, not just "low risk"
- [ ] R.4 PMCF cannot rescue unsupported core claim
- [ ] R.5 Equivalence requires data access
- [ ] R.6 Writer conclusion strength ≤ evidence strategy allows

---

**Total: 80 items**
