# EVIDENCE ACQUISITION LOOP SPEC — V2 (FROZEN)

> CCD 签发 | 2026-05-11

## Pool Model

`database_hit_count` → `retrieved_record_pool`(~200-500 operational target) → `screened_candidate_pool`(~50-100) → `fulltext_assessed_pool`(~20-50) → `final_cer_included_set`(20-40)

20-40 = final inclusion target. 200-500 = operational target range, adjustable by query precision/device class/hit density.

## Spiral (max 3 rounds)

R1: domain-locked. R2: query expansion + adjacent DB + citation chasing. R3: grey lit + registries + mfr data (runtime-native where available; human supplement where not). After R3: BLOCKED.

## Sufficiency: Claim-Level

Per claim: ≥1 evidence with role∈{pivotal,supportive}, applicability∈{high,medium}, **directness∈{high,medium}**, full_text∈{available,partial}, endpoint_match=true, conclusion_strength compatible with claim_type. directness=low → lower conclusion strength only (cautious/descriptive).

## Screen Threshold

30 = default floor, not universal. G40 checks device_class_retrieval_profile.

## Spiral Lineage

spiral_round_id, rework_reason, query_delta, records_delta per round.

---

*CCD 签发：2026-05-11*
