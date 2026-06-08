# IFU CONSUMPTION TEST REPORT (Gate 2)

## Test Coverage

| Test | Description | Expected | Result |
|------|-------------|----------|--------|
| test_ifu_exists_placeholder | IFU exists + "Not extracted from IFU" | HARD FAIL | PASS |
| test_no_ifu_placeholder_allowed | No IFU + placeholder | PASS | PASS |
| test_no_placeholders_clean | Clean body, no placeholders | PASS | PASS |

## Real Report Results

- PILOT_01 (Plasma Electrode): HARD FAIL — 202 IFU placeholders with IFU sources available
- PILOT_02 (Cardiac Stabilizer): HARD FAIL — 112 IFU placeholders with IFU sources available
- PILOT_03 (Imaging Software): HARD FAIL — 112 IFU placeholders with IFU sources available

**Verdict**: Gate 2 correctly detects IFU placeholder text when IFU source data is available. The Writer's failure to consume IFU facts is correctly flagged.
