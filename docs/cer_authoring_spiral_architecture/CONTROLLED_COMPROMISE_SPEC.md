# CONTROLLED COMPROMISE SPEC

> CCD 签发 | 2026-05-11 | Phase 0 Architecture Freeze

## Definition

`controlled_compromise` is a **terminal non-CER path**. It is entered when pre_writer_readiness_gate = BLOCKED or when the evidence spiral exhausts all rounds without reaching sufficiency.

## What Controlled Compromise IS

A structured termination of the authoring run that honestly reports what cannot be concluded.

## What Controlled Compromise IS NOT

- NOT a fallback that generates a "weaker CER"
- NOT a path that invokes Writer with reduced standards
- NOT a way to silently downgrade conclusions
- NOT a recovery path that restarts the run automatically

## Outputs

| Output | Required | Content |
|---|---|---|
| `compromise_manifest.json` | Yes | terminal_status, blocked_reason, blocked_conditions, spiral_rounds_exhausted |
| `evidence_status_report.md` | Yes | What IS known per claim, what CANNOT be concluded, evidence gaps |
| `recommendation.md` | Yes | supplement_evidence / accept_with_limitation / abandon |
| `human_decision_required.json` | Yes | List of decisions pending human review |
| `CER_draft.*` | **MUST NOT EXIST** | Writer was not invoked |
| `final_manifest.json` | **MUST NOT EXIST** | Not a completion |

## Terminal Statuses

| Status | Meaning |
|---|---|
| `EVIDENCE_INSUFFICIENT_TERMINAL` | After 3 spiral rounds, claims lack sufficient evidence |
| `DOMAIN_FATAL` | Device fundamentally misclassified, cannot recover within graph |
| `REASONING_CHAIN_INCOMPLETE` | One or more reasoning chain gates BLOCKED |
| `HUMAN_DECISION_REQUIRED` | Requires external input before any restart |

## Restart Rules

Controlled compromise does NOT auto-restart. Human decision required before:
- Re-running with supplemented evidence
- Re-running with corrected device identity
- Accepting limitations and proceeding to Writer (requires explicit human authorization)
- Abandoning the run

## Distinction from REWORK

| REWORK | Controlled Compromise |
|---|---|
| Failure is fixable within graph | Failure is terminal for this run |
| Automatic re-route to upstream node | Human decision required |
| Bounded retry | No auto-retry |
| Same run continues | Run terminates |

---

*CCD 签发：2026-05-11*
