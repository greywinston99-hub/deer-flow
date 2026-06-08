# BIGDP2026.6 — Phase 6: Review Feedback Boundary Report

**Date:** 2026-06-08
**Status:** COMPLETE — Review boundary clarified, SOP documented

---

## 1. Single Production Review Path

**Designated production path:** `cer_review_v1.yaml` (D1 workflow)

The review system has one active production workflow:
- `workflows/cer_review_v1.yaml` — active, versioned (`version: "1"`)

Deprecated paths:
- `cer_review_v0.yaml` — deprecated, marked in file header
- Legacy D1 runner — superseded by v1

`runner.py` now uses explicit `version` field from workflow YAML. Unknown versions cause fast-fail.

---

## 2. Review Feedback Boundary

**Default behavior:** Review feedback is **advisory-only**. Review findings are surfaced in human interrupt payloads for decision but do NOT trigger automatic rework.

Per Decision D-005:
> Review feedback backflow to Authoring (auto-rework based on Review findings) is NOT enabled by default.

**Implementation:**
- `review_feedback_ingestion` node exists in graph.py (feature-flagged `DF_REVIEW_FEEDBACK_INGESTION`, default disabled)
- When enabled, Review findings are loaded as read-only advisory context
- Human must explicitly confirm any rework action based on Review feedback

---

## 3. Human-Mediated Review → Authoring SOP

### When Review Identifies Issues

1. **Review pipeline completes** → `CER_REVIEW_FINDINGS.json` produced
2. **Human reviews findings** on Review dashboard
3. **Human decides** which findings warrant Authoring rework
4. **Human opens Authoring project** and triggers HC rework at the relevant confirmation point
5. **Authoring pipeline re-runs** from the rework target node
6. **Re-review** confirms resolution

### What Review Does NOT Do
- Does NOT automatically modify claim wording
- Does NOT automatically change evidence assessments
- Does NOT automatically rewrite CER sections
- Does NOT bypass G46 Writer Release Board

---

## 4. Feature Flag

```bash
# Enable experimental review feedback ingestion (OFF by default)
export DF_REVIEW_FEEDBACK_INGESTION=true
```

The ingestion node, when enabled:
- Loads `CER_REVIEW_FINDINGS.json` from the review artifact directory
- Surfaces findings as advisory context in human interrupt payloads
- Does NOT trigger automatic rework
- Logs all loaded findings for audit trail
