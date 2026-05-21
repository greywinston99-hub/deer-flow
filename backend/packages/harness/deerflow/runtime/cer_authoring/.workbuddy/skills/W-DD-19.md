# W-DD-19: Device Description Writing

- **Type**: Prompt+Guard
- **Step**: CER Writing 28.2 (§2.1 Device Description)
- **Batch**: P0
- **Agent**: authoring-cer-writer-agent

## Input
- `device_profile`: composition, working_principle, performance_summary, variants, sterility
- `document_structured_content` from IFU parsing

## Output
- §2.1 Device Description: ≥ 500 chars of substantive content

## Decision Logic (6 required elements)
1. **Composition**: materials, components, coatings, drug-eluting components
2. **Working Principle**: mechanism of action, energy delivery, physical/chemical principle
3. **Performance**: key performance characteristics, specifications, tolerances
4. **Variants**: model numbers, sizes, configurations in scope
5. **Sterility**: sterilization method, shelf life, packaging
6. **Accessories**: compatible accessories, required ancillary equipment

## IFU Location Rules
- Composition → IFU "Device Description" / "Materials" section
- Working principle → IFU "Principle of Operation" / "How it Works"
- Performance → IFU "Technical Specifications" / "Performance Characteristics"
- Distinguish device from surgical procedure context

## Checks
- Output ≥ 500 chars
- NO "Not extracted from IFU source text"
- Each element has IFU page/paragraph trace
- Device vs surgery context correctly separated
- 5+ human-reviewed descriptions
