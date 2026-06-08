"""RMF Review — Specialized subagent configurations for the RMF review pipeline.

Provides 7 RMF reviewer subagents covering the 8-stage RMF workflow
(rmf_fmea_precheck and rmf_precheck share rmf-precheck-reviewer with mode
distinguishing the two), plus 1 cross-domain CER<->RMF linkage reviewer.

8 stages mapped to 7 reviewers:
    1. rmf_intake          -> rmf-intake-reviewer
    2. rmf_parse_normalize -> rmf-parse-normalize-reviewer
    3. rmf_fmea_precheck   -> rmf-precheck-reviewer (mode=fmea)
    4. rmf_precheck        -> rmf-precheck-reviewer (mode=rmf)
    5. rmf_dimension_review-> rmf-dimension-reviewer (single call, 6 dims)
    6. rmf_human_boundary  -> rmf-human-boundary-reviewer
    7. rmf_final_report    -> rmf-report-reviewer
    8. rmf_gate_closure    -> rmf-gate-closure-reviewer

Plus optional cross-domain linkage:
    9. rmf-cer-linkage-reviewer (CER<->RMF benefit-risk consistency)
"""

from pathlib import Path

from deerflow.subagents.config import SubagentConfig

# REPO_ROOT: deer-flow project root.
REPO_ROOT = Path(__file__).resolve().parents[6]
_PROMPTS_ROOT = REPO_ROOT / "prompts"
_CER_INTEGRATION = REPO_ROOT / "prompts" / "cer" / "integration"


def _load_rmf_prompt(filename: str) -> str:
    """Load an RMF agent prompt from prompts/ root."""
    path = _PROMPTS_ROOT / filename
    if not path.exists():
        raise FileNotFoundError(f"RMF prompt missing: {path}")
    return path.read_text(encoding="utf-8")


def _load_integration_prompt(filename: str) -> str:
    """Load a CER integration prompt from prompts/cer/integration/."""
    path = _CER_INTEGRATION / filename
    if not path.exists():
        raise FileNotFoundError(f"Integration prompt missing: {path}")
    return path.read_text(encoding="utf-8")


_REVIEW_DISALLOWED = ["task", "ask_clarification", "present_files"]
_DEFAULT_TOOLS = ["read_file", "ls", "write_file", "str_replace"]
_TOOLS_WITH_BASH = _DEFAULT_TOOLS + ["bash"]


RMF_INTAKE_REVIEWER_CONFIG = SubagentConfig(
    name="rmf-intake-reviewer",
    description="""RMF stage 1 — review the RMF intake bundle for runnable readiness.

Use this subagent when:
- Validating that the core P0 RMF package (RMF, FMEA/Hazard Analysis, CER, IFU, TD, PMS/PMCF)
  is present and readable for one project under a fixed institution profile
- Producing run_manifest, input_inventory, and missing_items_report
- Distinguishing missing / present / present_but_unreadable for each required document""",
    system_prompt=_load_rmf_prompt("rmf_intake_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model="inherit",
    max_turns=50,
    timeout_seconds=900,
)


RMF_PARSE_NORMALIZE_REVIEWER_CONFIG = SubagentConfig(
    name="rmf-parse-normalize-reviewer",
    description="""RMF stage 2 — parse and normalize RMF / FMEA structured content.

Use this subagent when:
- Extracting risk entries, hazards, controls, and residual risks from RMF
- Normalizing FMEA tables (severity, occurrence, detectability, RPN)
- Producing rmf_normalized.json and fmea_normalized.json with structured entities

bash tool is enabled for mechanical text/table extraction (e.g. grep, wc) when scanning
the parsed content. The semantic normalization decisions remain LLM-driven.""",
    system_prompt=_load_rmf_prompt("rmf_parse_normalize_agent.md"),
    tools=_TOOLS_WITH_BASH,
    disallowed_tools=_REVIEW_DISALLOWED,
    model="inherit",
    max_turns=50,
    timeout_seconds=900,
)


RMF_PRECHECK_REVIEWER_CONFIG = SubagentConfig(
    name="rmf-precheck-reviewer",
    description="""RMF stages 3 and 4 — precheck FMEA (mode=fmea) and RMF (mode=rmf).

Use this subagent when:
- Mode 'fmea': checking FMEA / Hazard Analysis for severity scales, RPN logic, missing rows,
  contradictions in hazard/cause/effect chains
- Mode 'rmf': checking RMF risk register for benefit-risk balance statements, residual-risk
  acceptability links, and traceability to FMEA entries

The runner injects the active mode into the task prompt context so this subagent serves
both stages with one config. Output is a precheck_report.json scoped to the active mode.""",
    system_prompt=_load_rmf_prompt("rmf_precheck_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model="inherit",
    max_turns=50,
    timeout_seconds=900,
)


RMF_DIMENSION_REVIEWER_CONFIG = SubagentConfig(
    name="rmf-dimension-reviewer",
    description="""RMF stage 5 — single-call review producing all six RMF dimensions:
COMP (completeness), CORR (correctness), ADEQ (adequacy), TRAC (traceability),
CONS (consistency), ACPT (acceptability).

Use this subagent when:
- Producing dimension_assessment.json with status, findings[], evidence[] for each of 6 dims
- Cross-validating RMF against IFU / CER / TD / PMS-PMCF / FMEA inputs
- Surfacing acceptability concerns while marking human-judgment boundaries explicitly

This is a single invocation per RMF run — no per-dimension parallel calls.""",
    system_prompt=_load_rmf_prompt("rmf_dimension_review_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model="inherit",
    max_turns=50,
    timeout_seconds=900,
)


RMF_HUMAN_BOUNDARY_REVIEWER_CONFIG = SubagentConfig(
    name="rmf-human-boundary-reviewer",
    description="""RMF stage 6 — surface human-decision boundary items and produce a provisional gate.

Use this subagent when:
- Identifying RMF items that require human regulatory expert judgment
- Producing the human_review_queue.json with reason, severity, and recommended next action
- Producing provisional_gate_recommendation.json (advisory, not binding)""",
    system_prompt=_load_rmf_prompt("rmf_human_boundary_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model="inherit",
    max_turns=50,
    timeout_seconds=900,
)


RMF_REPORT_REVIEWER_CONFIG = SubagentConfig(
    name="rmf-report-reviewer",
    description="""RMF stage 7 — aggregate findings into the final RMF review report.

Use this subagent when:
- Aggregating per-stage findings, dimension assessment, and human-boundary items into final_report.json
- Producing dimension_summary, escalations[], boundaries[]
- Stating overall conclusions with traceable source_ref linkage""",
    system_prompt=_load_rmf_prompt("rmf_report_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model="inherit",
    max_turns=50,
    timeout_seconds=900,
)


RMF_GATE_CLOSURE_REVIEWER_CONFIG = SubagentConfig(
    name="rmf-gate-closure-reviewer",
    description="""RMF stage 8 — produce the gate closure report after human gate decision.

Use this subagent when:
- A human_gate_decision.json is present and the closure stage is authorized
- Producing gate_closure_report.json that aggregates the human decision, prior findings,
  and final closure outcome with traceable reasoning

This subagent must NEVER fabricate a simulated reviewer decision — closure may only be
performed when a real human_gate_decision.json exists. The runner enforces this guard.""",
    system_prompt=_load_rmf_prompt("rmf_gate_closure_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model="inherit",
    max_turns=50,
    timeout_seconds=900,
)


RMF_CER_LINKAGE_REVIEWER_CONFIG = SubagentConfig(
    name="rmf-cer-linkage-reviewer",
    description="""Cross-domain reviewer — CER<->RMF benefit-risk linkage consistency.

Use this subagent when:
- Validating that CER's benefit-risk conclusions reference RMF residual-risk decisions
- Checking that RMF's acceptability statements align with CER's clinical evidence
- Flagging cross-document contradictions material to either domain's gate decision

Optionally invoked at the closure stage for either CER or RMF when both domains are in scope.""",
    system_prompt=_load_integration_prompt("rmf_cer_linkage_agent.md"),
    tools=_DEFAULT_TOOLS,
    disallowed_tools=_REVIEW_DISALLOWED,
    model="inherit",
    max_turns=50,
    timeout_seconds=900,
)


__all__ = [
    "RMF_INTAKE_REVIEWER_CONFIG",
    "RMF_PARSE_NORMALIZE_REVIEWER_CONFIG",
    "RMF_PRECHECK_REVIEWER_CONFIG",
    "RMF_DIMENSION_REVIEWER_CONFIG",
    "RMF_HUMAN_BOUNDARY_REVIEWER_CONFIG",
    "RMF_REPORT_REVIEWER_CONFIG",
    "RMF_GATE_CLOSURE_REVIEWER_CONFIG",
    "RMF_CER_LINKAGE_REVIEWER_CONFIG",
]
