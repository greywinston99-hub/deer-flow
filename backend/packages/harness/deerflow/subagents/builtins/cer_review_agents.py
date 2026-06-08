"""CER Review — Specialized subagent configurations for D1 review pipeline.

Provides 10 subagent types corresponding to the CER 10-step review workflow:
intake -> structure_compliance -> intended_purpose -> cep_methodology
-> clinical_evidence_panel -> ifu_sscp_label -> qa_gate
-> cear_style_finding_formatter -> human_boundary -> gate_closure

Each subagent's system prompt is loaded from prompts/cer/canonical/*.md at import time
so that the prompt remains the single source of truth.
"""

from pathlib import Path

from deerflow.subagents.config import SubagentConfig
from deerflow.subagents.cer_review_model_policy import CER_REVIEW_DEFAULT_MODEL

# REPO_ROOT: deer-flow project root. parents[6] traverses
# builtins -> subagents -> deerflow -> harness -> packages -> backend -> deer-flow
REPO_ROOT = Path(__file__).resolve().parents[6]
_CANONICAL_PROMPTS = REPO_ROOT / "prompts" / "cer" / "canonical"


def _load_canonical_prompt(filename: str) -> str:
    """Load a CER canonical prompt at import time.

    Raises:
        FileNotFoundError: when the prompt file is absent. We fail loudly here
            so a missing prompt cannot silently degrade to an empty system prompt.
    """
    path = _CANONICAL_PROMPTS / filename
    if not path.exists():
        raise FileNotFoundError(f"CER canonical prompt missing: {path}")
    return path.read_text(encoding="utf-8")


_REVIEW_DISALLOWED = ["task", "ask_clarification", "present_files"]
_DEFAULT_TOOLS = ["read_file", "ls", "write_file", "str_replace"]
_TOOLS_WITH_BASH = _DEFAULT_TOOLS + ["bash"]


CER_INTAKE_REVIEWER_CONFIG = SubagentConfig(
    name="cer-intake-reviewer",
    description="""CER D1 step 1 — review the intake artifact for evidence-pack readiness.

Use this subagent when:
- Validating CER intake summary completeness against MDR 2017/745 evidence pack categories
- Confirming source-document inventory and per-document classification
- Surfacing intake-stage findings with source_ref linkage

Do NOT use for downstream structure / methodology / qa-gate work.""",
    system_prompt=_load_canonical_prompt("cer_intake_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)


CER_STRUCTURE_COMPLIANCE_REVIEWER_CONFIG = SubagentConfig(
    name="cer-structure-compliance-reviewer",
    description="""CER D1 step 2 — review CER document structure compliance against MEDDEV 2.7/1 Rev 4 and MDR Annex XIV.

Use this subagent when:
- Checking presence of mandated CER sections (executive summary, scope, methodology, evidence appraisal, conclusion, references)
- Identifying structural gaps or out-of-order sections
- Reporting blocking vs advisory structure findings""",
    system_prompt=_load_canonical_prompt("cer_structure_compliance_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)


CER_INTENDED_PURPOSE_REVIEWER_CONFIG = SubagentConfig(
    name="cer-intended-purpose-reviewer",
    description="""CER D1 step 3 — review intended-purpose statement consistency across CER, IFU, SSCP, and TD.

Use this subagent when:
- Comparing intended-purpose claims between core regulatory documents
- Checking risk classification consistency
- Flagging contradictions in target population, indications, or contraindications""",
    system_prompt=_load_canonical_prompt("cer_intended_purpose_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)


CER_CEP_METHODOLOGY_REVIEWER_CONFIG = SubagentConfig(
    name="cer-cep-methodology-reviewer",
    description="""CER D1 step 4 — review Clinical Evaluation Plan methodology rigor.

Use this subagent when:
- Validating CEP search strategy, inclusion/exclusion criteria, and appraisal grid
- Checking PMS/PMCF integration into CEP
- Identifying methodology gaps blocking evidence appraisal

bash tool is enabled to allow grep/wc helpers when scanning the CEP for keyword-by-section
audits (this is mechanical text inspection, not review judgment).""",
    system_prompt=_load_canonical_prompt("cer_cep_methodology_agent.md"),
    tools=_TOOLS_WITH_BASH,
    disallowed_tools=_REVIEW_DISALLOWED,
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)


CER_CLINICAL_EVIDENCE_PANEL_REVIEWER_CONFIG = SubagentConfig(
    name="cer-clinical-evidence-panel-reviewer",
    description="""CER D1 step 5 — review the clinical evidence panel across 5 lanes:
sota / clinical_evidence_adequacy / equivalence / pms_pmcf / benefit_risk.

Use this subagent when:
- Assessing state-of-the-art literature coverage
- Evaluating clinical-evidence adequacy for each indication
- Checking equivalence demonstration if claimed
- Reviewing PMS/PMCF data integration
- Producing benefit-risk lane findings (single subagent emits all 5 lanes)""",
    system_prompt=_load_canonical_prompt("cer_clinical_evidence_panel_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)


CER_IFU_SSCP_LABEL_REVIEWER_CONFIG = SubagentConfig(
    name="cer-ifu-sscp-label-reviewer",
    description="""CER D1 step 6 — review IFU, SSCP, and labeling for clinical-evidence backing.

Use this subagent when:
- Confirming IFU claims trace to clinical evidence
- Validating SSCP content against MDR Article 32
- Checking label/marketing claims for over-reach""",
    system_prompt=_load_canonical_prompt("cer_ifu_sscp_label_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)


CER_QA_GATE_REVIEWER_CONFIG = SubagentConfig(
    name="cer-qa-gate-reviewer",
    description="""CER D1 step 7 — aggregate QA gate review (cross-domain conflicts included).

Use this subagent when:
- Aggregating findings from steps 1-6 into a gate decision
- Detecting cross-domain conflicts (CER<->RMF<->IFU<->SSCP) — this responsibility was
  consolidated into qa-gate (no separate cross-domain detector exists)
- Producing gate recommendation with blocking/advisory severity""",
    system_prompt=_load_canonical_prompt("cer_qa_gate_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)


CER_CEAR_FORMATTER_REVIEWER_CONFIG = SubagentConfig(
    name="cer-cear-formatter-reviewer",
    description="""CER D1 step 8 — format findings into CEAR-style normalized output.

Use this subagent when:
- Converting raw step findings into the CEAR finding template
- Ensuring source_ref, severity, action_required fields are populated
- Producing a single normalized findings.json""",
    system_prompt=_load_canonical_prompt("cer_cear_style_finding_formatter_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)


CER_HUMAN_BOUNDARY_REVIEWER_CONFIG = SubagentConfig(
    name="cer-human-boundary-reviewer",
    description="""CER D1 step 9 — surface human-decision boundary items.

Use this subagent when:
- Identifying items requiring human regulatory expert judgment
- Producing the human-review queue with reason and next action
- Distinguishing AI-assistive vs human-only decisions""",
    system_prompt=_load_canonical_prompt("cer_human_boundary_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)


CER_GATE_CLOSURE_REVIEWER_CONFIG = SubagentConfig(
    name="cer-gate-closure-reviewer",
    description="""CER D1 step 10 — produce the final gate closure report.

Use this subagent when:
- Aggregating all upstream findings, gate recommendations, and human decisions
- Producing the gate_closure_report.json artifact
- Stating the closure outcome with traceable reasoning""",
    system_prompt=_load_canonical_prompt("cer_gate_closure_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)


# ── V28 NEW: QMS Review Agent (Step 11) ──────────────────────────────────
CER_QMS_REVIEWER_CONFIG = SubagentConfig(
    name="cer-qms-reviewer",
    description="""CER V28 Step 11 — review QMS documentation completeness against ISO 13485.

Use this subagent when:
- Reviewing QMS audit NCR findings (DEKRA, BSI, TUV style)
- Checking ISO 13485 §4-§8 documentation completeness
- Validating PRRC qualification, design traceability, process validation records
- The CEP/IFU agents do not cover QMS procedural audit items

Do NOT use for clinical evidence or CER content review — this is QMS-only.""",
    system_prompt=_load_canonical_prompt("cer_qms_review_agent.md"),
    tools=[],  # JSON-only, no tools
    disallowed_tools=[],
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)


# ── V28 NEW: Admin Precheck LLM Agent ────────────────────────────────────
CER_ADMIN_PRECHECK_REVIEWER_CONFIG = SubagentConfig(
    name="cer-admin-precheck-reviewer",
    description="""CER V28 Admin Pre-Check — deep LLM review of document administrative completeness.

Use this subagent when:
- Regex-based admin_pre_check.py returned WARNING/FAIL
- Need to distinguish real signature blocks from template boilerplate
- Need to validate certificate reference traceability beyond pattern matching
- Need to check version consistency in prose that regex can't parse

This agent supplements deterministic regex checks with reading comprehension.
Output is JSON-only — no tools, no file writes.""",
    system_prompt=_load_canonical_prompt("cer_admin_precheck_agent.md"),
    tools=[],  # JSON-only, read-only
    disallowed_tools=[],
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=30,
    timeout_seconds=600,
)


__all__ = [
    "CER_INTAKE_REVIEWER_CONFIG",
    "CER_STRUCTURE_COMPLIANCE_REVIEWER_CONFIG",
    "CER_INTENDED_PURPOSE_REVIEWER_CONFIG",
    "CER_CEP_METHODOLOGY_REVIEWER_CONFIG",
    "CER_CLINICAL_EVIDENCE_PANEL_REVIEWER_CONFIG",
    "CER_IFU_SSCP_LABEL_REVIEWER_CONFIG",
    "CER_QA_GATE_REVIEWER_CONFIG",
    "CER_CEAR_FORMATTER_REVIEWER_CONFIG",
    "CER_HUMAN_BOUNDARY_REVIEWER_CONFIG",
    "CER_GATE_CLOSURE_REVIEWER_CONFIG",
    "CER_QMS_REVIEWER_CONFIG",
    "CER_ADMIN_PRECHECK_REVIEWER_CONFIG",
]
