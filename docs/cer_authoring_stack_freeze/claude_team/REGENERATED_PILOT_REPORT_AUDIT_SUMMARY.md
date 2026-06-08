# REGENERATED PILOT REPORT AUDIT SUMMARY — Phase 2E

> Claude Code | 2026-05-15

## Current State

Three pilot CER drafts exist as contaminated outputs. All three are correctly rejected by the frozen stack (Gates 1-5). No regenerated clean pilot reports are available because Writer source regeneration requires full pipeline execution (outside implementer scope).

## Gate Results on Existing Contaminated Drafts

| Pilot | Gates Failed | QA Score | Quarantined |
|-------|-------------|----------|-------------|
| 启灏 Plasma Electrode | 1, 2, 3, 4 | 0 | YES |
| 米道斯 Cardiac Stabilizer | 1, 2, 3, 4 | 0 | YES |
| 永新 Imaging Software | 2, 3, 4 | 25 | YES |

## Contamination Types Detected

1. **Domain cross-wiring**: ureteroscope/UAS/urology terms in cardiac and orthopedic reports
2. **IFU non-consumption**: 112-202 "Not extracted from IFU" placeholders per report
3. **Evidence-conclusion mismatch**: "clinical data partially support" when all claims are INSUFFICIENT
4. **Internal language leakage**: Claude/DeerFlow/MCP/not_allowed/score:100 in CER body
5. **Template shell leakage**: "refer to IFU for details", "confirm with manufacturer" in body

## Regeneration Path

Clean pilot CERs require:
1. Writer agent running with domain-specific templates (Phase 2A)
2. IFU-grounded device descriptions (Phase 2A)
3. Frozen prompts and templates (Phase 2B/2C)
4. Same gate suite active (Phase 1 + Phase 2)

These regenerated reports would then be tested against:
- Gates 1-5 (must PASS)
- Human reviewability rubric (7 rules, must PASS)
- Full regression (298 tests, must PASS)

## Status

Regenerated reports not yet produced. Framework is frozen and ready for verification when Writer regeneration runs.
