# CER Authoring Calibration Decision Log

## 2026-05-09 — Phase 0.2 Locked Delta Analyzer

Decision: implement a standalone locked Delta Analyzer infrastructure patch.

Rationale:

- Project 1 Pilot had HC2/HC6 locked-folder access leakage.
- The run is useful as a diagnostic but cannot count as Calibration Project 1.
- The fix must not modify SOTA, Evidence Appraisal, Writer, Benefit-Risk,
  PMCF, Alignment, or Gate core logic.

Decision details:

- Mark previous Project 1 Pilot as
  `PROJECT_01_PILOT_INVALID_DUE_TO_LOCKED_ACCESS_LEAKAGE`.
- Add `scripts/calibration_delta_analyzer.py`.
- Allow locked folder access only through that analyzer after baseline freeze.
- Require `LOCKED_ACCESS_LOG.csv` and `NEEDS_HUMAN_CLASSIFICATION.csv`.
- Require baseline version bump before rerunning Project 1.
- Do not run Project 1 as part of this patch.

Expected conclusion if tests pass:

`PHASE0_2_ACCEPTED_FOR_PROJECT1_RERUN`
