# REPAIR TASK — Cycle 1, Tier 1: Writer Isolation

## Assign to: VS Code Repair

## Priority: Tier 1 of 3

## Task

Implement two fixes that isolate Writer context and enforce a clean render boundary. These are prerequisites for all downstream QA gates.

## Fix 1 — Writer Input Packet

Before Writer agent invocation, build writer_input_packet.json containing exactly:
- locked_device_domain
- allowed_domain_terms
- forbidden_domain_terms
- selected_modules (writer modules only, no internal control modules)
- consumed_source_artifacts (paths only, not body content)
- claim_evidence_matrix (summary: claim_id → support_level → max_conclusion_strength)
- BR_ledger_summary (overall judgment, per-claim benefit/risk)
- conclusion_strength_constraints (per claim: allowed_language, forbidden_phrases)
- evidence_funnel_counts (stage-labeled: searched/returned/screened/fetched/appraised/registry/G42/writer)

Writer reads ONLY from this packet. No direct state access. This is the single source of truth for Writer generation.

## Fix 3 — Render Boundary

After Writer generates CER body text, scan the entire rendered output. Reject if any of the following appear:
- Writer instruction text ("Do NOT write", "should be evaluated", "confirm with manufacturer")
- Selected module names or internal module identifiers
- Trigger signal markers or internal routing metadata
- Internal gate debug strings or score values
- "FORBIDDEN" prefixed terms from the domain matrix
- "not_allowed", "ALLOWED_USE_BLOCKED", or internal control vocabulary
- Raw pipeline state keys or MCP tool identifiers

Rejected → CER draft goes to quarantine with rejection_reason recorded per occurrence.

## Acceptance

- writer_input_packet.json generated and verified before Writer runs
- Writer reads from packet only, not raw state
- Render boundary scanner runs after Writer, rejects contaminated output
- Re-run CAL-001. If render boundary triggers, report what it caught
- Do NOT modify graph.py, gates.py, agents.py, or EI Core

## Output

- changed_files.txt
- targeted_test_results.txt
- full_regression_result.txt
- CAL001 rerun gate report summary
- CER draft quarantine/release status
