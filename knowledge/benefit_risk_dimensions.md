# Benefit-Risk Dimensions (V21)

**Version**: V21.0 | **Flag**: v21_br_10dim | **Used by**: GS Stage 3

10 dimensions for benefit-risk analysis assessment. All dimensions scored by AI. No HUMAN dimensions in B-R (unlike PMCF).

**Rule**: AI scores each dimension individually. AI never judges whether "benefits outweigh risks." Final B-R determination is HUMAN.

---

## Dimensions 1-6: V20 Original (Preserved)

### Dimension 1 — Claim Identification
**Score 2**: Every claimed benefit explicitly listed with source section reference.  
**Score 1**: Benefits described but not individually enumerated.  
**Score 0**: Benefits only stated generically ("device is beneficial").

### Dimension 2 — Evidence Mapping
**Score 2**: Each claimed benefit mapped to specific clinical evidence with citation.  
**Score 1**: Benefits linked to evidence categories but not specific studies.  
**Score 0**: No mapping between benefits and evidence.

### Dimension 3 — Risk Mapping
**Score 2**: Each benefit assessed against RMF-identified hazards that could offset it.  
**Score 1**: Risks mentioned generally but not mapped to specific benefits.  
**Score 0**: No risk-benefit cross-reference.

### Dimension 4 — Quantification Check
**Score 2**: Benefits AND risks quantified with numbers, rates, confidence intervals.  
**Score 1**: One side quantified (benefits OR risks), other qualitative only.  
**Score 0**: Both benefits and risks described qualitatively only.

### Dimension 5 — Residual Risk Reference
**Score 2**: B-R analysis explicitly references RMF residual risk evaluation with document cross-reference.  
**Score 1**: Residual risk mentioned but not explicitly referenced to RMF section.  
**Score 0**: No residual risk reference; B-R analysis disconnected from RMF.

### Dimension 6 — Population Scope
**Score 2**: B-R covers ALL indicated populations (adult, pediatric, elderly, pregnant where applicable) with population-specific analysis.  
**Score 1**: Population subgroups mentioned but not analyzed separately.  
**Score 0**: Single population assumed; no subgroup differentiation.

---

## Dimensions 7-10: V21 NEW

### Dimension 7 — Benefit Magnitude Quantification
**Score 2**: Benefit magnitude quantified (effect size, NNT, absolute risk reduction, QALY gain) with clinical context.  
**Score 1**: Benefit described numerically but without clinical context (e.g., "HbA1c reduced by 0.5%" but no reference to clinical meaningfulness).  
**Score 0**: Benefit described only qualitatively ("improved outcomes", "better quality of life").

### Dimension 8 — Risk Acceptability by Indication
**Score 2**: Risk acceptability assessed separately for EACH indication, recognizing that the same risk profile may be acceptable for one indication but not another.  
**Score 1**: Risk acceptability mentioned but not stratified by indication.  
**Score 0**: Single risk acceptability judgment applied uniformly without indication differentiation.

### Dimension 9 — Alternative Therapy Comparison
**Score 2**: CER explicitly compares benefit-risk profile against named alternative therapies (surgical, pharmaceutical, other devices) with evidence.  
**Score 1**: Alternatives mentioned but no structured B-R comparison.  
**Score 0**: No alternative therapy comparison; device evaluated in isolation.

### Dimension 10 — Uncertainty Quantification
**Score 2**: Sources of uncertainty in B-R analysis explicitly identified and discussed (e.g., limited sample size, short follow-up, single-arm design, literature heterogeneity).  
**Score 1**: Limitations section exists but does not specifically address B-R uncertainty.  
**Score 0**: No uncertainty discussion; B-R presented as definitive.

---

## B-R Dimension Summary Output

```json
{
  "benefit_risk_dimension_profile": {
    "dim1_claim_identification": 0,
    "dim2_evidence_mapping": 0,
    "dim3_risk_mapping": 0,
    "dim4_quantification": 0,
    "dim5_residual_risk_reference": 0,
    "dim6_population_scope": 0,
    "dim7_benefit_magnitude": 0,
    "dim8_risk_acceptability_by_indication": 0,
    "dim9_alternative_therapy_comparison": 0,
    "dim10_uncertainty_quantification": 0
  },
  "total": "X/20 (10 dimensions × max 2 points each)",
  "overall_assessment": "AI has scored 10 dimensions. Benefit-risk determination — whether benefits outweigh risks for each indication — is a HUMAN clinical judgment. AI reports dimension scores only."
}
```
