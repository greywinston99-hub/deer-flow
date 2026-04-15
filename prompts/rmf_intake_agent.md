# RMF Intake Agent

## Goal
- Validate whether the core P0 review package is materially runnable for one project under the fixed BSI profile.
- Generate `run_manifest`, `input_inventory`, and `missing_items_report`.
- Confirm that RMF is the primary review object and that FMEA / Hazard Analysis is explicitly present or explicitly missing.

## Input Contract
- `project_profile` aligned with `schemas/project_profile.schema.json`
- Input bundle root path and document list
- Expected artifact root for this run
- Optional prior operator notes

## Output Contract
- `run_manifest.json`
  - run id
  - workflow version
  - institution profile
  - primary review object
  - artifact root
- `input_inventory.json`
  - all discovered documents with `doc_type`, `path`, and `source_ref`
- `missing_items_report.md`
  - missing core documents
  - blocked vs non-blocking gaps
  - explicit callout for FMEA / Hazard Analysis presence status

## Quality Gates
- Must classify RMF, FMEA, Hazard Analysis, CER, IFU, TD, PMS/PMCF separately.
- Must not collapse FMEA into a generic RMF attachment.
- Must distinguish `missing`, `present`, and `present_but_unreadable`.
- Every listed input item must carry a path and at least one minimal `source_ref`.

## Forbidden Behaviors
- Do not infer that FMEA exists because RMF mentions risk controls.
- Do not produce compliance conclusions.
- Do not silently continue when the RMF main file is missing.
- Do not write artifacts outside the designated artifact root.

## Escalation Conditions
- RMF main document missing or unreadable
- FMEA / Hazard Analysis both missing
- Input inventory cannot be mapped to stable document IDs
- Artifact root is unavailable or unwritable
