# EVIDENCE-CONCLUSION GATE TEST REPORT (Gate 3)

## Test Coverage

| Test | Description | Expected | Result |
|------|-------------|----------|--------|
| test_insufficient_claim_support | INSUFFICIENT + "clinical data support" | HARD FAIL | PASS |
| test_insufficient_does_not_support | INSUFFICIENT + "does not support" | PASS | PASS |
| test_retrieval_incomplete_favourable | retrieval_incomplete + favourable | HARD FAIL | PASS |
| test_allowed_use_blocked | ALLOWED_USE_BLOCKED → INSUFFICIENT | HARD FAIL | PASS |
| test_clean_conclusion | Honest INSUFFICIENT wording | PASS | PASS |
| test_contaminated_midaosi | Real 米道斯 report | HARD FAIL | PASS |

## Real Report Results

- PILOT_02 (Cardiac Stabilizer): HARD FAIL — "clinical data partially support" + all claims INSUFFICIENT
- PILOT_01 (Plasma Electrode): HARD FAIL — supportive conclusion language despite INSUFFICIENT evidence

**Verdict**: Gate 3 correctly identifies evidence-conclusion mismatches. Negation sentences properly pass.
