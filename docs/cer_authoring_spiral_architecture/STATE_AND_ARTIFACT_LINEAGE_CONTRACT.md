# STATE AND ARTIFACT LINEAGE CONTRACT

> CCD 签发 | 2026-05-11 | Phase 0 Architecture Freeze

## Spiral Loop State

Each spiral round must record:

```text
spiral_round_id: int (1, 2, 3)
rework_trigger_gate: gate_id that triggered rework
rework_reason: structured failure description
query_before: query used in this round
query_delta: what changed from previous round
records_before: record count before this round
records_added: new unique records this round
records_total: cumulative unique records
screened_delta: new records screened this round
appraised_delta: new records appraised this round
sufficiency_after_round: PASS | REWORK | BLOCKED
```

Output artifact: `evidence_spiral_lineage.json`

## Gate Routing Trace

Every gate invocation must record:

```text
gate_id
invocation_order: sequence in this run
status: PASS | REWORK_REQUIRED | BLOCKED
failure_pattern: if not PASS
upstream_node_routed_to: if REWORK
spiral_round: if in evidence loop
blocked_reason: if BLOCKED
```

Output artifact: `gate_routing_trace.csv`

## Pre-Writer Readiness

```text
pre_writer_readiness_gate status
failing_sub_conditions: list of (condition_name, status)
reroute_target: if REWORK
compromise_reason: if BLOCKED
writer_invoked: boolean
```

Output artifact: `pre_writer_readiness_report.json`

## Retrieval Pool Lineage

Each evidence item must trace:

```text
evidence_id
pmid / doi
spiral_round_acquired: which round it entered
screening_decision: include | exclude
screening_rationale
fulltext_status: available | unavailable | partial
```

Output artifacts: `pubmed_mcp_retrieval_ledger.csv`, `pmid_screening_and_exclusion_table.csv`

## Writer Consumption Trace

Each CER section must trace:

```text
section_id
evidence_ids consumed
claim_ids supported
gate_status_at_write_time: must be PASS for all upstream gates
```

Output artifact: `writer_evidence_consumption_trace.csv`

## Lineage Immutability

Once a run enters controlled_compromise or Writer completes:
- Spiral lineage is frozen
- Gate trace is frozen
- No post-hoc modification of routing decisions

---

*CCD 签发：2026-05-11*
