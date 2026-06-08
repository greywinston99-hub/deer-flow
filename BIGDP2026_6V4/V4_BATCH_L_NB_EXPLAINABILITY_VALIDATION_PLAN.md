# V4 — Batch L: NB Explainability + Validation

**Target:** P0-5 (NB Explainability Packet) + Real Project Validation
**Dependencies:** All previous Batches (I+J+K)

---

## 1. Design

### 1.1 NB Explainability Packet

**Artifact:** `NB_EXPLAINABILITY_PACKET.json`

For each key regulatory decision, provide traceable rationale:

| Decision | Packet Section | Content |
|:---|:---|:---|
| Strategy route selection | `strategy_rationale` | Why this route, factors considered, alternatives rejected |
| Evidence sufficiency | `evidence_sufficiency_rationale` | Burden calculation, available evidence, gap analysis |
| Literature role assignment | `literature_role_rationale` | Per-article role justification, eligibility |
| Equivalence acceptance/rejection | `equivalence_rationale` | 3-dim results, data access, impact analysis |
| WET/legacy justification | `wet_legacy_rationale` | Conditions check, PMS data, SOTA stability |
| PMCF recommendation | `pmcf_rationale` | Why PMCF is/is not acceptable, gap closure plan |
| BR/GSPR conclusion | `br_gspr_rationale` | Benefit evidence, risk mitigation, residual uncertainty |
| Writer constraints | `writer_constraint_rationale` | Why conclusion strength is limited, forbidden language |

### 1.2 Per-Decision Traceability

Each decision must be traceable to:
- Regulatory reference (MDR Article, MDCG section)
- Evidence source (PMID, clinical data point, PMS record)
- System logic (which gate/validator/engine produced this decision)

### 1.3 Integration

- NB_EXPLAINABILITY_PACKET.json generated at CER_INPUT_PACKAGE export time
- Included in writer package for Claude Code Writer reference
- Writer may cite packet sections in CER rationale text

## 2. Validation

### 2.1 Real Project Dry-Run

Select 2–3 projects from Patch A Tier 2 assets representing different strategy routes:
- 1 WET/legacy candidate (if available)
- 1 equivalence or own-data candidate
- 1 literature-primary or innovation candidate

For each project:
1. Run strategy router (Batch I) → confirm route
2. Run literature intelligence (Batch J) → confirm article roles
3. Run CER blueprint (Batch K) → confirm argument structure
4. Generate NB_EXPLAINABILITY_PACKET
5. Review: can a regulatory expert understand each decision?

### 2.2 Submission Readiness Check

For each dry-run project:
- [ ] CER argument structure follows route blueprint
- [ ] Evidence meets burden level or gap is explicitly documented
- [ ] PMCF plan is appropriate for route
- [ ] Writer constraints are applied
- [ ] NB explainability packet is complete and traceable
- [ ] No unacceptable shortcut detected
- [ ] Human gates fire where expected

## 3. Tests

- [ ] NB_EXPLAINABILITY_PACKET generated for fixture project
- [ ] Each decision has regulatory reference
- [ ] Each decision has evidence source
- [ ] WET justification includes 6-condition check results
- [ ] Equivalence justification includes 3-dim comparison results
- [ ] Insufficient evidence → explains why PMCF alone insufficient
- [ ] Packet validates against JSON schema

## 4. Acceptance

**Batch L PASS:** NB_EXPLAINABILITY_PACKET generated for ≥2 projects. Each decision traceable. Dry-run validation passes for available projects. Submission readiness check complete.
