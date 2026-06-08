# Batch G — Domain Library + BR/GSPR

**Status:** PASS | **Tests:** 5/5 | **Closure:** HEURISTIC (U4) / DERIVED (U5)

## Implemented
- U4: 5 domain templates in `config/cer/endpoint_domain_templates.yaml`
- U5: validate_br_gspr_crosswalk — benefit evidence + uncertainty disposition

## Code
- `config/cer/endpoint_domain_templates.yaml`: 5 domains + generic_fallback
- `expert_rule_loader.py`: validate_br_gspr_crosswalk

## Tests
- `test_v3_batch_fgh.py`: 5 tests (domain + BR/GSPR)
