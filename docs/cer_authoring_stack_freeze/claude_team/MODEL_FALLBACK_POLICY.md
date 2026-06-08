# MODEL FALLBACK POLICY — CER Authoring V1.0

> Claude Code | 2026-05-15 | Phase 2C

## Policy

1. Fallback is currently DISABLED (no fallback models configured).
2. If the primary model becomes unavailable:
   - Writer generation stops.
   - In-progress CER authoring is paused.
   - State is preserved for resumption.
   - Owner is notified.

## Rationale

Fallback models can produce:
- Different domain consistency behavior (may introduce cross-domain text)
- Different evidence-conclusion phrasing (may violate gate constraints)
- Different template adherence (may ignore domain-specific instructions)

A fallback model that passes Gate 1 but weakens Gate 3 quality is a regression.

## If Fallback Is Needed

1. The fallback model must pass the same gate suite as the primary model.
2. Full regression must be run with the fallback model.
3. Fallback model performance must be documented in MODEL_ROUTING_POLICY.md.
4. Fallback is a configuration change (env var or runtime config), not a code change.

## Resumption Protocol

When primary model becomes available again after a fallback period:
1. Restore CER_AUTHORING_MODEL_NAME to primary model.
2. Re-run any CER drafts generated during fallback through gates 1-5.
3. Flag and quarantine any fallback-generated drafts that fail gates.
