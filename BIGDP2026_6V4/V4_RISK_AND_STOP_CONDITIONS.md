# V4 — Risk Register and Stop Conditions

---

## Risk Register

| ID | Risk | Impact | Mitigation |
|:---|:---|:--:|:---|
| R1 | WET determination over-inclusive (too many devices classified as WET) | HIGH — CER may claim insufficient evidence as sufficient | Conservative WET 6-condition check; borderline → not WET |
| R2 | Legacy = sufficient assumption | HIGH — legacy devices without PMS data | Explicit PMS data requirement for legacy route |
| R3 | PMCF used to rescue unsupported core claim | HIGH — NB rejection | Hard rule: PMCF insufficient for unsupported core claim |
| R4 | Equivalence without data access | HIGH — NB rejection | Hard rule: data access required for equivalence |
| R5 | Literature role misclassification (direct vs indirect) | MEDIUM — weak evidence used as strong | Per-article role rationale required |
| R6 | Strategy route gold labels unavailable | MEDIUM — route accuracy unverified | Heuristic rules from regulatory text; mark HEURISTIC_ONLY |
| R7 | NB explainability packet too generic | LOW — may not satisfy NB | Template from CEAR + real NB feedback |

---

## Stop Conditions

### Regulatory Principle Violations

Stop if the system produces any of these — they are hard failures:

- [ ] WET route accepted without ALL 6 conditions explicitly checked → **STOP**
- [ ] Legacy route accepted without PMS data review → **STOP**
- [ ] PMCF recommended for unsupported core claim → **STOP**
- [ ] Equivalence claimed without data access evidence → **STOP**
- [ ] Innovation route producing positive conclusion without CI plan → **STOP**
- [ ] Writer conclusion exceeds evidence strategy limit → **STOP**

### Asset / Knowledge Gaps

- [ ] MDR Annex XIV not available for rule extraction → mark Batch I HEURISTIC_ONLY
- [ ] Strategy route gold labels not available → mark all routes HEURISTIC_ONLY
- [ ] Literature role gold labels not available → mark Batch J HEURISTIC_ONLY
- [ ] No project available for dry-run → Batch L SYNTHETIC_ONLY

### Implementation Risks

- [ ] Baseline test regression → fix before continuing
- [ ] Code change >300 lines in single file → split
- [ ] Core graph routing change needed → architecture fit check
- [ ] V2/V3 capability conflict → isolate or feature-flag

### Repair Loop Budget

- Max 3 repair loops per batch
- Stop at 2 consecutive without new evidence
- Any batch with failing tests → cannot PASS
