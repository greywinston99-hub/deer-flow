# Artifact Consumption Contract

Schema version: `cer-authoring-phase0-contract-v1`

Purpose: prevent "artifact theater" by requiring each important artifact to declare its producer, consumer, required status, and whether it is actually consumed by later workflow stages.

## Required Fields

| Field | Meaning |
|---|---|
| `contract_id` | Stable row ID. |
| `artifact_name` | State key, file name, or repair/final artifact path. |
| `producer` | Function, node, or layer that creates the artifact. |
| `consumer` | Function, node, gate, repair layer, or final package that uses it. |
| `required_or_optional` | `required`, `required_when_*`, `optional_repair`, or `optional_final`. |
| `consumption_status` | `state_used_and_exported`, `exported_and_read_by_supervisor`, `external_to_graph`, or `external_delivery`. |
| `calibration_use` | How the artifact supports calibration/root-cause analysis. |

The runtime copy is exported as `artifact_consumption_contract.xlsx` and included in `authoring_workbook.json`.

