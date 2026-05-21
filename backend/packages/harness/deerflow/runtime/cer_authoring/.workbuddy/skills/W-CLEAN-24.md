# W-CLEAN-24: Body Cleanliness Rules

- **Type**: Deterministic
- **Step**: CER Writing 28.9 (Cleanliness enforcement)
- **Batch**: P0
- **Agent**: authoring-cer-writer-agent

## Input
- CER chapter drafts (all §1-§9 + Annex text)
- `banned_internal_strings` list (50+ patterns)
- `domain_term_matrix`

## Output
- `writer_remediation_gate_results`: W1-W6 gate decisions
- `context_contamination_trace`

## Banned Patterns (50+ items, categories)
**System Language**: "Claude/DeerFlow must generate", "as an AI", "according to my training", "I will now write"
**Template Residue**: "This CER evaluates whether", "According to MEDDEV 2.7/1", "placeholder", "[insert]", "TBD"
**Internal Control Fields**: "ALLOWED_USE_BLOCKED", "quantitative_or_source-reported", "EVIDENCE_PENDING"
**Placeholders**: "Not extracted from IFU", "---SEGMENT---", "[translation failed]", "pending execution"
**Format Pollution**: "WhenWhenWhen", "Sample Sample Sample", "VersionVersion"

## Decision Logic
1. Regex scan all chapter text for each banned pattern
2. Auto-fixable: template residue deletion, duplicate word removal
3. Non-auto-fixable: system language leakage → HARD_FAIL → quarantine
4. Context exceptions: permitted in Annex M (engineer comments), not in body

## Checks
- 50+ banned patterns defined with detection regex
- Auto-fix rules defined per pattern
- Zero leakage on 10+ test cases
- Gate W4 enforces at export time
