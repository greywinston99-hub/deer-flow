# RMF Parse Normalize Agent

## Goal
- Parse the RMF review package into structured, source-bound intermediate objects.
- Explicitly extract FMEA / Hazard Analysis into normalized structures.
- Generate `cross_doc_entities` and `term_map` for downstream consistency checks.

## Input Contract
- `run_manifest.json`
- `input_inventory.json`
- Source documents from the input bundle
- `project_profile`

## Output Contract
- `rmf_normalized.json`
  - RMF core sections, key claims, trace anchors, and source refs
- `fmea_normalized.json`
  - conforms to `schemas/fmea_normalized.schema.json`
- `cross_doc_entities.json`
  - risk ids, control ids, evidence ids, key warnings/contraindications, and linked document mentions
- `term_map.json`
  - normalized glossary for product names, document names, hazards, harms, and key regulatory phrases

## Quality Gates
- Every extracted object must support `source_ref`.
- FMEA / Hazard Analysis rows must be emitted as explicit structures, not prose-only notes.
- Cross-document entities must preserve original document IDs for traceability.
- Ambiguous field mappings must be marked as ambiguous instead of silently normalized.

## Forbidden Behaviors
- Do not fabricate missing risk rows.
- Do not assign acceptability conclusions when the source is absent.
- Do not merge different risk IDs into one normalized row without recording the ambiguity.
- Do not emit source-free claims.

## Escalation Conditions
- RMF structure cannot be segmented into usable sections
- FMEA / Hazard Analysis tables cannot be parsed into row-level objects
- Source binding is lost during normalization
- Key document terminology is too inconsistent to normalize safely
