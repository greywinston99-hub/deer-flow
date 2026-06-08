# BIGDP2026.6V_2 — Writer QA Architecture Decision

**Status:** EFFECTIVE | **Date:** 2026-06-08

---

## Two-Layer Architecture

### Layer 1: Pre-Write Constraint (DeerFlow side)

Location: G46 → Package Export → Claude Code Preflight

- Enforce conclusion_strength ceiling per claim
- Enforce evidence ID resolution
- Enforce benchmark limitation preservation
- Block invalid packages (orphan refs, missing schema version)

**Already implemented in BIGDP2026.6.** Inherited.

### Layer 2: Post-Write Validation (Writer side)

Location: Claude Code writer skill or post-generation validator

Rules enforced:
1. No conclusion exceeds ledger conclusion_strength
2. No hidden numeric data without PMID
3. No denominator misuse in prose
4. No endpoint taxonomy contradiction
5. No SOTA accounting inconsistency
6. No missing benchmark limitation in narrative
7. No subgroup result generalized to total population
8. No device abandonment miswritten as AE

**Partially implemented.** `cer_package_validator.py` checks package-level constraints. Writer prose validation not yet automated.

### Writer Output Levels

| Level | Source | Supports |
|:---|:---|:---|
| Level 1 | Current-run Writer output | FULLY_CLOSED for DC-11 |
| Level 2 | Historical accepted CER | CLOSED_WITH_DERIVED_VALIDATION |
| Level 3 | Synthetic CER prose | CLOSED_WITH_SYNTHETIC_FIXTURE_ONLY |
