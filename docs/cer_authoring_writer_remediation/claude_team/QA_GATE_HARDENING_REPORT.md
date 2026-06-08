# QA GATE HARDENING REPORT (Gate 5)

## Test Coverage

| Test | Description | Expected | Result |
|------|-------------|----------|--------|
| test_contaminated_cardiac_qa_fail | Cardiac stabilizer → QA FAIL | FAIL | PASS |
| test_contaminated_plasma_qa_fail | Plasma electrode → QA FAIL | FAIL | PASS |
| test_internal_language_qa_fail | Internal language → QA FAIL | FAIL | PASS |
| test_evidence_mismatch_qa_fail | Evidence mismatch → QA FAIL | FAIL | PASS |
| test_clean_minimal_qa_pass | Clean report → QA PASS | PASS | PASS |
| test_no_unsupported_pass | No false PASS/100 on contaminated | Not PASS+100 | PASS |

## Real Report Results

| Report | QA Score | Status | Failing Dimensions |
|--------|----------|--------|--------------------|
| Plasma Electrode | 0 | FAIL | domain, evidence, IFU, cleanliness |
| Cardiac Stabilizer | 0 | FAIL | domain, evidence, IFU, cleanliness |
| Imaging Software | 25 | FAIL | evidence, IFU, cleanliness |

## QA Dimension Status Legend

- **PASS**: All checks passed for this dimension
- **FAIL**: Hard failure — report not acceptable
- **WARNING**: Minor issues found, report still PASSes but with caveats
- **SKIPPED**: Check could not run (missing input artifacts)

## Score System

- Base score: 100
- Per FAIL dimension: -25
- Per WARNING dimension: -10
- Minimum score: 0

**Verdict**: Gate 5 correctly replaces the old QA gate. No more false PASS/100/findings-empty on contaminated reports. The 4-dimension structure provides granular quality signals.
