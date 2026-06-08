# EVIDENCE CONFLICT DETECTION SPEC

> CCD 签发 | 2026-05-12 | V3-Core

## Problem

Multiple studies may report conflicting results for the same endpoint. This must be detected and flagged, not silently averaged or ignored.

## Conflict Types

| Type | Example | Severity |
|---|---|---|
| DIRECTIONAL | Study A shows benefit, Study B shows harm | CRITICAL |
| MAGNITUDE | Effect sizes differ by >2x | HIGH |
| STATISTICAL | Significant vs non-significant for same endpoint | HIGH |
| POPULATION | Different population subgroups show different effects | MEDIUM |
| TEMPORAL | Short-term vs long-term outcomes diverge | MEDIUM |

## Detection Method — Cluster-Based

Group by endpoint_cluster_id (not just endpoint_family). Each cluster includes:
  endpoint + timepoint + population + procedure/anatomy + device_relationship + comparator (where available)

For each cluster, compare normalized values. Flag conflicts where:
  - Directional mismatch (positive vs negative effect)
  - Magnitude ratio >2.0
  - Significance mismatch (p<0.05 vs p>0.05)

## Conflict Impact

CRITICAL conflict → claim-specific impact (only claims linked to conflicting evidence).
Conflict impact recorded per claim in evidence_conflict_report.json.

## Output

`evidence_conflict_report.json`:
- conflict_id, endpoint_family, evidence_ids, conflict_type, severity, description

## G42 Impact

CRITICAL conflict → evidence role capped at supportive (cannot be pivotal for any claim)
HIGH conflict → claim flagged for human review

---

*CCD 签发：2026-05-12*
