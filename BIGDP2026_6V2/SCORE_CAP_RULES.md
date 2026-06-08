# BIGDP2026.6V_2 — Score Cap Rules

**Status:** EFFECTIVE | **Date:** 2026-06-08

---

## Rule 1: Full-score requires FULLY_CLOSED

A score area can only receive full points if the corresponding defect class is classified as `FULLY_CLOSED`.

`CLOSED_WITH_DERIVED_VALIDATION` → max 80% of full score.
`CLOSED_WITH_HEURISTIC_VALIDATION` → max 60% of full score.
`CLOSED_WITH_SYNTHETIC_FIXTURE_ONLY` → max 40% of full score.
`ASSET_BLOCKED` / `ENV_BLOCKED` → max 25% of full score.
`NOT_IMPLEMENTED` → 0 points.

---

## Rule 2: Missing asset → multi-area cap

If Golden Feedback Pack is missing, ALL score areas that depend on it are capped per their individual dependency level. See `ASSET_DEPENDENCY_MATRIX.csv`.

---

## Rule 3: Path B hard cap

Path B cannot exceed the sum of all individual score caps determined by missing assets. The actual score is `min(path_B_max, sum(individual_caps))`.

Path B can never claim 100/100.

---

## Rule 4: Evidence requirement

- Full score: requires code evidence + test evidence + runtime evidence + validation evidence
- 80%: requires code evidence + test evidence + runtime evidence (no validation evidence)
- 60%: requires code evidence + test evidence (no runtime, no validation)
- 40%: requires test evidence only (synthetic fixtures)
- 25%: requires documented design + partial test coverage
- 0%: not implemented

---

## Rule 5: DOC_ONLY / NOT_RUN → 0

Any item that is documentation-only, not run, not tested, or only inspected receives 0 points for that score area regardless of other evidence.
