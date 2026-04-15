# RMF Review Input Tree Example

This example shows a P0 input bundle layout for one real project review. The
goal is not to force exact filenames, but to make document roles explicit so the
workflow can build `run_manifest`, `input_inventory`, and downstream artifacts.

```text
inputs/
└── seed_project_01_wuxi_pamu/
    ├── project_profile.yaml
    ├── RMF/
    │   ├── Risk_Management_File.pdf
    │   ├── Risk_Management_Plan.pdf
    │   ├── Risk_Acceptability_Matrix.xlsx
    │   └── Traceability_Matrix.xlsx
    ├── FMEA/
    │   ├── Design_FMEA.xlsx
    │   ├── Process_FMEA.xlsx
    │   └── Use_FMEA.xlsx
    ├── Hazard_Analysis/
    │   └── Hazard_Analysis.xlsx
    ├── IFU/
    │   └── IFU.pdf
    ├── CER/
    │   └── CER.pdf
    ├── TD/
    │   ├── Essential_Requirements_Checklist.xlsx
    │   └── Verification_Summary.pdf
    └── PMS_PMCF/
        ├── PMS_Plan.pdf
        └── PMCF_Plan.pdf
```

## Minimal P0 expectations
- `project_profile.yaml` must identify RMF as the primary review object.
- At least one RMF main file must be present.
- At least one FMEA or Hazard Analysis source must be present, and P0 strongly prefers both.
- IFU / CER / TD / PMS-PMCF are cross-validation inputs. They may be incomplete in P0, but missing files must be surfaced as artifacts.

## Recommended artifact output tree

```text
outputs/
└── rmf_review_v1_1/
    └── {run_id}/
        ├── 00_run_manifest/
        ├── 01_normalized/
        ├── 02_fmea_precheck/
        ├── 03_rmf_precheck/
        ├── 04_dimension_review/
        ├── 05_human_boundary/
        └── 06_final/
```

## Mapping tips
- If the source project uses different names, keep the original filenames and map them through `project_profile.yaml`.
- If FMEA and Hazard Analysis are combined in one workbook, still mark the source as explicit `FMEA` or `Hazard_Analysis` in the profile and preserve row-level source refs during normalization.
- Do not rely on chat-only descriptions of missing files. Missing items must be emitted into `missing_items_report.md`.
