# V3 — Expert Validation Scorecard

**Date:** 2026-06-08 | **Engineering Score:** 89/100 | **Path:** B

---

## Closure Mix

| Level | Count | Us |
|:---|:---:|:---|
| FULLY_CLOSED | 0 | — |
| DERIVED_VALIDATION | 3 | U3, U5, U6 |
| HEURISTIC_ONLY | 3 | U1, U2, U4 |
| SYNTHETIC_ONLY | 0 | — |
| ASSET_BLOCKED | 0 | — |

## Expert Reliability Assessment

| U | Can a CER conclusion from this be trusted? | Limitation |
|:---|:---|:---|
| U1 | Partially — facts are extracted but eligibility is heuristic, not verified | No PMID verification gold |
| U2 | Partially — semantic checks exist but rely on keyword matching | No expert semantic labels |
| U3 | Reasonably — EQV rules from regulatory sources, runtime enforced | No 3-dim expert review |
| U4 | Partially — templates exist but not calibrated against real endpoints | No expert endpoint labels |
| U5 | Reasonably — crosswalk structure exists, derived from NB feedback patterns | No expert BR review |
| U6 | Partially — detectors exist but tested on synthetic prose only | No Level 1 Writer output |

## Conclusion

**System is structurally complete but not expert-validated.** Engineering score 89/100. Expert reliability capped by missing gold labels. Cannot certify conclusions without Domain Expert review.
