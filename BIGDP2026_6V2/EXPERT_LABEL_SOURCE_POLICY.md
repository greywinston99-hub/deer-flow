# BIGDP2026.6V_2 — Expert Label Source Policy

**Status:** EFFECTIVE | **Date:** 2026-06-08

## Closure Levels

| Level | Definition | Max Score |
|:---|:---|:---:|
| FULLY_CLOSED | Explicit Domain Expert label OR direct Engineer feedback correction with source evidence | 100% |
| CLOSED_WITH_DERIVED_VALIDATION | NB feedback + accepted revision OR final accepted CER reverse-derived label | 80% |
| CLOSED_WITH_HEURISTIC_VALIDATION | Generalized rule without expert label | 60% |
| CLOSED_WITH_SYNTHETIC_FIXTURE_ONLY | Synthetic fixture only | 40% |
| ASSET_BLOCKED | Required label/source missing | 25% |
| DOMAIN_DECISION_BLOCKED | Requires human expert decision | 0% |

## Source Hierarchy

1. Domain Expert supplied (highest)
2. Engineer feedback explicit correction
3. NB feedback + accepted revision
4. Final accepted CER reverse-derived label
5. Heuristic-only rule (lowest)
6. Synthetic fixture only (lowest)

## Derived Validation Requirements

CLOSED_WITH_DERIVED_VALIDATION requires:
- Source path documented
- Before/after or accepted rationale available
- No conflicting evidence
- Validation repeated on ≥1 non-training artifact
