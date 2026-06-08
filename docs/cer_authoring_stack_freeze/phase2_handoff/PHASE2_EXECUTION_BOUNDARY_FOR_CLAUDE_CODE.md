# PHASE 2 EXECUTION BOUNDARY FOR CLAUDE CODE

> CCD | 2026-05-15

## Your Role

You are the implementer. Not the controller. Not the owner.

## Allowed

- Fix Writer source generation: template de-contamination, IFU fact consumption
- Extract and hash actual runtime prompts
- Run Writer model A/B testing
- Generate domain-specific template pack
- Document agent team runtime inventory
- Document skill registry
- Document toolchain freeze
- Regenerate pilot CERs under frozen stack
- Add targeted tests
- Run full regression (≥284 tests)

## Forbidden

- Modify graph.py / gates.py / agents.py (unless owner explicitly authorizes)
- Modify EI Core _ei_* reasoning semantics
- Switch model as first remediation step — prompts and templates first
- Write gate-failed reports to release/final/customer-facing output
- Declare Pilot ready
- Claim customer-ready or NB-ready CER
- Expand scope beyond Phase 2 plan
- Remove existing gate logic (G1d, G6, G17, G18, Phase 1 gates)

## Owner Authorization Required For

- Any graph.py / gates.py / agents.py change
- Pilot authorization
- CER delivery claim
- Stack freeze declaration (CCD audits, owner approves)

---

*CCD 签发：2026-05-15*
