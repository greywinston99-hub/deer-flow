# CER Authoring Failure Taxonomy

Schema version: `cer-authoring-phase0-contract-v1`

Purpose: make calibration deltas actionable by assigning every finding to a workflow root-cause category rather than generic "AI wrote poorly" language.

| Category | Meaning | Default handling |
|---|---|---|
| `source` | Wrong, missing, or contaminated source; IFU/domain identity not locked. | Source-role fix or full rerun. |
| `claim` | IFU/intended-purpose/clinical-benefit claims missing, overbroad, or unsupported. | Claim registry correction before writer. |
| `sota` | SOTA endpoint/benchmark/pathway/acceptance criterion missing or unused. | Repair SOTA benchmark artifacts before evidence conclusion. |
| `evidence` | Evidence harvesting, citation verification, full-text extraction, or endpoint extraction insufficient. | Repair evidence registry and endpoint extraction. |
| `appraisal` | Evidence level, applicability, contribution, or pivotal/supportive weight wrong. | Repair appraisal before conclusion strength. |
| `pmcf` | PMCF used as evidence-gap dumping ground or lacks boundary/timetable. | Repair gap/PMCF decision log and benefit-risk conditions. |
| `alignment` | CER conflicts with RMF/IFU/PMCF/CEP/SSCP or lacks closure. | Repair alignment matrix or human hold. |
| `writer` | CER paragraph wording unsupported, too strong, template-like, or untraceable. | Repair section trace and writer output. |
| `gate` | Gate detects issue but lacks upstream route/recheck discipline. | Repair gate-to-upstream map. |
| `lineage` | Baseline/repair/final/calibration artifacts mixed or unversioned. | Repair baseline freeze/final manifest. |
| `leakage` | Human CER/NB comments leak into writer. | Stop calibration and repair data partitioning. |

The runtime copy is exported as `failure_taxonomy_cer_authoring.xlsx`.

