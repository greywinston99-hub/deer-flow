# QUANTITATIVE NORMALIZATION SPEC

> CCD 签发 | 2026-05-12 | V3-Core

## Problem

Extracted values use different units, formats, and statistical expressions. "92.3%" vs "0.923" vs "92.3 per 100". Need normalization for cross-study comparison.

## Normalization Rules

| Raw | Normalized |
|---|---|
| Percentage: "92.3%", "0.923" | value: 92.3, unit: %, normalized: 0.923 | Decimal→percentage requires source context (e.g., "rate" or "proportion") or expected_endpoint_unit. Do not auto-convert bare decimals without context. |
| Rate: "3.2 per 100 patient-years" | value: 3.2, unit: per_100_py |
| Mean ± SD: "45.2 ± 12.1 mmHg" | value: 45.2, sd: 12.1, unit: mmHg |
| Median (IQR): "12 (8-18) months" | median: 12, iqr_low: 8, iqr_high: 18, unit: months |
| OR/HR/RR: "OR 2.1 (95% CI 1.3-3.4)" | value: 2.1, ci_low: 1.3, ci_high: 3.4, type: OR |
| Count: "n=156" | n: 156 |

## Validators

| Check | Fail If |
|---|---|
| numeric_sanity | Value outside clinically plausible range for endpoint |
| unit_consistency | Unit doesn't match endpoint expected unit |
| denominator_check | n/N mismatch (e.g., % calculated from wrong base) |
| CI_cross_check | CI bounds don't contain point estimate |

## Normalization Status

- `raw`: extracted, not normalized
- `normalized`: successfully normalized
- `normalization_failed`: requires human review
- `normalized_human_verified`: human confirmed

---

*CCD 签发：2026-05-12*
