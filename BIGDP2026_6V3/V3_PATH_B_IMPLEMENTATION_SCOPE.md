# V3 Path B Implementation Scope

**Date:** 2026-06-08 | **Path:** B | **Target:** V3_ABSORBED_WITH_ASSET_LIMITATIONS

---

## What CAN Be Implemented Now

| U | Capability | Can Implement | Closure Level |
|:---|:---|:---|:---|
| U1 | Clinical Fact V2 | Structural + E0 eligibility + stat parsers | HEURISTIC_ONLY |
| U2 | Semantic Support | Atomic claim decomposition + G43 extension | HEURISTIC_ONLY |
| U3 | Equivalence Gate | Runtime gate + EQV Rulebook consumption | DERIVED_VALIDATION |
| U4 | Domain Library | 5 domain templates + runtime loading | HEURISTIC_ONLY |
| U5 | BR/GSPR Crosswalk | Crosswalk structure + validator | DERIVED_VALIDATION |
| U6 | Writer QA | 9 detectors + Level 2/3 text testing | DERIVED_VALIDATION |

## What CANNOT Be FULLY_CLOSED (without new assets)

All 6 Us require Domain Expert labels for FULLY_CLOSED. None have gold labels currently.

## Expected Max Expert Score

~88-90/100 (engineering absorption close to 100, expert validation capped)

## Implementation Can Proceed

All structural implementation is possible with existing V2 codebase + Patch A Tier 2 assets. No new asset extraction needed.
