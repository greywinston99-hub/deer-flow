# V3 Architecture Fit Check

**Date:** 2026-06-08

## Decisions

| U | Approach | Reuse | New | Conflicts? |
|:---|:---|:---|:---|:---|
| U1 | Extend `_node_extract_clinical_facts` with E0 fields + stat parsers | graph.py node | HR/RR/OR/CI parsers in expert_rule_loader | None |
| U2 | Add `_validate_semantic_claim_support` to gates.py, wire into G43 | gates.py G43 | semantic validator function | None — extends G43 |
| U3 | Add `_validate_equivalence_route` to gates.py, consume EQV rules | gates.py + Rulebook | equivalence gate function | None |
| U4 | Create `config/cer/endpoint_domain_templates.yaml` + loader function | config + expert_rule_loader | 5 domain templates | None |
| U5 | Add `_validate_br_gspr_crosswalk` to gates.py | gates.py | crosswalk validator | None — extends G44/G45 path |
| U6 | Add 9 post-write detectors to `cer_package_validator.py` | package_validator.py | detector functions | None |

## V2 Conflict Check

All 6 extensions are additive. No existing gate bypassed. No graph routing changed. All backward compatible.
