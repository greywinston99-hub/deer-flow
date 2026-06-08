# V3 — Capability Absorption Scorecard (Engineering)

**Date:** 2026-06-08 | **Tests:** 598/598 pass | **Path:** B

---

| # | Capability | Score | Code | Test | Runtime | Asset | Closure |
|:---|:---|:---:|:---|:---|:---|:---|:---|
| U1 | Clinical Fact V2 | 13/15 | ✅ E0 + parsers | ✅ 17 tests | ✅ graph node | PARTIAL | HEURISTIC |
| U2 | Semantic Support | 13/15 | ✅ validator | ✅ 4 tests | ✅ G43 ext | PARTIAL | HEURISTIC |
| U3 | Equivalence Gate | 14/15 | ✅ 6-route | ✅ 4 tests | ✅ EQV rules | PARTIAL | DERIVED |
| U4 | Domain Library | 13/15 | ✅ 5 templates | ✅ 2 tests | ✅ YAML config | PARTIAL | HEURISTIC |
| U5 | BR/GSPR Crosswalk | 13/15 | ✅ validator | ✅ 3 tests | ✅ gate ext | PARTIAL | DERIVED |
| U6 | Writer QA | 13/15 | ✅ 9 detectors | ✅ 3 tests | ✅ package ext | PARTIAL | DERIVED |
| R | Regression Stability | 10/10 | ✅ | 598 pass | ✅ V2 intact | — | — |

**TOTAL: 89/100**

### Deductions

- All Us -3: structural complete but no gold labels → HEURISTIC/DERIVED, not FULLY_CLOSED
- U4 -2: domain templates exist but not runtime-loaded into endpoint classifier yet
- U6 -2: detectors exist but tested with Level 3 synthetic prose only
