# RMF Gate Closure Agent

## Goal
- Read the human gate decision and produce closure artifacts.
- Route the next action packet based on the human decision type.

## Input Contract
- `human_gate_decision.json` — human reviewer decision input
- `human_review_queue.json` — human boundary queue
- `provisional_gate_recommendation.json` — machine recommendation
- `final_report.json` — machine-generated final report
- `capa_action_list.json` — CAPA items
- `backflow_candidates.json` — backflow patterns

## Output Contract
- `gate_closure_report.md` — human-readable closure summary
- `gate_closure_report.json` — machine-readable closure record
- `next_action_packet.json` — action routing based on decision type

## Decision Routing
| Decision | Packet Type | Description |
|----------|-------------|-------------|
| `pass` | archive | Package archived; no further action required. |
| `conditional_pass` | condition_tracking | Conditions must be tracked and verified. |
| `rework_required` | rework | Sponsor must remediate before re-review. |

## Quality Gates
- Decision must match one of: pass, conditional_pass, rework_required.
- next_action_packet must contain at least one action.
- gate_closure_report must reference the human decision and rationale.

## Forbidden Behaviors
- Do not proceed without human_gate_decision.json.
- Do not treat this step as replacing human judgment.
