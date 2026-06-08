# Critical Thinking Patterns (V20)

**Version**: V20.0 | **Flag**: v20_dynamic_hypotheses | **Used by**: GS Stage 2b

Five universal patterns for dynamic hypothesis generation. These patterns are applied to claim text IN REAL TIME during GS Stage 2 — they are not pre-loaded device-type libraries. They tell GS HOW to think, not WHAT to find.

---

## Core Principle

```
GS reads claim → applies patterns → generates hypotheses FROM the claim text
→ tests each hypothesis against evidence → escalates unresolved hypotheses
```

Hypotheses are generated dynamically from what GS reads, not retrieved from a library. The patterns are universal — they apply to any CER, any device type.

---

## Pattern 1 — DATE CHECK

**Trigger**: Any date mentioned in the claim or its evidence.

**Questions to ask**:
1. Is the date recent? (>3 years → investigate staleness)
2. Does the date align with the document's signature date? (gap → investigate)
3. Has anything changed since this date? (design change? standard update? predicate recall? new guideline?)

**Example hypotheses generated**:
- "Evidence from 2019 — 7 years old. For [device type], SOTA may have changed. Check if newer data exists."
- "CER signed 2025 but data search ended 2023. 2-year gap. Was newer evidence considered?"
- "Predicate device FDA cleared 2018 — 8 years ago. Has predicate been recalled or updated? Is it still on the market?"
- "ISO 14971:2007 referenced but current version is 2019+A11:2021. Was the migration managed?"

**Action**: For each date found, generate at least one staleness hypothesis. Test against current standards/guidelines/databases.

---

## Pattern 2 — SOURCE CHECK

**Trigger**: Any evidence cited to support a claim.

**Questions to ask**:
1. Where does this evidence come from? Manufacturer? Published literature? Predicate manufacturer? Registry?
2. If predicate → Is predicate MDR-certified? Is access to predicate technical documentation declared (Art 61(10))?
3. If manufacturer-generated → Is it independently verified? Any third-party validation?
4. If published literature → Peer-reviewed? Recent enough? Relevant jurisdiction (EU vs FDA vs NMPA)?
5. If registry → Which registry? Public or private? Quality-controlled?

**Example hypotheses generated**:
- "Predicate device is NMPA-registered only. Under MDR Art 61(10), manufacturer must declare access to predicate TD. Is this declared?"
- "Clinical data from manufacturer's own PMCF — not independently verified. Any third-party clinical evidence?"
- "Literature cited is from non-EU jurisdiction (FDA studies). Are results transferable to EU population under MDR?"
- "Expert opinion cited as primary evidence for safety claim. Expert opinion has lowest evidential weight under MEDDEV 2.7/1."

**Action**: For each evidence source, generate a source-quality hypothesis. Test against MDR evidence hierarchy.

---

## Pattern 3 — COVERAGE CHECK

**Trigger**: Any claim that asserts coverage of indications, populations, or device configurations.

**Questions to ask**:
1. What does this claim COVER? (list: indications, populations, configurations, accessories)
2. Compare against intended use statement in §2. Does the claim cover EVERYTHING?
3. What is MISSING from the coverage? (pediatric? pregnant? specific indications?)
4. Does evidence cover all claimed populations? (e.g., clinical data from adults only but device indicated for all ages)

**Example hypotheses generated**:
- "CER claims safety for all patient populations but clinical data covers adults only (age 18-65). Pediatric and elderly populations not represented in evidence."
- "Device has 8 models/configurations but equivalence comparison table covers only 1 model. Other 7 models not addressed."
- "Indications include [A, B, C] but clinical evidence only covers [A, B]. Indication C lacks supporting data."
- "IFU says 'no known contraindications' — Coverage Check: are there REALLY no contraindications? What do guidelines say?"

**Action**: Map claim coverage against intended use. Flag every gap between claimed coverage and evidenced coverage.

---

## Pattern 4 — CONSISTENCY CHECK

**Trigger**: Any claim that relates to content in another document or another section of the same document.

**Questions to ask**:
1. Does this claim appear consistently across CER/RMF/IFU/GSPR? (use cross-family argument map)
2. CER §X says A. RMF §Y says B about the same topic. Does A == B?
3. IFU contraindications match CER B-R conclusions? IFU warnings traceable to RMF hazards?
4. GSPR checklist claims conformance — does the referenced evidence actually demonstrate conformance?
5. If inconsistency found → is it a contradiction (cannot both be true) or staleness (one is outdated)?

**Example hypotheses generated**:
- "CER says 'device is Class IIb.' RMF uses Class II risk matrix. Are these consistent? (MDR classification ≠ ISO 14971 risk class — may be valid but must be explained)"
- "IFU contraindication: 'Not for use on pregnant patients.' CER B-R conclusion: 'Acceptable benefit-risk for all indicated populations.' Contradiction: if contraindicated, B-R should reflect this."
- "GSPR 11.7 claims conformance to EN 60601-1. Does the referenced test report cover GSPR 11.7 specifically?"

**Action**: Cross-reference using argument map dependency graph. Flag every inconsistency with both document references.

---

## Pattern 5 — ASSUMPTION CHECK

**Trigger**: Every claim. This is the most powerful pattern.

**Questions to ask**:
1. What does this claim ASSUME to be true?
2. "Equivalent to predicate X" → assumes X is a valid predicate, assumes access to X's TD, assumes X is still on the market, assumes X's safety profile is known
3. "Class IIb" → assumes the classification is correct under MDR Annex VIII
4. "No clinical investigation needed" → assumes Art 61(5) WET exemption or Art 61(10) equivalence applies
5. "Benefits outweigh risks" → assumes all risks have been identified, assumes benefit quantification is accurate
6. "State of the art" → assumes the referenced standards and literature represent CURRENT SOTA

**Example hypotheses generated**:
- "Claim: 'Equivalent to predicate X.' Assumption: Predicate X is a valid MDR predicate. CHALLENGE: Is predicate X MDR-certified? Is predicate X still marketed in EU? Does manufacturer have access to X's full technical documentation?"
- "Claim: 'PMCF plan is adequate.' Assumption: The PMCF activities will actually generate meaningful clinical data. CHALLENGE: Does the PMCF plan name specific data sources with sample sizes and timelines? Or is it generic?"
- "Claim: 'Device classification: Class IIb.' Assumption: Classification is correct. CHALLENGE: Verify against MDR Annex VIII rules. Is it active? Implantable? Surgical? Does it deliver energy?"
- "Claim: 'No known contraindications.' Assumption: There are genuinely no populations or conditions where the device should not be used. CHALLENGE: What do clinical guidelines say? What do similar device IFUs say?"

**Action**: For every claim, identify at least one assumption. Challenge it. Verify independently. This pattern alone generates the most high-value hypotheses.

---

## Hypothesis Chain Rules

**Max depth**: 3 levels. Beyond 3 levels, marginal value of deeper reasoning diminishes.

```
Level 1: Direct hypothesis about the claim
  "Is retrospective data sufficient for Class III?"
  
Level 2: If Level 1 hypothesis is unresolved (evidence doesn't answer it):
  "If retrospective data is insufficient, what was the manufacturer's strategy?"
  → Check CER §3 for equivalence claim
  
Level 3: If Level 2 reveals a strategy issue:
  "If equivalence is the strategy, is it validly demonstrated?"
  → Check predicate TD access, predicate MDR certification, Art 61(10) compliance
```

**Stopping rules**:
- Hypothesis resolved by evidence → STOP (note as VERIFIED)
- Hypothesis chain reaches Level 3 → STOP (flag as UNRESOLVED, escalate to deep-dive)
- Hypothesis leads outside review scope (e.g., requires clinical judgment) → STOP (note RC-8 boundary)

**Deep-dive activation**: Only when Level 3 hypothesis is UNRESOLVED AND claim priority is HIGH or MEDIUM. Do NOT deep-dive on LOW-priority claims.

---

## Pattern Application Rules

**When to apply each pattern**:

| Pattern | Apply When | Skip When |
|---------|-----------|-----------|
| DATE CHECK | Any date in claim or evidence | No temporal data in claim |
| SOURCE CHECK | Evidence cited to support claim | Claim has no evidence citation |
| COVERAGE CHECK | Claim about indications, populations, configurations | Claim is purely procedural (e.g., "document was reviewed") |
| CONSISTENCY CHECK | Claim relates to content in other documents (argument map dependency exists) | Claim is self-contained within one document section |
| ASSUMPTION CHECK | ALWAYS — every claim has assumptions | — |

**Minimum application**: At minimum, apply PATTERN 5 (ASSUMPTION CHECK) to every claim. Apply other patterns when triggers are present.

---

## Output Format

```json
{
  "claim_id": "MASTER-Claim-3",
  "hypotheses_generated": [
    {
      "pattern": "ASSUMPTION_CHECK",
      "level": 1,
      "hypothesis": "Assumes predicate X is MDR-certified. Is it?",
      "tested_against": "Predicate regulatory status in source documents + MDR database reference",
      "result": "UNRESOLVED — predicate regulatory status not documented",
      "escalated": true
    },
    {
      "pattern": "ASSUMPTION_CHECK",
      "level": 2,
      "hypothesis": "If predicate not MDR-certified, can equivalence still be claimed under Art 61(10)?",
      "tested_against": "MDR Art 61(10) requirements for predicate TD access",
      "result": "UNRESOLVED — manufacturer has not declared access to predicate TD",
      "escalated": true
    },
    {
      "pattern": "DATE_CHECK",
      "level": 3,
      "hypothesis": "Predicate FDA clearance 2018 — 8 years old. Has SOTA changed?",
      "tested_against": "SOTA literature date range in CER §3-4",
      "result": "CONFIRMED — CER literature search ended 2023, 2-year gap",
      "escalated": false
    }
  ],
  "deep_dive_triggered": true,
  "deep_dive_depth": 3,
  "max_hypothesis_chain_depth": 3
}
```

---

## Reflection Pass (Stage 2.5)

After all claims have been traced in Stage 2, execute a reflection pass to re-weight findings based on the cross-family argument map dependency graph.

**For each claim in the dependency graph**:

**FOUNDATIONAL claims** (other claims depend on this one):
- IF claim was found WEAK (low evidence quality, unresolved hypotheses):
  → **Elevate severity**: the weakness cascades through the entire CER
  → Add `cascade_impact`: "This foundational claim is weak. [N] downstream claims (CLAIM-X, CLAIM-Y, ...) depend on it. Fix this first."
  → Severity elevation: WEAK foundational → escalate to HIGH. MODERATE foundational with unresolved hypotheses → escalate to HIGH.

**DEPENDENT claims** (depends on a FOUNDATIONAL claim that was found WEAK):
- Add `dependency_note`: "May be impacted by upstream weakness in CLAIM-X. Fix CLAIM-X first, then re-evaluate this claim."
- **DO NOT change this claim's independent severity.** The independent gap is still valid and reported separately. The dependency_note informs the human reviewer of the review order: fix upstream first, then re-evaluate.

**Independent claims** (no dependencies, no dependents):
- No re-weighting applied. Severity stands as assessed in Stage 2.

**Output**: `claim_reweighting` — list of claims with:
- `claim_id`, `role` (FOUNDATIONAL | DEPENDENT | INDEPENDENT)
- `original_severity`, `adjusted_severity` (if FOUNDATIONAL and weak)
- `dependency_note` (if DEPENDENT on a weak foundation)
- `cascade_impact` (if FOUNDATIONAL and weak: N downstream claims affected)
