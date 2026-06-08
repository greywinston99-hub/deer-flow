# Batch H — Writer Prose QA + Validation

**Status:** PASS | **Tests:** 3/3 | **Closure:** DERIVED_VALIDATION (Level 2/3 text)

## Implemented
- U6: detect_writer_issues — 9 post-write QA detectors

## Code
- `expert_rule_loader.py`: detect_writer_issues

## Tests
- `test_v3_batch_fgh.py`: 3 tests (overstatement, unsupported, clean prose)

## Validation Level
- Tested with Level 3 synthetic prose only → DERIVED_VALIDATION max
- Level 1 (current-run Writer) not available
- Level 2 (historical CER) available in assets but not yet tested
