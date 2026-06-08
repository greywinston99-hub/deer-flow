# AGENT TEAM SPEC V1.0 — CER Authoring

> Claude Code | 2026-05-15 | Phase 2D | Target contract

## Architecture

7 physical agents + deterministic pipelines = CER authoring stack.

## Per-Agent Contracts

### cer-authoring-lead-agent
- **Forbidden**: Writing CER prose, replacing deterministic gates, informal routing
- **Must**: Use SharedAuthoringState, route by target stage and evidence gap
- **Failure**: Returns structured REWORK_REQUIRED with rework_targets

### authoring-cer-writer-agent
- **Forbidden**: Cross-domain template text, internal language in body, favourable conclusion for INSUFFICIENT claims, ignoring claim_support_matrix, writing audit artifact into CER body
- **Must**: Consume only gate-passed evidence, follow domain-specific template, use IFU-grounded device descriptions, obey writer_conclusion_constraints
- **Failure**: Writer output rejected by Gates 1-5 → quarantined

### authoring-evidence-agent
- **Forbidden**: Inventing clinical evidence, linking evidence to wrong-domain claims
- **Must**: Record missing evidence as evidence gap, trace every conclusion to evidence_id
- **Failure**: Returns BLOCKED when evidence insufficient

### authoring-methodology-sota-agent
- **Forbidden**: Writing SOTA for wrong clinical domain, fabricating benchmarks
- **Must**: Link SOTA benchmarks to PICO items, follow LSP methodology
- **Failure**: Returns REWORK_REQUIRED with domain mismatch flag

### authoring-intake-profile-claim-agent
- **Forbidden**: Overriding deterministic device_identity_lock
- **Must**: Extract claims from IFU text, derive PICO from clinical uncertainty
- **Failure**: Returns BLOCKED when IFU source insufficient

### authoring-risk-equivalence-gspr-agent
- **Forbidden**: Claiming equivalence without technical/biological/clinical comparison
- **Must**: Map every risk to GSPR, document equivalence decision basis
- **Failure**: Returns REWORK_REQUIRED for insufficient equivalence evidence

### authoring-qa-review-agent
- **Forbidden**: Rewriting CER content, giving false PASS on contaminated reports
- **Must**: Review all 8 dimensions (methodology, evidence integrity, SOTA benchmark, equivalence, vigilance, risk/GSPR, human-template style, NB precheck)
- **Failure**: Returns REWORK_REQUIRED with per-dimension findings

## Dependency Graph

```
Intake → SOTA → Evidence → Risk/GSPR → Writer → QA → Lead (gate closure)
```

## State Protocol

All agents communicate through SharedAuthoringState (immutable append-only state). No agent-to-agent direct messaging.
