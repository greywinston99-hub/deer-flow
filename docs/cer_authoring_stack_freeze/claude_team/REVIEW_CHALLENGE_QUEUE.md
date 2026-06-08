# REVIEW CHALLENGE QUEUE

> Review Agent | 2026-05-15 | Phase 2 Final Audit

---

## Open Challenges

*(None)*

---

## Resolved Challenges

### CHG-001: cardiovascular_rf_ablation_catheter domain mapping gap
- **Severity**: MAJOR
- **Phase**: 2A
- **Resolution**: FIXED — `DOMAIN_TEMPLATE_MAP` now includes both `cardiovascular_rf_ablation_catheter` (→ `therapeutic_catheter_template_sections`) and `surgical_ligating_clip` (→ `surgical_ligating_clip_template_sections`). Both have skeleton contracts with explicit forbidden cross-domain terms. Pipeline.py already provides full section composition via `_therapeutic_catheter_template_sections()` / `_surgical_implant_ligating_clip_template_sections()`.
- **Evidence**: `domain_templates.py` lines 363-443. `pipeline.py` lines 7052, 7078.
- **Status**: RESOLVED

### CHG-002: Model A/B testing not executed
- **Severity**: MAJOR
- **Phase**: 2C
- **Resolution**: DEFERRED with documented rationale. Dev Agent lacks LLM runtime access from VS Code — cannot invoke graph/Writer agent. Framework (7 dimensions, 3 candidates) documented for future execution. Model routing is config-driven (env var), not code-driven.
- **Evidence**: `DEV_RESPONSE_TO_REVIEW.md` lines 18-36. `WRITER_MODEL_SELECTION_REPORT.md` lines 20-48.
- **Status**: RESOLVED (deferred to runtime-available environment)

### CHG-003: IFU keyword matching is naive
- **Severity**: MEDIUM
- **Phase**: 2A
- **Resolution**: DOCUMENTED — KNOWN LIMITATION comment block added to `_text_relates_to_field()` documenting substring limitation, false-positive risk, Gate 2 mitigation, and planned improvement path.
- **Evidence**: `domain_templates.py` line 551.
- **Status**: RESOLVED

---

## Escalated to CCD

*(None)*
