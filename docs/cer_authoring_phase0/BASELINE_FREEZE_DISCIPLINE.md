# Baseline Freeze Discipline

Schema version: `cer-authoring-phase0-contract-v1`

Phase 1 formal calibration requires a frozen `authoring_baseline_version`.

## Allowed Between Formal Calibration Projects

- Delta analysis.
- Root-cause classification.
- Schema/protocol bug fix.
- Artifact/export/readback fix.
- Data leakage fix.
- Blocker recording.

## Forbidden Between Formal Calibration Projects

- SOTA Agent logic change.
- Evidence Appraisal logic change.
- Writer Contract change.
- Benefit-Risk Rule change.
- PMCF Boundary Rule change.
- Alignment Rule change.
- Gate Logic change.

## Fatal Blocker Exception

If a fatal blocker prevents calibration:

1. Bump `authoring_baseline_version`.
2. Record blocker and repair reason.
3. Rerun affected calibration project.
4. Aggregate only same-baseline projects, or stratify by baseline version.

The runtime copy is exported as `authoring_baseline_freeze_manifest.json`.
