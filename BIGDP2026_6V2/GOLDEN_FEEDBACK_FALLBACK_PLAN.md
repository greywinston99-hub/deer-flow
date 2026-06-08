# BIGDP2026.6V_2 — Golden Feedback Fallback Plan

**Status:** ACTIVE | **Date:** 2026-06-08

---

## Current Status

CAND-001 / Golden Feedback Pack: **NOT_FOUND at source verification level.**

Folder structure suggests iTClamp / 南驰 / hemostasis feedback exists but source artifacts not yet verified.

## If Found (Path A)

- Use as GOLDEN path for DC-1 through DC-11 calibration
- Create path-reference manifests only
- Lock feedback boundary per LOCKED_FEEDBACK_USE_POLICY

## If Not Found (Path B)

- Select best available calibration project (CAND-003 or higher from inventory)
- Use injected defects matching DC-1 through DC-11
- Mark Golden Feedback unavailable
- Apply all relevant score caps across affected areas
- Produce Owner request for exact Golden source

## Owner Questions (if Golden missing)

1. Confirm whether `iTClamp` / `南驰` project has explicit engineer feedback document
2. Confirm whether PMID 31539432 / 32209132 are from the feedback project
3. Confirm whether a "Golden Feedback Pack" exists as a formal document or is implicit in engineer review notes
4. If no formal Golden exists, authorize best available calibration project as primary validation source

## Score Impact

Golden missing → multi-area cap across:
- DC-1 (retrieval recall) → max 5/10
- DC-3 (screening labels) → max 5/8
- DC-4 (PMID verification) → max 6/12
- DC-6 (endpoint labels) → max 6/10
- DC-7 (comparator ranges) → max 5/8
- DC-9 (SOTA accounting) → max 5/8
- DC-10 (denominator labels) → max 5/10
- Real project validation → max 1/4
