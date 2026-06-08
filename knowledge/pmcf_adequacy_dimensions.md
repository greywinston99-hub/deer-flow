# PMCF Adequacy Dimensions (V21)

**Version**: V21.0 | **Flag**: v21_pmcf_13dim | **Used by**: GS Stage 3

13 dimensions for PMCF plan/program assessment. AI scores dimensions 1-8, 10-13. HUMAN dimensions (7c, 9d) are clearly marked and left blank for human reviewer.

**Rule**: AI scores each dimension individually. AI never judges overall "adequacy." Final judgment is HUMAN.

---

## AI-Scored Dimensions (1-8, 10-13)

### Dimension 1 — Data Source Type
**Score 2**: ≥1 named proactive source (specific registry, named clinical study, structured survey with defined sample).  
**Score 1**: Generic source named but no details (e.g., "registry study" without naming which registry).  
**Score 0**: Only passive sources listed ("literature review", "complaint monitoring", "PMS data review").

### Dimension 2 — Sample Size Specification
**Score 2**: Specific sample size given with rationale (e.g., "100 patients over 2 years from EUDAMED registry X").  
**Score 1**: Number given without rationale or calculation basis.  
**Score 0**: Vague descriptors ("adequate", "sufficient", "as needed").

### Dimension 3 — Timeline with Milestones
**Score 2**: Specific dates/quarters with defined milestones and deliverables.  
**Score 1**: Date range given but no intermediate milestones.  
**Score 0**: "ongoing", "continuous", "regular" — no time-bound commitments.

### Dimension 4 — CER Gap Coverage
**Score 2**: Each CER-identified clinical evidence gap has a corresponding, specifically-named PMCF activity.  
**Score 1**: Some CER gaps addressed, others not referenced.  
**Score 0**: No CER gaps referenced; PMCF plan disconnected from CER findings.

### Dimension 5 — Device Class Proportionality (MDCG 2020-7)
**Score 2**: Class III ≥3 proactive sources, Class IIb ≥2, Class IIa ≥1.  
**Score 1**: Below MDCG 2020-7 threshold but at least 1 proactive source.  
**Score 0**: No proactive sources for any class, or all sources are passive.

### Dimension 6 — Study Design Type Detected
**Score 2**: Study design explicitly named (RCT, prospective cohort, registry-based, case-control, etc.) with design justification.  
**Score 1**: Study mentioned but design type not specified.  
**Score 0**: No study mentioned; only passive data collection.

### Dimension 7a — Endpoint Type
**Score 2**: Clinical outcomes (survival, QoL, functional status, adverse events) specified as endpoints.  
**Score 1**: Technical/performance endpoints only (device output, accuracy) without clinical correlation.  
**Score 0**: No endpoints defined.

### Dimension 7b — Endpoint Objectively Measurable
**Score 2**: Endpoints are objectively measurable with defined measurement methods and thresholds.  
**Score 1**: Endpoints described but measurement method not specified.  
**Score 0**: Endpoints are subjective or undefined.

### Dimension 7c — Endpoint Clinically Meaningful [HUMAN JUDGMENT REQUIRED]
**LEFT BLANK BY AI.** Human reviewer assesses: Are the chosen endpoints clinically meaningful for the device's intended purpose? Do they reflect outcomes that matter to patients and clinicians?

### Dimension 8 — Follow-up Duration vs Benchmark
**Score 2**: Follow-up duration meets or exceeds device-class benchmark (Class III implant: ≥2yr; Class IIb: ≥1yr; Class IIa: ≥6mo).  
**Score 1**: Some follow-up but below benchmark.  
**Score 0**: No follow-up defined or follow-up grossly inadequate for device lifetime.

### Dimension 9a — Comparator Name
**Score 2**: Comparator explicitly named with model/version identifier.  
**Score 1**: Comparator type described but not specifically named.  
**Score 0**: No comparator defined.

### Dimension 9b — Comparator Regulatory Status
**Score 2**: Comparator regulatory status documented (MDR-certified, FDA-cleared, NMPA-registered, etc.) with certificate reference.  
**Score 1**: Comparator regulatory status mentioned but no evidence provided.  
**Score 0**: Comparator regulatory status not addressed.

### Dimension 9c — Comparator Evidence Base
**Score 2**: Comparator has published clinical evidence referenced with citations.  
**Score 1**: Comparator evidence mentioned generally without specific citations.  
**Score 0**: No comparator evidence referenced.

### Dimension 9d — Comparator Appropriateness [HUMAN JUDGMENT REQUIRED]
**LEFT BLANK BY AI.** Human reviewer assesses: Is the chosen comparator appropriate for the device under evaluation? Do indications, technology, and patient population match?

### Dimension 10 — Learning Curve Accounting
**Score 2**: PMCF plan explicitly addresses learning curve effects (e.g., separate analysis for first N cases per center, training requirements documented).  
**Score 1**: Training mentioned but no learning curve analysis planned.  
**Score 0**: No mention of learning curve or training in PMCF context.

### Dimension 11 — Subgroup Analysis Plan
**Score 2**: PMCF plan specifies subgroup analyses (age, sex, comorbidity, indication severity) with rationale.  
**Score 1**: Subgroups mentioned but no analysis plan.  
**Score 0**: No subgroup consideration.

### Dimension 12 — PMCF-CER Feedback Specificity
**Score 2**: PMCF plan describes how findings will feed back into CER updates, with specific triggers (e.g., "if adverse event rate exceeds X, CER §5 will be updated").  
**Score 1**: Generic statement that PMCF will inform CER.  
**Score 0**: No feedback mechanism described.

### Dimension 13 — Cross-Document PMCF Integration
**Score 2**: PMCF plan references CER gaps, PSUR reporting schedule, and RMF residual risks — demonstrating cross-document integration.  
**Score 1**: References 1-2 of the three (CER/PSUR/RMF).  
**Score 0**: No cross-document integration; PMCF plan is isolated.

---

## PMCF Dimension Summary Output

```json
{
  "pmcf_dimension_profile": {
    "ai_scored": {
      "dim1_data_source_type": 0,
      "dim2_sample_size": 0,
      "dim3_timeline": 0,
      "dim4_cer_gap_coverage": 0,
      "dim5_class_proportionality": 0,
      "dim6_study_design": 0,
      "dim7a_endpoint_type": 0,
      "dim7b_objectively_measurable": 0,
      "dim8_follow_up_vs_benchmark": 0,
      "dim9a_comparator_name": 0,
      "dim9b_comparator_regulatory": 0,
      "dim9c_comparator_evidence": 0,
      "dim10_learning_curve": 0,
      "dim11_subgroup_analysis": 0,
      "dim12_pmcf_cer_feedback": 0,
      "dim13_cross_document_integration": 0
    },
    "human_required": {
      "dim7c_endpoint_clinical_meaningfulness": "[HUMAN JUDGMENT REQUIRED]",
      "dim9d_comparator_appropriateness": "[HUMAN JUDGMENT REQUIRED]"
    },
    "ai_total": "X/26 (13 dimensions × max 2 points each, AI only)",
    "overall_assessment": "AI has scored 13 dimensions. 2 dimensions (7c, 9d) require human clinical judgment. Final PMCF adequacy determination is HUMAN."
  }
}
```
