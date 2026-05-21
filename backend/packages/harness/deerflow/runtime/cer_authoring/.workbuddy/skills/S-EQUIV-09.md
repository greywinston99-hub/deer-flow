# S-EQUIV-09: Equivalent Device 3D Assessment

- **Type**: Prompt+Guard
- **Step**: Device Equivalence Search (Step 8B)
- **Batch**: P2
- **Agent**: authoring-risk-equivalence-gspr-agent

## Input
- `device_profile` (technical specs, materials, intended use)
- FDA 510k / AccessGUDID search results
- EUDAMED / equivalent device registration data

## Output
- `equivalence_matrix`: comparison_id, technical/biological/clinical characteristics, difference_impact_conclusion, confidence
- `similar_device_four_step_confirmation`

## Decision Logic
1. Three-dimensional scoring (technical / biological / clinical):
   - Each dimension: ≥ 5 assessment fields
   - Technical: design, materials, specifications, manufacturing, sterility
   - Biological: tissue contact, biocompatibility, degradation, leachables
   - Clinical: intended use, target population, anatomical site, procedure, outcomes
2. Composite scoring formula for overall equivalence determination
3. Difference analysis with clinical impact conclusion per dimension
4. Confidence levels: demonstrated / probable / not_claimed / gap
5. "Heart engine" mode: if no equivalent device exists → `equivalence_not_claimed`

## Checks
- Each dimension has ≥ 5 assessment fields
- Difference analysis has clinical impact conclusion
- Overclaimed equivalence blocked (no "demonstrated" with low confidence)
- "Heart engine" path activates when no equivalent found
