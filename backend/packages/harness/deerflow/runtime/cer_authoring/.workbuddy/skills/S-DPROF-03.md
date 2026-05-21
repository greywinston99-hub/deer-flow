# S-DPROF-03: Device Profile Disambiguation

- **Type**: Prompt+Guard
- **Step**: Device Profile (Step 3)
- **Batch**: P1
- **Agent**: authoring-intake-profile-claim-agent

## Input
- `document_structured_content` from IFU parsing
- Source inventory with IFU page/paragraph trace

## Output
- `device_profile`: device_name, device_type, intended_purpose, mode_of_action, anatomical_site, target_population, device_class, sterility, shelf_life, composition, working_principle, performance_summary, warnings, contraindications

## Decision Logic (8-level arbitration priority)
1. Deterministic source fields (model number, classification from IFU header) — highest priority
2. IFU structured section headers (e.g., "Intended Use", "Device Description")
3. IFU body text with keyword anchors ("is indicated for", "is intended to")
4. Regulatory database lookup (FDA 510k, EUDAMED) for classification
5. Domain template defaults from `DOMAIN_DEFAULTS`
6. Agent reasoning from full IFU context
7. Similar device profile inference
8. Manual placeholder (HUMAN_HOLD) — lowest priority

## Checks
- `mode_of_action` not polluted by accessory keywords
- `anatomical_site` is specific (e.g., "right atrium" not "heart")
- `device_name` matches IFU header, not filename
- Agent reasoning items flagged in `device_identity_arbitration`
