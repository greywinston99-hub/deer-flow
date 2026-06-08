# BIGDP2026.6V_2 — A1 Asset Verification Report

**Date:** 2026-06-08 | **Source:** `/WorkBuddy/.../BIGDP2026_6V2/assets/`

---

## Tier 1: Structural Verification — PASS

| Check | Result |
|:---|:---:|
| CSVs machine-readable (pandas) | 17/17 ✅ |
| Required columns present | ✅ |
| Dataset role present | ✅ |
| Writer access control present | ✅ |
| 南驰/iTClamp excluded from calibration/holdout | ✅ (only in exclusion file) |
| No duplicate PMID/endpoint/claim | ✅ |

## Tier 2: Content Verification — PASS

| Check | Result |
|:---|:---:|
| TO_BE_EXTRACTED placeholders | 0 ✅ |
| Source/file/PMID columns present | 16/17 ✅ |
| Content rows total | 726 |

## DC Coverage

| DC | Covered | Quota | Status |
|:---|:---:|:---:|:---:|
| DC-1 | 6 | 5 | ✅ |
| DC-2 | 2 | 5 | ❌ |
| DC-3 | 6 | 5 | ✅ |
| DC-4 | 10 | 5 | ✅ |
| DC-5 | 4 | 5 | ❌ |
| DC-6 | 8 | 6 | ✅ |
| DC-7 | 11 | 4 | ✅ |
| DC-8 | 7 | 5 | ✅ |
| DC-9 | 42 | 5 | ✅ |
| DC-10 | 3 | 4 | ❌ |
| DC-11 | 25 | 4 | ✅ |

8/11 pass. DC-2/5/10 near-miss (1-3 short each).

## Dataset Distribution

| Role | Count |
|:---|:---:|
| Calibration | 9 |
| Stress | 4 |
| Holdout | 4 |
| Special Evidence | 1 |

## Updated Score: 75/100 (was 69)
