# BIGDP2026.6 — Expert Business Logic Specification

**Date:** 2026-06-08
**Purpose:** Define the expert reasoning rules that the CER system must enforce at runtime.
**Scope:** All 7 rule categories must be implemented, tested, and verified against expert scenario fixtures.

---

## Rule Category 1: IFU is Working Input, Not Gold Standard

### Principle
The Instructions for Use (IFU) document expresses the manufacturer's intended claims. However, IFU text may contain marketing language, aspirational statements, or claims that are not fully supported by clinical evidence. The CER system must treat IFU text as **working input** — a starting point for claim extraction — not as the final CER conclusion.

### Rules

| ID | Rule | Enforcement |
|:---|:---|:---|
| IFU-01 | Raw IFU claims MAY be narrowed in scope | IFU_CLAIM_EVOLUTION_LEDGER tracks narrowing |
| IFU-02 | Raw IFU claims MAY be qualified with safety language | Evolution flag: `safety_qualifier_added` |
| IFU-03 | Raw IFU claims MAY be weakened if evidence is insufficient | Evolution flag: `claim_narrowed` |
| IFU-04 | Raw IFU claims MAY be rejected entirely | Final CER claim set to `not_supported` |
| IFU-05 | Marketing-language claims in IFU MUST NOT directly become CER conclusions | `marketing_language_detected` → `requires_human_review: true` |
| IFU-06 | Every transformation from IFU text to final CER claim MUST have a recorded reason | Each stage includes `transformation_reason` |
| IFU-07 | IFU claims that are strengthened (beyond IFU wording) MUST be flagged for human review | `claim_strengthened: true` → `requires_human_review: true` |

### Marketing Language Keywords (non-exhaustive)
`revolutionary`, `best`, `superior`, `unmatched`, `guaranteed`, `perfect`, `game-changing`, `first-ever`, `only`, `unique`, `unparalleled`, `breakthrough`, `gold standard`, `ultimate`

---

## Rule Category 2: Claim Classification

### Principle
Every claim extracted from IFU or derived from clinical evidence must be classified into exactly one regulatory claim type. The classification determines evidence requirements, gate routing, and Writer permissions.

### Classification Taxonomy

| Code | Type | Definition | Evidence Required | Example |
|:---|:---|:---|:---|:---|
| `clinical_performance` | Clinical Performance | Claim about therapeutic efficacy or clinical outcome | Direct or indirect clinical evidence (N≥30) | "Achieves hemostasis within 3 minutes" |
| `clinical_safety` | Clinical Safety | Claim about adverse event rate or safety profile | Direct clinical evidence or equivalent device data | "Device-related AE rate < 2%" |
| `usability` | Usability / Human Factors | Claim about ease of use, ergonomics, or user interface | Usability study or expert evaluation | "Ergonomic handle reduces surgeon fatigue" |
| `warning` | Warning / Precaution | Safety warning, contraindication, or precaution | RMF + GSPR analysis | "Do not use in patients with coagulopathy" |
| `non_clinical` | Non-Clinical Statement | General description, materials, or physical properties | Technical documentation | "Device is made of medical-grade titanium" |
| `unsupported` | Unsupported / Overreaching | Claim that cannot be supported by available evidence | N/A — must be downgraded or removed | "100% success rate in all patients" |

### Classification Rules

| ID | Rule |
|:---|:---|
| CLS-01 | Every claim MUST be classified into exactly one type |
| CLS-02 | `unsupported` claims MUST be downgraded before Writer release |
| CLS-03 | `clinical_performance` claims require the highest evidence burden |
| CLS-04 | `warning` claims derive from RMF, not from PubMed literature |
| CLS-05 | `usability` claims may use manufacturer data with documented limitations |
| CLS-06 | `non_clinical` claims do not require clinical evidence but must reference TD |

---

## Rule Category 3: Evidence Support Type

### Principle
Every claim must have its evidence support type explicitly identified. The system must distinguish between different evidence quality levels and must not conflate direct clinical evidence with indirect, equivalent, or manufacturer data.

### Support Type Taxonomy

| Code | Type | Definition | Weight |
|:---|:---|:---|:---:|
| `direct` | Direct Clinical Evidence | Clinical study on the subject device with relevant endpoints | 1.0 |
| `indirect` | Indirect Literature Evidence | Clinical study on a different device in the same clinical domain | 0.7 |
| `equivalent` | Equivalent Device Evidence | Clinical data from an equivalent device (MDR Annex XIV) | 0.6 |
| `manufacturer` | Manufacturer / Bench Data | Pre-clinical, bench testing, or manufacturer internal data | 0.4 |
| `PMS` | Post-Market Surveillance | Real-world evidence, registries, complaints analysis | 0.5 |
| `rmf_gspr` | RMF / GSPR Support | Risk management file or GSPR analysis (for safety claims) | 0.6 |
| `insufficient` | Insufficient Support | No adequate evidence available | 0.0 |

### Rules

| ID | Rule |
|:---|:---|
| EVS-01 | Every claim MUST have a declared `evidence_support_type` |
| EVS-02 | `direct` support requires at least one clinical study on the subject device |
| EVS-03 | `equivalent` support requires documented equivalence under MDR Annex XIV |
| EVS-04 | `manufacturer` support alone CANNOT produce `strong` conclusions for clinical claims |
| EVS-05 | `insufficient` support MUST trigger gap disposition |
| EVS-06 | Evidence support type influences conclusion strength ceiling |

---

## Rule Category 4: Conclusion Strength Logic

### Principle
The strength of a CER conclusion must be derived from the quality and quantity of underlying evidence, not from the IFU claim wording. The system must enforce evidence-based ceilings on conclusion strength.

### Strength Levels

| Level | Definition | Minimum Evidence Required |
|:---|:---|:---|
| `strong` | High-confidence conclusion supported by multiple independent studies | ≥2 direct clinical studies OR 1 direct + ≥2 indirect, all with consistent results |
| `moderate` | Reasonable confidence; some limitations | ≥1 direct study OR ≥2 indirect studies, with minor limitations |
| `limited` | Low confidence; significant evidence gaps | Only indirect/manufacturer evidence OR single study with limitations |
| `not_supported` | Cannot conclude based on available evidence | No adequate evidence OR evidence contradicts claim |
| `cannot_conclude` | Insufficient data to reach any conclusion | No evidence at all |

### Derivation Rules

| ID | Rule |
|:---|:---|
| CON-01 | Conclusion strength is derived from `evidence_support_type` + number of sources |
| CON-02 | `manufacturer`-only support CANNOT produce `strong` |
| CON-03 | `insufficient` support → `not_supported` or `cannot_conclude` |
| CON-04 | Single-study support with `direct` evidence → at most `moderate` |
| CON-05 | Contradictory evidence → `limited` or `not_supported`, never `strong` |
| CON-06 | Conclusion strength MUST be non-null for every claim in CER_REASONING_LEDGER |
| CON-07 | Writer cannot assert `strong` for claims where ledger says `limited` or below |

---

## Rule Category 5: Benchmark Derivation Logic

### Principle
A SOTA benchmark is not a naked number. Every benchmark must be traceable to its source studies, with explicit assessment of population comparability, device comparability, directness, and confidence. Fallback benchmarks must declare their limitations.

### Required Benchmark Fields

| Field | Required? | Description |
|:---|:---:|:---|
| `endpoint_name` | ✅ | Standardized endpoint name |
| `endpoint_clinical_meaning` | ✅ | Clinical interpretation |
| `source_studies` | ✅ | PMID list with author, year, design, sample_size |
| `benchmark_value_range` | ✅ | Value with CI or range, derivation method |
| `population_comparability` | ✅ | direct_match / comparable / partial_overlap / different / unknown |
| `device_comparability` | ✅ | same_device / similar_device / alternative_therapy / different |
| `directness` | ✅ | direct / indirect / fallback |
| `confidence` | ✅ | high / medium / low / insufficient |
| `acceptability_rationale` | ✅ | WHY this benchmark is acceptable (must be non-empty) |
| `alternatives_rejected_rationale` | Required for fallback | WHY alternatives were rejected |
| `limitations` | Recommended | Known limitations |

### Rules

| ID | Rule |
|:---|:---|
| BMK-01 | Every benchmark endpoint MUST have a non-empty `acceptability_rationale` |
| BMK-02 | Fallback benchmarks MUST have `alternatives_rejected_rationale` |
| BMK-03 | Benchmarks from studies with `population_comparability: different` → confidence at most `low` |
| BMK-04 | Benchmarks from `alternative_therapy` → `directness` at most `indirect` |
| BMK-05 | A benchmark without source studies → `directness: fallback`, `confidence: low` |
| BMK-06 | Benchmark value MUST include derivation method (meta-analysis, weighted average, single study, etc.) |

---

## Rule Category 6: Gap Disposition Logic

### Principle
When evidence is insufficient to fully support a claim, the system must disposition the gap. The disposition determines what action is required: PMCF study, labeling change, risk control, or claim narrowing. Unresolved gaps block Writer release.

### Disposition Types

| Disposition | Meaning | Writer Permission |
|:---|:---|:---|
| `no_gap` | Evidence fully supports the claim | Allowed |
| `PMCF` | Post-Market Clinical Follow-up required | Allowed with PMCF note |
| `labeling` | IFU/labeling update required | Allowed with labeling note |
| `risk_control` | Risk control measure required | Allowed with risk control documentation |
| `claim_narrowing` | Claim scope must be narrowed | Writer must narrow claim |
| `cannot_support` | Claim cannot be supported | BLOCKED — claim must be removed or downgraded |

### Rules

| ID | Rule |
|:---|:---|
| GAP-01 | `insufficient` evidence MUST trigger a gap disposition |
| GAP-02 | `cannot_support` disposition → Writer BLOCKED for that claim |
| GAP-03 | `PMCF` disposition → Writer must include PMCF recommendation in CER |
| GAP-04 | Gap disposition MUST have a rationale (why this disposition was chosen) |
| GAP-05 | Claims with `cannot_support` disposition → conclusion_strength MUST be `not_supported` |

---

## Rule Category 7: Writer Release Logic

### Principle
The Writer (Claude Code `cer-authoring-section-writer`) must not write from raw IFU text or raw evidence. The Writer can only write from gate-passed expert reasoning ledgers and a validated `CER_INPUT_PACKAGE`. If evidence does not support the claim strength, writing must be blocked or downgraded.

### Writer Permissions

| Condition | Writer Permission |
|:---|:---|
| All claims have `conclusion_strength` in {strong, moderate, limited} | ALLOWED |
| Any claim has `conclusion_strength: not_supported` | BLOCKED for that claim |
| Any claim has `gap_disposition: cannot_support` | BLOCKED for that claim |
| `CER_REASONING_LEDGER` missing or empty | BLOCKED entirely |
| `IFU_CLAIM_EVOLUTION_LEDGER` missing or empty | ALLOWED_WITH_WARNING |
| `BENCHMARK_DERIVATION_TRACE` missing or empty | ALLOWED_WITH_WARNING |
| G46 status is not PASS | BLOCKED entirely |
| `cer_input_package_exported` is not true | BLOCKED entirely |
| Any `evidence_id` in a claim is not resolvable | BLOCKED for that claim |

### Rules

| ID | Rule |
|:---|:---|
| WRT-01 | Writer MUST validate `CER_INPUT_PACKAGE` before writing any section |
| WRT-02 | Writer MUST refuse to write if G46 is not PASS |
| WRT-03 | Writer MUST use `CER_REASONING_LEDGER.conclusion_strength` as ceiling |
| WRT-04 | Writer MUST NOT write `strong` conclusions for claims with `limited` ledger strength |
| WRT-05 | Writer MUST include PMCF recommendations for claims with `PMCF` gap disposition |
| WRT-06 | Writer MUST include labeling notes for claims with `labeling` gap disposition |
| WRT-07 | Writer MUST flag `cannot_support` claims as unsupported in CER text |
| WRT-08 | Writer MUST use `IFU_CLAIM_EVOLUTION_LEDGER` to prevent marketing language in CER |

---

## Cross-Cutting Rules

| ID | Rule |
|:---|:---|
| CC-01 | Every numerical claim in CER must be traceable to a PMID via evidence_registry |
| CC-02 | Every expert decision must have a recorded reason |
| CC-03 | No ledger artifact may be generated but not consumed by a downstream gate or export |
| CC-04 | All 7 rule categories must have passing semantic tests |
| CC-05 | All 8 expert scenario fixtures must produce expected results |

---

## Rule Category Summary

| # | Category | Rules | Semantic Tests |
|:---|:---|:---:|:---:|
| 1 | IFU as Working Input | IFU-01 ~ IFU-07 | `test_ifu_claim_semantic_evolution.py` |
| 2 | Claim Classification | CLS-01 ~ CLS-06 | `test_claim_conclusion_strength.py` |
| 3 | Evidence Support Type | EVS-01 ~ EVS-06 | `test_claim_conclusion_strength.py` |
| 4 | Conclusion Strength | CON-01 ~ CON-07 | `test_claim_conclusion_strength.py` |
| 5 | Benchmark Derivation | BMK-01 ~ BMK-06 | `test_benchmark_derivation_semantics.py` |
| 6 | Gap Disposition | GAP-01 ~ GAP-05 | `test_gap_disposition_logic.py` |
| 7 | Writer Release | WRT-01 ~ WRT-08 | `test_writer_release_semantics.py` |
