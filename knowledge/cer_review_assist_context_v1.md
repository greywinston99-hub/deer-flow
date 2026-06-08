# CER Review Assist Context Pack V1

**Date:** 2026-04-27 | **Status:** Sandbox-Only | **Version:** 1.0

## Purpose

This context pack provides structured calibration injection for the 5 sandbox agents in the CER Review Assist Sandbox. It is **not** for production runtime use.

## Sandbox Agents and Calibration Mapping

| Agent | BD ID | Category | Calibration Types | Max Confidence | Use Mode |
|-------|-------|----------|-------------------|----------------|----------|
| canonical-recommendation-engine.sandbox | BD-0001 | Knowledge | GS + AP | HIGH | system_prompt |
| evidence-artifact-curator.sandbox | BD-0004 | Knowledge | GS + AP | HIGH | system_prompt |
| gap-analysis-specialist.sandbox | BD-0002 | Knowledge | AP + SV + BD | MEDIUM | sys+context |
| regulatory-boundary-qa.sandbox | BD-0005+10 | Review Logic | AP + RD | HIGH | sys+context |
| cer-rmf-review-logic-qa.sandbox | BD-0003 | Review Logic | SV + RP + RD | MEDIUM | system_prompt |

## Calibration Pack Source

- **Pack:** Track C V5 Calibration Pack
- **Path:** `track_c_consolidation_v5/TRACK_C_CALIBRATION_PACK_V5.json`
- **Total candidates:** 252
- **P0 quarantined:** 7 (from projects 016_baining, 017_demaidi)
- **Binding coverage:** 13 of 24 agents bound (54%)

## Severity Framework

Based on D7 Evaluation Logic + D8 Human Gate Boundary Map + V5 Empirical Data:

| Severity | D7 | D8 | Definition |
|----------|----|----|-----------|
| CRITICAL | FAIL | human-only | Blocks submission. Clinical judgment required. |
| HIGH | QUALIFIED PASS (major) | human-only (edge) / ai-assisted | May block submission or trigger deeper NB audit. |
| MEDIUM | QUALIFIED PASS | ai-assisted | Requires NB discussion but unlikely to block alone. |
| LOW | PASS | ai-auto | Documentation completeness. Deterministic check. |

## Anti-Pattern Categories (V5 Taxonomy)

1. **DOCUMENT_INTEGRITY** (8 types): empty file, copy-paste template, placeholder, version inconsistency, etc.
2. **CLINICAL_CLAIM_VALIDITY** (6 types): cross-document contradiction, IFU contraindication not in CER, statistically improbable claim, etc.
3. **EXTRACTION_QUALITY** (7 types): synthetic summary, over-generalization, source class confusion, etc.
4. **PROCESS_EXECUTION** (2 types): plan without execution, PMCF data unavailable.
5. **AGENT_BINDING_QUALITY** (4 types): incomplete binding, unverified decisions, missing gate scope, etc.

**P0-adjacent anti-patterns (CRITICAL, HOLD_FOR_HUMAN_REVIEW):**
- KA-CAL-AP-RPR-0007: cross_document_consistency_failure
- KA-CAL-AP-RPR-0015: wrong_document_referenced_in_verification_chain
- KA-CAL-AP-RPR-0016: statistically_improbable_safety_claim

## Track A References

- D1 Requirement Hierarchy: `track_a_output/D1_REQUIREMENT_HIERARCHY.md`
- D2 Knowledge Gap: `track_a_output/D2_KNOWLEDGE_GAP.md`
- D7 Evaluation Logic: `track_a_output/D7_EVALUATION_LOGIC.md`
- D8 Human Gate Boundary: `track_a_output/D8_HUMAN_GATE_BOUNDARY_MAP.md`

## Pilot Projects

| Pilot | Path | Device | Status |
|-------|------|--------|--------|
| 082 | `track_b_output/082_tianjinhengyu/` | IVUS Imaging System | Written, NB pending |
| 052 | `track_b_output/052_52.珠海健帆/` | Blood Purification Tubing | Completed* |
| 029 | `track_b_output/029_pamu/` | PADN (PAH) | Completed |

\* Manifest says ACTIVE_PRE_SUBMISSION -- discrepancy to be flagged by sandbox.

## Hard Boundaries (All Sandbox Agents)

- No NocoDB writes
- No state DB access
- No runtime modification
- No auto-approval
- No backflow execution
- No approved/active/reusable asset creation
- No P0 quarantine lift
- No production decisions

## Human Gate Policy

- **General rule:** Every finding is flagged for human review. Auto-pass is the exception.
- **Auto-pass eligible:** PASS quality + HIGH confidence + non-regulatory finding type.
- **Mandatory gate:** CRITICAL/HIGH severity, regulatory boundary violations, cross-document inconsistencies, P0-adjacent patterns, final report sign-off.
