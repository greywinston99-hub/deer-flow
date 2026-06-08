## V28.4: Mandatory Findings Output (ALL CEP Sub-Agents)

This section is AUTO-INJECTED into all 5 CEP sub-agent prompts.
It replaces ad-hoc finding instructions with a unified format.

### Output Contract — MANDATORY

Your JSON output MUST include a `findings` array.  Every finding must have:

```json
{
  "finding_id": "string — unique ID",
  "defect_code": "DO-001|GS-001|EV-001|EQ-001|CL-001|PM-001|BR-001|DT-001|MF-001|LB-001|SW-001|null",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "source_location": "specific CER section, table, or appendix",
  "evidence_gap": "what exactly is missing or insufficient",
  "regulatory_anchor": "specific MDR Article, GSPR clause, ISO standard, or MDCG paragraph",
  "recommended_action": "concrete remediation step"
}
```

### Severity Rules

- **CRITICAL**: Blocks regulatory submission. Missing required section, no clinical data for intended use, equivalence claimed without TD access.
- **HIGH**: Significant gap. INCOMPLETE GSPR, missing PRISMA, unjustified N/A, unsupported claim.
- **MEDIUM**: Notable deficiency. Thin section, outdated standard reference, missing detail.
- **LOW**: Minor improvement. Format issue, wording inconsistency, optional enhancement.

### Defect Code Reference

Map your findings to known NB defect patterns. If your finding matches a known pattern, include the defect code:

| Code | When to Use |
|------|------------|
| DO-001 | Device description incomplete, variant without rationale, intended purpose vague |
| GS-001 | GSPR N/A without justification, incomplete checklist, standard reference outdated |
| EV-001 | Search strategy not documented, PRISMA missing, SOTA lacks device positioning, benchmark unreferenced |
| EQ-001 | Only one comparator, three-pillar incomplete, difference not justified, no TD access evidence |
| CL-001 | Study design not described, sample size unjustified, endpoints undefined, limitations not discussed |
| PM-001 | PMCF plan vague, no timeline, data sources unspecified, trigger conditions missing |
| BR-001 | B-R qualitative only, no quantitative comparison, residual risks not referenced from RMF |
| DT-001 | Data inconsistency across chapters, spec mismatch, literature count ≠ Annex |
| MF-001 | Process validation missing, sterilization validation incomplete, cleanroom not evidenced |
| null | Finding does not match a known defect pattern |

### Finding Granularity

- ONE finding = ONE specific gap.  Do NOT combine multiple gaps into one finding.
- If a section has 3 separate deficiencies, produce 3 separate findings.
- Each finding must be independently verifiable — a human reviewer should be able to check the CER and confirm or refute the finding without reading other findings.

### Minimum Findings Per Agent

Each sub-agent must produce at least:
- SOTA Literature: ≥3 findings (search strategy, benchmark completeness, alternative treatments)
- Evidence Adequacy: ≥3 findings (study quality, population coverage, endpoint relevance)
- Equivalence: ≥3 findings per dimension if equivalence is claimed (technical, biological, clinical)
- PMS/PMCF: ≥1 finding per dimension scored <2 (13 dimensions)
- Benefit-Risk: ≥3 findings (benefit quantification, risk mapping, alternative comparison)

If the CER is complete and no gaps exist, produce a single finding with severity=LOW stating "No critical gaps identified; all [N] checks passed."
