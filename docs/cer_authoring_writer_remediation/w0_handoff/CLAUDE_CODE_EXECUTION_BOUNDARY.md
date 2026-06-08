# CLAUDE CODE EXECUTION BOUNDARY

> CCD | 2026-05-15

## Allowed

- Add new gate evaluation functions in pipeline
- Add post-Writer output scanning
- Add quarantine routing in artifact export
- Modify Writer 2.1 field-to-source mapping
- Modify QA gate evaluation logic
- Add regression tests
- Write phase closeout files

## Forbidden

- Modify graph.py / gates.py / agents.py (unless owner explicitly authorizes)
- Modify EI Core _ei_* reasoning semantics
- Switch Writer model as first remediation step
- Start Pilot
- Claim customer-ready or NB-ready CER
- Write gate-failed reports to release/final/customer-facing directories
- Remove existing gate logic (G1d, G6, G17, G18, etc.)
- Reduce test coverage below 259

## Owner Authorization Required For

- Any graph.py / gates.py / agents.py change
- Writer model switch
- Pilot authorization
- CER delivery claim

---

*CCD 签发：2026-05-15*
