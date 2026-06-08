# V4 — Strategy-Specific CER Blueprints

**Purpose:** Define CER argument structure, evidence requirements, Writer constraints, NB challenge responses, and minimum argument to pass for each strategy route.
**Format per blueprint:** `minimum_argument_to_pass` | `hard_fail_shortcuts` | `allowed_claim_strength` | `required_human_gate` | `NB challenge responses` (system answer + regulatory basis + evidence basis + limitation).

---

## Blueprint 1 — WET CER

**适用条件：** WET 6 条件全部满足。

**CER 论证结构：**
- §3 SOTA：证明技术成熟、SOTA 稳定
- §4 等效性：通常不需要（WET 本身是 well-known）
- §5 临床数据：PMS/PMCF 数据为主，文献为辅
- §6 综合：PMS 数据证明持续安全性
- §7 BR：低风险 + 充分 PMS → favorable

**必须 evidence：** PMS data ≥ 2-3 years, complaint/vigilance trend, SOTA literature confirming stability
**可接受 evidence：** Literature review (non-systematic), clinical experience reports
**不可接受 shortcut：** WET 声明无 PMS 数据支撑
**PMCF role：** Routine surveillance
**BR/GSPR focus：** Low risk + stable performance history
**Writer tone：** Factual, moderate. Avoid "demonstrates superiority" — WET is about "established safety and performance"
**NB likely questions：** Why WET? Evidence of technology stability? PMS data coverage? SOTA unchanged?

---

## Blueprint 2 — Legacy Device CER

**适用条件：** Device previously CE-marked under MDD/AIMDD.

**CER 论证结构：**
- §3 SOTA：对比 MDD-era 和 MDR-era 的 SOTA 变化
- §4 等效性：通常不需要
- §5 临床数据：Pre-MDR clinical data + post-market PMS/PMCF
- §6 综合：Gap analysis MDD→MDR requirements
- §7 BR：PMS 数据 + legacy data 证明持续 acceptable

**必须 evidence：** Pre-MDR clinical data, PMS/PMCF data since market introduction, safety signal review
**可接受 evidence：** Published literature on same device type, clinical experience
**不可接受 shortcut：** Legacy = automatically MDR-sufficient
**PMCF role：** Enhanced if safety signals or SOTA changes
**BR/GSPR focus：** Continued safety, no new risks emerged
**Writer tone：** "Continued safety and performance demonstrated through post-market surveillance"
**NB likely questions：** Gap analysis MDD→MDR? PMS data since introduction? Any new safety signals?

---

## Blueprint 3 — Own-Data-Primary CER

**适用条件：** Manufacturer holds substantial own clinical data.

**CER 论证结构：**
- §3 SOTA：文献提供 context，own data 是核心
- §4 等效性：如适用
- §5 临床数据：Own clinical investigation/PMS/PMCF 数据为主
- §6 综合：Own data quality assessment + external literature 对比
- §7 BR：Own data 支撑 BR analysis

**必须 evidence：** Clinical investigation report, PMS/PMCF data, complaints/vigilance analysis, data quality self-assessment
**可接受 evidence：** External SOTA literature, comparator benchmarks
**不可接受 shortcut：** Own data without quality assessment
**PMCF role：** Ongoing surveillance + specific gap closure
**BR/GSPR focus：** Own data sufficiency + external validation
**Writer tone：** "Supported by manufacturer's clinical data from [N] patients"
**NB likely questions：** Data quality? Representativeness? External validation?

---

## Blueprint 4 — Equivalence CER

**适用条件：** Equivalent device identified + data access confirmed.

**CER 论证结构：**
- §3 SOTA：Context for subject and equivalent device
- §4 等效性：FULL 3-dim comparison (technical/biological/clinical)
- §5 临床数据：Equivalent device clinical data primary; subject device PMS/PMCF
- §6 综合：Differences impact analysis
- §7 BR：Equivalent data + subject-specific risk analysis

**必须 evidence：** 3-dim comparison table, data access contract evidence, equivalent device clinical evidence, differences impact analysis
**可接受 evidence：** Subject device PMS, comparator benchmarks
**不可接受 shortcut：** Equivalence without data access, equivalent evidence as direct proof without limitation
**PMCF role：** Confirm equivalence assumptions in clinical use
**BR/GSPR focus：** Residual differences do not impact safety/performance
**Writer tone：** "Equivalence demonstrated... Equivalent device data supports..."
**NB likely questions：** Data access proven? Differences impact? 3-dim complete?

---

## Blueprint 5 — Literature-Primary CER

**适用条件：** No equivalent, no substantial own data, no WET claim.

**CER 论证结构：**
- §3 SOTA：Comprehensive systematic literature review
- §4 等效性：Equivalence NOT claimed — non-equivalence path
- §5 临床数据：Literature-derived clinical evidence + pre-clinical data
- §6 综合：Literature quality assessment + SOTA comparison
- §7 BR：Literature evidence + own pre-clinical + PMCF plan

**必须 evidence：** Systematic literature review with PRISMA, SOTA benchmark derivation, own pre-clinical data, PMCF plan
**可接受 evidence：** Clinical experience reports, expert consensus
**不可接受 shortcut：** Selective citation, missing comparator benchmark
**PMCF role：** Critical — PMCF to close literature gaps
**BR/GSPR focus：** Literature-justified benefit + PMCF-mitigated residual risk
**Writer tone：** "Published clinical evidence supports... PMCF will address residual uncertainty"
**NB likely questions：** Systematic search? Benchmark comparison? PMCF plan credible?

---

## Blueprint 6 — Innovation / Insufficient Evidence CER

**适用条件：** Novel device or evidence insufficient for positive conclusion.

**CER 论证结构：**
- §3 SOTA：Identify evidence gap compared to established therapies
- §4 等效性：Not applicable
- §5 临床数据：Pre-clinical + feasibility/early clinical + analogous technology literature
- §6 综合：Clear gap identification → clinical investigation recommended
- §7 BR：Pre-clinical promise + clinical investigation justification

**必须 evidence：** Pre-clinical data, analogous technology literature, clinical investigation plan, PMCF plan
**可接受 evidence：** Expert opinion, feasibility data
**不可接受 shortcut：** Writing a positive conclusion without clinical data, PMCF as rescue for unsupported claim
**PMCF role：** May be part of clinical investigation follow-up
**BR/GSPR focus：** Pre-clinical safety + clinical investigation design justification
**Writer tone：** "Pre-clinical evidence suggests... Clinical investigation is required to confirm... PMCF will..."
**NB likely questions：** Clinical investigation design? PMCF plan? When will clinical data be available?

---

## Blueprint Summary: Route Constraints

| Route | Minimum Argument to Pass | Hard Fail Shortcuts | Allowed Claim Strength | Required Human Gate |
|:---|:---|:---|:---|:---|
| WET | 6-condition check all met + PMS data review | WET without PMS; WET for implantable without justification | moderate (no "demonstrates") | WET borderline (Class IIb+) |
| Legacy | Gap analysis MDD→MDR + PMS since intro | Legacy = automatic sufficient; no PMS review | moderate | PMS data insufficient or safety signals |
| Own-Data | Data quality score ≥ moderate + external validation | Own data without quality assessment | up to strong (if quality high) | Data quality concern flagged |
| Equivalence | 3-dim comparison + data access + impact analysis | Equivalence without data access | moderate ("based on equivalent device") | Data access uncertain or 3-dim borderline |
| Literature | Systematic search + SOTA benchmark + PMCF plan | Selective citation; missing comparator | limited to moderate | Evidence level < burden |
| Innovation | Pre-clinical + analogous lit + CI plan | Positive conclusion without clinical data | limited or not_supported | CI design review |

## NB Challenge Response Format

Each blueprint must provide pre-computed NB challenge responses:

```json
{
  "blueprint": "WET",
  "likely_NB_challenges": [
    {
      "question": "Why is this device considered well-established technology?",
      "system_answer": "All 6 WET conditions are met: [condition results]. PMS data from [N] years confirms...",
      "regulatory_basis": "MDR Article 61(6), MDCG 2020-6 §X",
      "evidence_basis": "PMS data [source]. SOTA literature [PMIDs]",
      "limitation": "WET classification is borderline due to [factor]. Human gate reviewed.",
      "trigger_for_rework": "If new safety signal emerges or SOTA changes significantly"
    }
  ]
}
```

**Rule:** NB_EXPLAINABILITY_PACKET must include per-blueprint NB challenge responses. These are not internal rationale — they are pre-computed answers to expected NB questions.

