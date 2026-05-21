# W-SOTA-21: Clinical Background / SOTA Narrative

- **Type**: Prompt+Guard
- **Step**: CER Writing 28.5 (§3.x Clinical Background)
- **Batch**: P0
- **Agent**: authoring-cer-writer-agent

## Input
- `sota_clinical_context_table`: domain-aware clinical context
- `sota_benchmark_table`: quantitative benchmarks
- `cross_evidence_synthesis_table`: evidence synthesis
- `guideline_pathway_table`: clinical guidelines
- `alternative_treatment_benchmark_table`: alternative treatments
- `hazard_source_table`: known hazards

## Output
- §3.1-§3.9: Clinical background, current knowledge, SOTA

## Decision Logic (Narrative structure)
1. **Disease Background** (§3.1-3.2): condition, epidemiology, pathophysiology
2. **Target Population** (§3.3): demographics, inclusion/exclusion
3. **Existing Treatments** (§3.4): current standard of care, limitations
4. **Similar Device Benchmarks** (§3.5-3.6): competitor benchmarks, device class overview
5. **Known Hazards** (§3.7): procedure and device-related complications
6. **Safety & Performance Endpoints** (§3.8-3.9): SOTA benchmark ranges, device positioning

## Writing Rules
- Every claim answers "What does this mean for our device?"
- Benchmark data has "bridge sentences" to clinical meaning
- NO template residue (Gate W4 enforced)
- Each SOTA statement has literature trace

## Checks
- No template placeholder text
- Benchmark-to-clinical-meaning bridges present
- SOTA data consistent with `sota_benchmark_table`
- 5+ human-reviewed SOTA sections
