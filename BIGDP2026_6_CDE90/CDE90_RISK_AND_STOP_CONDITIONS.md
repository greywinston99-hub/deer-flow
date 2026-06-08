# CDE90 — Risk and Stop Conditions

---

## Risk Register

| ID | Risk | Impact | Mitigation |
|:---|:---|:--:|:---|
| R1 | Table extraction hallucination (parser creates data not in table) | HIGH | Source anchor mandatory; no fact without source_table_or_figure |
| R2 | Statistical parser false positive (wrong CI/p-value extraction) | HIGH | Incomplete fact mechanism; verification_status tracking |
| R3 | Denominator confusion (analysis sets mixed) | HIGH | Hard rules for subgroup/arm/analysis_set distinction |
| R4 | Subgroup overgeneralization | HIGH | Subgroup guard + Writer constraint |
| R5 | Low-confidence fact entering benchmark or strong claim | HIGH | data_use_allowed enforcement |
| R6 | Source anchor missing | HIGH | Hard rule: no anchor → not_allowed or background_only |
| R7 | Gold set insufficient (<150 facts) | MEDIUM | Cap Stage 5 at 86 |
| R8 | Real project validation missing | MEDIUM | Cap Stage 5 at 88 |

## Stop Conditions

Stop if:

- [ ] Table extraction produces facts without source anchor → STOP, fix anchor enforcement
- [ ] Statistical parser false positive rate >20% on gold set → STOP, recalibrate
- [ ] Denominator resolver fails on McKee-style mismatch → STOP, add test case
- [ ] Low-confidence fact reaches benchmark or strong claim → STOP, fix data_use_allowed enforcement
- [ ] Baseline regression >5 tests → STOP, fix regression
- [ ] Gold set <100 facts → STOP, mark ASSET_BLOCKED

## Score Caps

| Condition | Max Stage 5 Score |
|:---|:--:|
| No table extraction | 84 |
| No denominator resolver | 85 |
| No gold set | 86 |
| No median/IQR parser | 87 |
| No KM/survival handling or candidate detection | 88 |
| No AE severity parser | 88 |
| No real project validation | 88 |
| No source anchors | 80 |
| Orphan numeric facts present | 82 |
| Figure/KM numeric extraction claimed without source verification | not allowed — KM figure detection ≠ extraction |
