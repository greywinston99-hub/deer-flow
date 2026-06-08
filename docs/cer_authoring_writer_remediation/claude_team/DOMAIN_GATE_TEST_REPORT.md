# DOMAIN GATE TEST REPORT (Gate 1)

## Test Coverage

| Test | Description | Expected | Result |
|------|-------------|----------|--------|
| test_f1_cardiac_stabilizer | 米道斯 report + ureteroscope | HARD FAIL | PASS |
| test_f2_plasma_electrode | 启灏 report + UAS | HARD FAIL | PASS |
| test_f4_exclusion_context | Forbidden term in exclusion | PASS | PASS |
| test_f5_clean_minimal | Clean cardiac stabilizer | PASS | PASS |
| test_f6_imaging_software | Software + physical terms | HARD FAIL | PASS |

## Real Report Results

- PILOT_02 (Cardiac Stabilizer): HARD FAIL — "ureteroscope" found
- PILOT_01 (Plasma Electrode): HARD FAIL — "ureteral access sheath" found

**Verdict**: Gate 1 correctly identifies domain contamination in all test cases and real contaminated reports.
