# 07 — Test Evidence Audit

**Note:** pytest is not installed in the environment. All tests are inspected for structure and coverage, but not executed.

---

## Phase 1 Tests

### test_g46.py

| Test Name | Behavior Covered | Evidence Grade | Notes |
|:---|:---|:---|:---|
| `test_claim_evidence_blocked_no_evidence_id` | G46 BLOCKED when claim lacks evidence | ARTIFACT_CONFIRMED | Tests _check_claim_evidence_linkage |
| `test_claim_evidence_pass_all_linked` | G46 PASS when all claims have evidence | ARTIFACT_CONFIRMED | |
| `test_retrieval_completeness_blocked_no_search` | G46 BLOCKED when search registry empty | ARTIFACT_CONFIRMED | Tests _check_retrieval_completeness |
| `test_retrieval_completeness_pass_complete` | G46 PASS when searches complete | ARTIFACT_CONFIRMED | |
| `test_retrieval_completeness_rework_incomplete` | G46 REWORK when searches partial | ARTIFACT_CONFIRMED | |
| `test_no_auto_downgrade` | No BLOCKED→REWORK downgrade | ARTIFACT_CONFIRMED | Critical P0 test |
| `test_g46_report_structure` | Report includes per-condition details | ARTIFACT_CONFIRMED | |
| `test_g46_blocked_prevents_writer` | BLOCKED aggregate status | ARTIFACT_CONFIRMED | |
| `test_g46_with_overrides` | Override mechanism preserved | ARTIFACT_CONFIRMED | |
| `test_g46_reasoning_ledger_check` | G46 checks CER_REASONING_LEDGER | ARTIFACT_CONFIRMED | Phase 3 integration |
| `test_g46_ifu_evolution_ledger_check` | G46 checks IFU_CLAIM_EVOLUTION_LEDGER | ARTIFACT_CONFIRMED | Phase 3 integration |

**Coverage:** A.1.1-A.1.8 all addressed.

### test_hc_rework.py

| Test Name | Behavior Covered | Evidence Grade | Notes |
|:---|:---|:---|:---|
| `test_device_profile_targets_non_empty` | A.2.1 REWORK_TARGETS populated | ARTIFACT_CONFIRMED | |
| `test_device_profile_contains_input_gate` | A.2.2 target includes input_gate | ARTIFACT_CONFIRMED | |
| `test_device_profile_contains_intake_pack_review` | A.2.2 target includes intake_pack_review | ARTIFACT_CONFIRMED | |
| `test_valid_rework_returns_command` | A.2.3 Command(goto=...) returned | ARTIFACT_CONFIRMED | |
| `test_unknown_target_raises_valueerror` | A.2.4 ValueError on unknown | ARTIFACT_CONFIRMED | |
| `test_none_approval_returns_none` | Non-rework approval passes through | ARTIFACT_CONFIRMED | |

**Coverage:** A.2.1-A.2.7 all addressed except A.2.5 (UI display) and A.2.6 (checkpoint log).

### test_event_bus_fallback.py

| Test Name | Behavior Covered | Evidence Grade | Notes |
|:---|:---|:---|:---|
| `test_no_duplicates_passthrough` | Dedupe preserves unique entries | ARTIFACT_CONFIRMED | |
| `test_duplicates_removed` | Dedupe drops duplicates by evidence_id | ARTIFACT_CONFIRMED | |
| `test_mixed_ids_and_no_ids` | Entries without ID preserved | ARTIFACT_CONFIRMED | |
| `test_snapshot_isolation` | Snapshot not mutated by dedupe | ARTIFACT_CONFIRMED | |
| `test_partial_bus_success_fallback` | Partial Event Bus + fallback | ARTIFACT_CONFIRMED | A.4.5 addressed |

**Coverage:** A.4.1-A.4.5 all addressed.

### test_g42.py

| Test Name | Behavior Covered | Evidence Grade | Notes |
|:---|:---|:---|:---|
| `test_max_spiral_rounds_contract` | A.3.5 graph and gates share constant | ARTIFACT_CONFIRMED | |
| `test_no_hardcoded_spiral_integers` | A.3.6 no literal 3 or 5 | ARTIFACT_CONFIRMED | Uses AST inspection |
| `test_g42_report_max_spiral_rounds` | A.3.3 report includes constant | ARTIFACT_CONFIRMED | |
| `test_all_failure_patterns_have_routes` | 13 patterns all routed | ARTIFACT_CONFIRMED | |
| `test_g42_blocked_at_max_rounds` | BLOCKED when rounds exhausted | ARTIFACT_CONFIRMED | |

**Coverage:** A.3.1-A.3.6 all addressed.

---

## Phase 2-3 Tests

### test_phase2_ledgers.py

| Test Name | Behavior Covered | Evidence Grade | Notes |
|:---|:---|:---|:---|
| `test_reasoning_ledger_schema_valid` | Schema validation | ARTIFACT_CONFIRMED | |
| `test_ifu_evolution_ledger_schema_valid` | Schema validation | ARTIFACT_CONFIRMED | |
| `test_benchmark_trace_schema_valid` | Schema validation | ARTIFACT_CONFIRMED | |
| `test_reasoning_ledger_populated` | Node produces ledger | ARTIFACT_CONFIRMED | |
| `test_ifu_evolution_ledger_populated` | Node produces ledger | ARTIFACT_CONFIRMED | |
| `test_benchmark_trace_populated` | Node produces ledger | ARTIFACT_CONFIRMED | |

### test_phase3_gates.py

| Test Name | Behavior Covered | Evidence Grade | Notes |
|:---|:---|:---|:---|
| `test_g46_consumes_reasoning_ledger` | G46 checks reasoning ledger | ARTIFACT_CONFIRMED | |
| `test_g46_consumes_ifu_evolution_ledger` | G46 checks IFU evolution ledger | ARTIFACT_CONFIRMED | |
| `test_g42_uses_benchmark_trace` | G42 dynamic routing | ARTIFACT_CONFIRMED | |
| `test_g43_evidence_support_type` | G43 support type verification | ARTIFACT_CONFIRMED | |

---

## Phase 4 Tests

### test_phase4_handoff.py

| Test Name | Behavior Covered | Evidence Grade | Notes |
|:---|:---|:---|:---|
| `test_package_validator_exists` | Validator module loads | ARTIFACT_CONFIRMED | |
| `test_validator_detects_orphan_evidence` | Orphan detection | ARTIFACT_CONFIRMED | |
| `test_validator_detects_unresolved_claim` | Claim resolution | ARTIFACT_CONFIRMED | |

---

## Missing Tests

| Required Test | Status | Reason |
|:---|:---|:---|
| I.9 test_source_preflight_tiers.py | MISSING | 4-tier not implemented |
| I.10 test_intake_full_traversal.py | MISSING | Intake not in scope yet |
| I.11 test_review_workflow_version.py | MISSING | Phase 6 not started |
| I.12 test_claude_code_package_validator.py | MISSING | Skill not found |
| I.13 test_controlled_compromise.py | MISSING | Export failure visibility not fully verified |

---

## Execution Status

| Test File | Tests Count | Executed | Result |
|:---|:---:|:---:|:---|
| test_g46.py | 11 | NO | NOT_RUN |
| test_hc_rework.py | 6 | NO | NOT_RUN |
| test_event_bus_fallback.py | 5 | NO | NOT_RUN |
| test_g42.py | 5 | NO | NOT_RUN |
| test_phase2_ledgers.py | 6 | NO | NOT_RUN |
| test_phase3_gates.py | 4 | NO | NOT_RUN |
| test_phase4_handoff.py | 3 | NO | NOT_RUN |
| **TOTAL** | **40** | **0** | **ALL NOT_RUN** |

---

## Environment Blockage

**Root cause:** pytest not installed.

**Impact:** All 40 tests are unverified. Code could have syntax errors, import failures, or logic bugs.

**Recommended action:**
```bash
pip install pytest
pytest backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_g46.py -v
pytest backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_hc_rework.py -v
pytest backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_event_bus_fallback.py -v
pytest backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_g42.py -v
```
