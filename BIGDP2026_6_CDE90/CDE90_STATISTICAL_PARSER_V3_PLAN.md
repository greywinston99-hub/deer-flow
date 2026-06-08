# CDE90 — Batch O: Statistical Fact Parser V3

**Target:** Expand parsing from common formats to full CER/SOTA clinical statistics
**Principle:** incomplete facts must not enter benchmark or strong claims

---

## 1. Statistical Types — Full Coverage

| Type | Example | Priority |
|:---|:---|:--:|
| proportion | 87.5% (70/80) | P0 (已有) |
| mean ± SD | 45.2 ± 12.3 mmHg | P0 (已有) |
| median / IQR | 3.2 (2.1–5.8) | P0 |
| HR | HR 0.72 (95% CI 0.58–0.89) | P0 |
| RR | RR 1.45 (95% CI 1.12–1.88) | P0 |
| OR | OR 2.31 (95% CI 1.45–3.67) | P0 |
| CI | 95% CI 76.1%–85.6% | P0 (已有) |
| p-value | p=0.032 | P0 |
| Kaplan-Meier / survival | 12-month survival 85.3% (95% CI 80.1–89.4) | P1 |
| event-free survival | EFS at 2 years 72.4% | P1 |
| time-to-event | median TTE 14.5 months | P1 |
| incidence density | 3.2 events per 100 patient-years | P1 |
| rate per patient-year | 0.45 per patient-year | P1 |
| range / min-max | range 12–78 | P1 |
| mean change from baseline | −8.5 ± 4.2 | P1 |
| between-group difference | difference 12.3% (95% CI 5.1–19.5) | P1 |
| non-inferiority margin | within pre-specified margin of 10% | P2 |
| AE count / rate | 23 device-related AEs in 18 patients | P0 |
| AE severity | Grade 3 AE: 5 events (2.3%) | P1 |
| procedure-related AE | 12 procedure-related AEs | P1 |

## 2. Incomplete Fact Mechanism

If parser cannot determine denominator / endpoint / population / source anchor:

```
fact_status = incomplete
data_use_allowed = background_only
NOT allowed for: benchmark, strong claim, BR conclusion
human_gate_required = true
```

## 3. Integration

- Populates clinical_fact_registry_v3 (fact_type, value, CI, p_value, statistical_measure fields)
- Backward compatible: existing parsers produce v3-format facts
- Incomplete fact flags surface in G46 data-traceability condition

## 4. Acceptance

- [ ] ≥15 statistical types parseable from fixtures
- [ ] ≥10 CI/range/statistical facts from test fixtures
- [ ] ≥5 KM/survival/time-to-event facts
- [ ] ≥5 AE severity facts
- [ ] Incomplete facts correctly flagged (data_use_allowed=background_only)
- [ ] No incomplete fact passes benchmark eligibility
