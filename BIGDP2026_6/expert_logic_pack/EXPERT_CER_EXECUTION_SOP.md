# Expert CER Execution SOP

**Document:** BIGDP2026.6 Expert Logic Pack — Standard Operating Procedure
**Audience:** CER regulatory engineers + system implementers
**Purpose:** Define the expert execution workflow — how a 10+ year regulatory engineer executes CER work, encoded as system-enforceable rules.

---

## 1. Product Identity First

Before any literature search, evidence appraisal, or claim analysis, the expert engineer establishes product identity.

| Step | Action | Output | Gate |
|:---|:---|:---|:---|
| 1.1 | Confirm device name, model, variant | `device_profile.device_name` | HC-01 |
| 1.2 | Confirm intended purpose (what the device does, for whom, where) | `device_profile.intended_use` | HC-01 |
| 1.3 | Identify target population (age, condition, comorbidities) | `device_profile.target_population` | HC-01 |
| 1.4 | Identify anatomical site / application location | `device_profile.anatomical_site` | HC-01 |
| 1.5 | Confirm mechanism of action (how it works) | `device_profile.mechanism_of_action` | HC-01 |
| 1.6 | Extract indications, contraindications, warnings from IFU | `device_profile.indications` | HC-02 |
| 1.7 | Confirm MDR classification (I, IIa, IIb, III) | `device_profile.device_class` | G_DP_STATE |

**Rule:** If product identity is uncertain, STOP. Do not proceed to claim extraction. Trigger HC-01 human gate.

---

## 2. Claim Boundary Second

From the IFU and device understanding, the expert engineer identifies what the manufacturer claims the device does. Claims are then classified, bounded, and assessed.

| Step | Action | Output |
|:---|:---|:---|
| 2.1 | Extract all statements from IFU that could be claims | `claim_ledger[]` |
| 2.2 | Classify each claim (clinical performance, clinical safety, usability, warning, non-clinical) | `claim_ledger[].claim_type` |
| 2.3 | Flag marketing language that overstates evidence | IFU evolution ledger `marketing_language_detected` |
| 2.4 | Identify claims that appear unsupported by any plausible evidence | `gap_disposition: cannot_support` |
| 2.5 | Identify claims that are merely administrative (device name, materials) — no clinical evidence needed | `non_clinical` classification |
| 2.6 | Set claim criticality (high/medium/low) | `claim_criticality` |

**Rule:** Marketing claims MUST NOT directly become CER conclusions. Every transformation must have a recorded reason.

---

## 3. Evaluation Route Selection

The expert engineer selects one or more evaluation routes based on device characteristics and available data.

| Route | When to Use | Key Requirement |
|:---|:---|:---|
| **Literature route** | No equivalent device; clinical data from published studies | Systematic literature search per MDR Annex XIV |
| **Equivalence route** | Equivalent device exists with accessible technical/clinical data | MDR Annex XIV 3-dimension comparison (clinical/technical/biological) |
| **Own clinical data route** | Manufacturer has clinical investigation data on subject device | CIP compliance; GCP; ISO 14155 |
| **PMS / PMCF route** | Post-market data available; pre-market data insufficient | PMCF plan; PMS data per MDR Articles 83-86 |
| **Mixed route** | Combination of above | Document which claims use which route |

**Rule:** Equivalence route requires ALL THREE dimensions to match (structure, mechanism, indication). Scenario-only match → alternative therapy, NOT equivalence.

---

## 4. PICO / Endpoint / Benchmark Derivation

| Step | Action | Output |
|:---|:---|:---|
| 4.1 | For each claim, derive PICO (Population, Intervention, Comparator, Outcome) | `pico_derivation` |
| 4.2 | Map PICO outcomes to clinical endpoints | `endpoint_registry[]` |
| 4.3 | For each endpoint, search SOTA literature for benchmark values | `sota_benchmark_table[]` |
| 4.4 | Assess benchmark directness (direct/indirect/fallback) | `BENCHMARK_DERIVATION_TRACE.directness` |
| 4.5 | Assess benchmark confidence (high/medium/low) | `BENCHMARK_DERIVATION_TRACE.confidence` |
| 4.6 | Write acceptability rationale | `BENCHMARK_DERIVATION_TRACE.acceptability_rationale` |
| 4.7 | If fallback benchmark, write alternatives rejected rationale | `BENCHMARK_DERIVATION_TRACE.alternatives_rejected_rationale` |

**Rule:** A benchmark is NEVER a naked number. It MUST have source studies, comparability, directness, confidence, acceptability rationale. Fallback benchmarks MUST state limitations.

---

## 5. Evidence Appraisal

| Step | Action | Output |
|:---|:---|:---|
| 5.1 | For each study, assess evidence quality per MDCG 2020-6 | `evidence_registry[].quality_score` |
| 5.2 | Classify evidence support type (direct/indirect/equivalent/manufacturer/PMS/insufficient) | `evidence_support_type` |
| 5.3 | Assess population comparability | `population_comparability` |
| 5.4 | Assess device comparability | `device_comparability` |
| 5.5 | Assess source type (RCT, prospective, retrospective, registry, case series) | `study_design` |
| 5.6 | Identify limitations per study | `limitations[]` |
| 5.7 | Weight evidence by relevance and quality | `relevance_weight`, `quality_weight` |

**Rule:** Direct evidence on the subject device carries the highest weight. Equivalent device evidence is NOT direct evidence. Manufacturer bench data alone cannot support clinical claims.

---

## 6. Gap Disposition

When evidence is insufficient for a claim, the engineer must disposition the gap.

| Gap Pattern | Disposition | Action |
|:---|:---|:---|
| Evidence fully supports claim | `no_gap` | Proceed |
| Evidence exists but is weak or limited | `PMCF` | Recommend PMCF study; allow CER with limitations |
| Claim wording overstates evidence | `claim_narrowing` | Narrow claim scope in CER |
| IFU claim cannot be supported | `cannot_support` | BLOCK; claim must be removed or downgraded |
| Safety claim lacks RMF/GSPR | `risk_control` | Require risk control documentation |
| Administrative claim unverifiable | `labeling` | Recommend labeling update |
| Ambiguous borderline case | `human_gate_required` | Trigger human review |

**Rule:** `cannot_support` disposition BLOCKS the Writer for that claim. `PMCF` allows writing with documented limitations.

---

## 7. BR / GSPR / RMF / IFU Alignment

| Step | Action |
|:---|:---|
| 7.1 | Verify CER benefit conclusions do not contradict RMF risk assessments |
| 7.2 | Verify CER safety claims are supported by GSPR checklist |
| 7.3 | Verify CER clinical claims are consistent with IFU indications |
| 7.4 | Flag misalignments as `alignment_gate` issues |

**Rule:** CER conclusion cannot conflict with risk file, GSPR, or IFU. Safety claims require RMF/GSPR/IFU support.

---

## 8. Writer Release

The expert engineer does NOT release the Writer until all conditions are met.

| Condition | Check |
|:---|:---|
| Product identity confirmed | `device_profile` locked |
| Claim ledger complete | `CER_REASONING_LEDGER` populated |
| Evidence links established | `claim_evidence_matrix` complete |
| SOTA benchmarks traceable | `BENCHMARK_DERIVATION_TRACE` populated |
| IFU claims evolved | `IFU_CLAIM_EVOLUTION_LEDGER` populated |
| Gaps dispositioned | No `cannot_support` claims without explicit human decision |
| BR justified | `benefit_risk_ledger` complete |
| GSPR/RMF aligned | `alignment_matrix` complete |
| Package exported | `CER_INPUT_PACKAGE.json` with `package_schema_version` |

**Rule:** Writer must not reason from raw IFU or raw evidence. Writer may only write from gate-passed expert ledgers and validated CER_INPUT_PACKAGE. Writer must not strengthen conclusion beyond evidence support.

---

## Expert Execution Checklist

Before Writer release, the expert engineer (or system) confirms:

- [ ] Product identity is confirmed (device name, class, intended use, MoA, population)
- [ ] All IFU claims are extracted, classified, and bounded
- [ ] Marketing claims are flagged and not directly used as CER conclusions
- [ ] Evaluation route is selected and justified
- [ ] PICO/endpoints serve each claim
- [ ] Every benchmark has rationality, source studies, directness, confidence
- [ ] Evidence is appraised for quality, comparability, directness
- [ ] Gaps are dispositioned (no_gap / PMCF / labeling / risk_control / claim_narrowing / cannot_support)
- [ ] BR / GSPR / RMF / IFU alignment is verified
- [ ] Writer release conditions are all met (G46 PASS)
