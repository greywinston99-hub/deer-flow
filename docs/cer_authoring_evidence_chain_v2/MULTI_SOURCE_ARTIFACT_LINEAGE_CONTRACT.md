# MULTI-SOURCE ARTIFACT LINEAGE CONTRACT

> CCD 签发 | 2026-05-12

## New Artifacts (V2)

| Artifact | Content |
|---|---|
| `evidence_source_inventory.json` | All evidence sources found in 01_, classified by source_type + device_relationship |
| `similar_competitor_device_matrix.xlsx` | Per similar/competitor device: classification, comparability scores, allowed use |
| `source_anchoring_table.csv` | Per evidence item: source_type, source_anchor, source_provenance |
| `allowed_use_matrix.xlsx` | Per evidence item: which claim types it may support, max conclusion strength |
| `missing_data_register.csv` | Per evidence item: missing fields, impact, rationale |
| `multi_source_g42_routing_trace.csv` | Per G42 evaluation: source-type-specific sufficiency + REWORK route |
| `human_supplement_queue.json` | Items requiring human-provided data before evidence role can be determined |

## Extended Artifacts (V1→V2)

| Artifact | V2 Extension |
|---|---|
| `evidence_registry` | + source_type, source_anchor, device_relationship, comparability_score, allowed_claim_types, missing_data_flags |
| `claim_evidence_matrix` | + allowed_use_check per link |
| `gate_routing_trace` | + source_type dimension in G42 trace |
| `writer_evidence_consumption_trace` | + allowed_use verification per consumption |

## Lineage Immutability

Same as V1: frozen at controlled_compromise or Writer completion.

---

*CCD 签发：2026-05-12*
