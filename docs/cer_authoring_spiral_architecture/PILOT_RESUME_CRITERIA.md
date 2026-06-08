# PILOT RESUME CRITERIA

> CCD 签发 | 2026-05-11 | Phase 0 Architecture Freeze

## Pilot Resume Gate

All pilot projects remain suspended until the following conditions are ALL met:

| # | Criterion | Verification |
|---|---|---|
| 1 | Spiral architecture implemented per SPIRAL_ARCHITECTURE_SPEC | Code audit |
| 2 | Hard gate routing implemented per HARD_GATE_ROUTING_SPEC | Code audit |
| 3 | Evidence acquisition loop functional per EVIDENCE_ACQUISITION_LOOP_SPEC | Runtime proof |
| 4 | Pre-writer readiness gate blocks Writer when conditions not met | Negative test |
| 5 | Controlled compromise outputs structured insufficiency, not CER draft | Negative test |
| 6 | Writer only invoked when pre_writer_readiness = PASS | Runtime proof |
| 7 | Evidence spiral lineage traceable (round-by-round) | Artifact check |
| 8 | 20-40 is final inclusion, not retrieval cap (5-pool model) | Runtime proof |
| 9 | PILOT-01 spiral rerun: evidence insufficiency triggers re-search, not silent Writer | Runtime proof |
| 10 | PILOT-01 spiral rerun: domain mismatch blocked, no cardiac EP for orthopedic RF | Runtime proof |
| 11 | CAL-001/002/003 regression: gate status no degradation | Regression test |
| 12 | HOLD-001/002 regression: 80-level maintained under spiral architecture | Regression test |

## Pilot NOT Resumed Until

- All 12 criteria confirmed by CCD
- Owner explicitly authorizes pilot restart
- Baseline version bumped to reflect spiral architecture

---

*CCD 签发：2026-05-11*
