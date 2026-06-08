# BIGDP2026.6V_2 — Locked Feedback Use Policy

**Status:** EFFECTIVE | **Date:** 2026-06-08

---

## Principle

Locked feedback (NB feedback, engineer feedback, customer-specific conclusions) may be used for calibration, rule induction, fixture generation, and evaluator design. It must NOT enter Writer input, CER_INPUT_PACKAGE for writing, or final CER generation context.

## Asset Classification

| Asset Type | Default Access | Can Enter Runtime? | Can Enter Writer Input? |
|:---|:---|:---:|:---:|
| Golden Feedback Pack | LOCKED_NO_WRITER | No | No |
| NB Feedback | LOCKED_NO_WRITER | No | No |
| Engineer Feedback | CALIBRATION_ONLY | Yes (generalized rules only) | No |
| Final Accepted CER | VALIDATION_ONLY | No | No |
| Gold Labels (any type) | LOCKED_NO_WRITER | No | No |
| Real Project IFU/RMF | WRITER_ALLOWED | Yes | Yes |
| Published Literature | WRITER_ALLOWED | Yes | Yes |

## Derived Artifact Policy

Rules, thresholds, labels, and classifiers **derived from** locked feedback MAY enter runtime if:
1. They are generalized (not project-specific)
2. The derivation process is documented
3. Locked source content is not embedded in the rule
4. The rule is independently testable without the locked source

## Prohibition

- Specific NB comments must NOT appear in Writer input
- Engineer comments must NOT appear in Writer input
- Customer-specific conclusions must NOT appear in Writer input
- Project-specific final wording must NOT appear in Writer input
