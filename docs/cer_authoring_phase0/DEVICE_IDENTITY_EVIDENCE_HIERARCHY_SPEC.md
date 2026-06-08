# Device Identity Evidence Hierarchy Spec

Status: Phase 0.6 implementation spec

This spec controls how CER authoring selects the subject-device clinical domain when deterministic intake evidence and LLM/text classification evidence disagree.

## Eight-Rank Hierarchy

| Rank | Evidence source | Strength | Rule |
|---:|---|---|---|
| 1 | `locked_domain_hint` | STRONGEST | Deterministic source-role/domain lock. Cannot be overridden by LLM/text classifier output. |
| 2 | `subject_ifu_intended_purpose` | STRONG | Subject IFU intended use / intended purpose / indications. |
| 3 | `subject_ifu_filename_path` | STRONG | Subject IFU filename and folder path. |
| 4 | `structured_metadata` | MEDIUM_STRONG | Manufacturer metadata or extracted document metadata. |
| 5 | `rmf_rmr_risk_context` | MEDIUM | RMF/RMR clinical risk context. |
| 6 | `gspr_context` | MEDIUM_WEAK | GSPR context. May contain incidental terms and cannot override stronger identity evidence. |
| 7 | `project_path_target_keywords` | WEAK | Project path and user target keywords. |
| 8 | `llm_or_text_classifier` | WEAKEST | LLM/text classifier output. Can fill gaps but cannot override stronger evidence. |

## Arbitration Rule

The selected domain is the first specific domain observed in the hierarchy. If a lower-ranked evidence source observes a different specific domain, the row is marked `DEVICE_IDENTITY_CONFLICT`. The selected domain is not silently replaced.

The workflow must preserve the conflict in `device_identity_arbitration_table` and in the device identity lock. This makes incidental wording, such as a GSPR checklist containing "diagnostic" terms, auditable without letting it override a locked cardiovascular RF ablation catheter domain.

## Required Regression Outcomes

| Calibration case | Expected selected domain |
|---|---|
| CAL-001 | `cardiovascular_rf_ablation_catheter` |
| CAL-002 | `ai_diagnostic_software` |
| CAL-003 | `surgical_ligating_clip` |

