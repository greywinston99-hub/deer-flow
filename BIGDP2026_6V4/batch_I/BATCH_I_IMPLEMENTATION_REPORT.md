# Batch I — Strategy Router + Evidence Burden | PASS | HEURISTIC_ONLY

## Implemented
- `classify_strategy_route`: 6 routes, WET 6-condition, hard overrides
- `WET_6_CONDITIONS`: device_technology, low_risk, SOTA_stable, PMS_PMCF, BR_acceptable, intended_purpose_narrow
- Hard overrides: unsupported→cannot_support, equivalence no access→blocked, WET no PMS→blocked, innovation no CI→insufficient

## Code: expert_rule_loader.py (+80 lines)
## Tests: test_v4_batches_ijkl.py (6 tests, all pass)
## Assets: PARTIAL (I1-I3 CSVs, 49 rows)
