# BIGDP2026.6V_3 — Risk Register and Stop Conditions

---

## Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|:---|:---|:--:|:--:|:---|
| R1 | Tier 2 assets remain PARTIAL | HIGH | U1/U2/U5/U6 capped at heuristic/derived | Implement structural framework now; content calibration when assets READY |
| R2 | Expert labels (endpoint, AE, denominator) unavailable | MEDIUM | DC-6/DC-10 remain HEURISTIC_ONLY | CLAUDE.md rules as heuristic baseline; mark limitation in scorecard |
| R3 | Writer output (Level 1) unavailable for E2E | MEDIUM | U6 capped at Level 2 (historical) | Use D2/D3 historical CER texts; mark DERIVED_VALIDATION |
| R4 | Holdout validation projects insufficient | LOW | Real project score capped at 1–2/4 | Artifact-level validation as fallback |
| R5 | Code changes trigger baseline regression | LOW | Blocked until fixed | Targeted tests per batch; full regression before closeout |
| R6 | Architecture scope creep (>300 lines in core graph) | LOW | Fragment batch into smaller PRs | Architecture fit check before each batch |
| R7 | Conflict with V2 existing capabilities | LOW | Dual-path support or feature flag | Read V2 code before implementing |
| R8 | liteparse/PubMed MCP unavailable | LOW | Table/figure extraction limited | Structural extraction only; mark limitation |

---

## Stop Conditions

### Per-Batch Stop

- [ ] Any batch has 3 consecutive repair loops with no new evidence → STOP, write blocker report
- [ ] Any batch has >2 architecture rewrites → STOP, re-evaluate approach
- [ ] Baseline test regression introduced → STOP, fix regression before continuing

### Asset Stop

- [ ] Tier 2 assets not advancing from PARTIAL to READY, and batch claims FULLY_CLOSED → STOP, downgrade claim
- [ ] Required asset (e.g., B4 PMID trace for U1) completely unavailable and no heuristic alternative → STOP, mark ASSET_BLOCKED

### Scope Stop

- [ ] Code change exceeds 300 lines in a single file → STOP, split into smaller implementation
- [ ] Change touches core graph routing (graph.py node edges) → STOP, architecture fit check
- [ ] Work expands into Review v5/frontend/gateway → STOP, isolate

### Environment Stop

- [ ] pytest/venv unavailable → STOP, ENV_BLOCKED
- [ ] liteparse unavailable for U1 table extraction → STOP, mark limitation, continue without
- [ ] Full E2E dry-run blocked → STOP, use deterministic artifact-level validation

### Quality Stop

- [ ] Any DC claimed FULLY_CLOSED without corresponding test + runtime + validation evidence → STOP, downgrade
- [ ] Any checklist item marked PASS without code/test evidence → STOP, revert to NOT_CHECKED
- [ ] Score claimed above cap without documented justification → STOP

---

## Block Scenarios

### Worst Case: All 6 Upgrades Capped

If Tier 2 assets never advance beyond PARTIAL:
- U1: CLOSED_WITH_HEURISTIC_VALIDATION (regex-based extraction only)
- U2: CLOSED_WITH_DERIVED_VALIDATION (accepted CER reverse-labeling)
- U3: CLOSED_WITH_DERIVED_VALIDATION (EQV Rulebook structural checks)
- U4: CLOSED_WITH_HEURISTIC_VALIDATION (classifier + domain inference)
- U5: CLOSED_WITH_DERIVED_VALIDATION (existing ledgers crosswalk)
- U6: CLOSED_WITH_DERIVED_VALIDATION (Level 2 historical CER)
- **Max Score: ~85–87/100**

### Best Case: Partial Tier 2 → READY for U1/U2/U3

If Owner fills B4/B5/C3 TO_BE_EXTRACTED placeholders:
- U1: Up to DERIVED_VALIDATION
- U2: Up to DERIVED_VALIDATION
- U3: Up to DERIVED_VALIDATION
- U4/U5/U6: same as worst case
- **Max Score: ~88–90/100**
