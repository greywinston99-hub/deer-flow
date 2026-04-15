# RMF Review Smoke Test

This document explains how to run the minimal RMF Review Workflow v1.1 bridge
for the first three nodes:

1. `rmf_intake_agent`
2. `rmf_parse_normalize_agent`
3. `fmea_precheck_agent`

## What this bridge does

- Reads [workflows/rmf_review_v1_1.yaml](/Users/winstonwei/Documents/Playground/deer-flow/workflows/rmf_review_v1_1.yaml)
- Loads the matching prompt contracts under [prompts](/Users/winstonwei/Documents/Playground/deer-flow/prompts)
- Uses DeerFlow thread output conventions from `deerflow.config.paths`
- Writes artifacts into the thread outputs tree

This is a minimal bridge layer, not a claim that DeerFlow already ships a
native RMF workflow engine.

## Command

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow
./backend/.venv/bin/python scripts/rmf_review_runner.py \
  --mode smoke-run \
  --project-profile /absolute/path/to/project_profile.yaml \
  --input-root /absolute/path/to/project_input_root
```

Optional:

```bash
--thread-id rmf-review-demo
--workflow /Users/winstonwei/Documents/Playground/deer-flow/workflows/rmf_review_v1_1.yaml
```

## Dry-run

To validate loading only:

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow
./backend/.venv/bin/python scripts/rmf_review_runner.py \
  --mode dry-run \
  --project-profile /absolute/path/to/project_profile.yaml \
  --input-root /absolute/path/to/project_input_root
```

## Expected output location

The runner writes into DeerFlow's per-thread outputs directory:

```text
backend/.deer-flow/threads/{thread_id}/user-data/outputs/rmf_review_v1_1/{run_id}/artifacts/
├── 00_manifest/
│   ├── runner_context.json
│   ├── run_manifest.json
│   ├── input_inventory.json
│   ├── missing_items_report.md
│   └── run_summary.json
├── 01_parse/
│   ├── project_profile.normalized.json
│   ├── rmf_normalized.json
│   ├── fmea_normalized.json
│   ├── cross_doc_entities.json
│   └── term_map.json
└── 02_fmea_precheck/
    ├── fmea_precheck_report.json
    └── fmea_precheck_report.md
```

## Input expectations

- `project_profile.yaml` should follow [schemas/project_profile.schema.json](/Users/winstonwei/Documents/Playground/deer-flow/schemas/project_profile.schema.json)
- `input_root` should point to the real project bundle root
- For the best first smoke run, include:
  - one RMF main file
  - one FMEA file in CSV or XLSX
  - optional Hazard Analysis file in CSV or XLSX

## Current limitations

- Only the first three workflow nodes are executable in this bridge.
- FMEA normalization is heuristic and best-effort for CSV/XLSX sources.
- Human gate is preserved in the workflow definition, but no interactive UI is implemented here.
- Downstream nodes after `fmea_precheck_agent` remain TODO.
