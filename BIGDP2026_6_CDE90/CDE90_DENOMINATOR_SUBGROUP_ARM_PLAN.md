# CDE90 — Batch P: Denominator / Subgroup / Arm Resolver

**Target:** Resolve clinical data's most common errors — denominator, subgroup, study arm, and analysis set conflation

---

## 1. Components

### denominator_context_resolver
For each fact:
- Identify what the denominator represents (total enrolled / safety set / evaluable / arm-specific / subgroup)
- Compare against study reported N
- Flag mismatch

### subgroup_generalization_guard
- Subgroup result cannot support whole-population claim unless explicitly justified
- Subgroup claims must carry subgroup label throughout (Writer constraint)

### analysis_population_validator
Distinguish:
- total enrolled N
- safety analysis set
- performance analysis set
- evaluable population
- ITT vs PP

### arm_consistency_checker
- treatment arm
- control arm
- comparator arm
- Per-arm facts must be arm-labeled

### percentage_recalculation_validator
- Recalculate percentage from numerator/denominator when both present
- Flag calculation errors

## 2. Denominator Types

| Type | Example | Context |
|:---|:---|:---|
| total_enrolled_N | N=216 | study-wide |
| safety_analysis_set | N=210 | all treated |
| evaluable_population | N=198 | completed follow-up |
| subgroup_n | n=80 | CMF subgroup |
| treatment_arm_N | N=108 | treatment only |
| control_arm_N | N=108 | control only |
| event_denominator | per 100 patient-years | incidence |
| per_patient | per patient | individual |
| per_procedure | per procedure | procedural |
| per_device | per device | device-level |

## 3. Hard Rules

- Subgroup result written as whole-population → FAIL
- Per-procedure written as per-patient → FAIL
- Safety denominator mixed with performance denominator → FAIL
- Missing denominator + benchmark/strong claim → FAIL
- Percentage not recalculable from given numerator/denominator → FLAG
- McKee-style mismatch (N=216 vs n=80, 70/80) → FAIL

## 4. Acceptance

- [ ] All 10 denominator types distinguishable
- [ ] Subgroup generalization → blocked unless explicit justification
- [ ] Per-procedure vs per-patient correctly detected
- [ ] McKee-style mismatch detected (N=216 / CMF n=80 / 70/80)
- [ ] Percentage recalculation catches errors
- [ ] Missing denominator + benchmark → FAIL
