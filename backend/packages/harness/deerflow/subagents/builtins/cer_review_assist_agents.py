"""CER Review Assist — Smoke agent registration.

DomainAgentSpec-built SubagentConfig for evidence-artifact-curator-smoke.
Compiled with Track C calibration rules injected at module load time.

If Track C calibration pack cannot be loaded, the agent is still registered
but without calibration rules — the import is non-fatal to avoid breaking
existing BUILTIN_SUBAGENTS importability.
"""

import logging
from pathlib import Path

from deerflow.agent_capability.domain_agent_spec import DomainAgentSpec
from deerflow.agent_capability.rule_registry import RuleRegistry
from deerflow.subagents.cer_review_model_policy import CER_REVIEW_DEFAULT_MODEL

logger = logging.getLogger(__name__)

# ── Track C calibration pack path ────────────────────────
_CALIBRATION_PACK_PATH = Path(
    "/Users/winstonwei/CER-RAG/00_knowledge_extraction_build/"
    "track_c_consolidation_v5/TRACK_C_CALIBRATION_PACK_V5.json"
)

# ── Load RuleRegistry (non-fatal on failure) ─────────────
_rule_registry: RuleRegistry | None = None
try:
    _rr = RuleRegistry()
    _rr.load(_CALIBRATION_PACK_PATH)
    _rule_registry = _rr
    logger.info(
        "Loaded %d rules from Track C V5 for review-assist agents",
        _rr.rule_count(),
    )
except Exception as exc:
    logger.warning(
        "Could not load Track C calibration pack from %s: %s. "
        "Smoke agent will be registered without calibration rules.",
        _CALIBRATION_PACK_PATH,
        exc,
    )

# ── Smoke Agent Spec ─────────────────────────────────────

_EVIDENCE_CURATOR_SMOKE_SPEC = DomainAgentSpec(
    name="evidence-artifact-curator-smoke",
    role="evidence_artifact_curator",
    description=(
        "Smoke test agent: source inventory, evidence readiness check, "
        "evidence depth classification (PRIMARY/SECONDARY/INDIRECT), "
        "synthetic summary detection, pipeline limitation flagging. "
        "Advisory output only — no terminal verdicts."
    ),
    task_modes=["review"],
    system_prompt_base=(
        "@"
        + str(
            Path(__file__).resolve().parents[6]
            / "prompts"
            / "cer"
            / "canonical"
            / "evidence_artifact_curator_smoke.md"
        )
    ),
    tools=["read_file", "ls", "write_file", "str_replace", "bash"],
    disallowed_tools=["task", "ask_clarification", "present_files"],
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
    rule_registry_refs=[
        "KA-CAL-AP-RPR-0001",  # empty_file_accepted_as_source
        "KA-CAL-AP-RPR-0004",  # synthetic_summary_instead_of_excerpt
        "KA-CAL-GS-RPR-0001",  # source_excerpt_fidelity
    ],
    evidence_policy={
        "required_depth": "PRIMARY",
        "allow_synthetic": False,
        "allow_indirect_with_flag": True,
    },
    severity_policy={
        "can_signal": True,
        "can_adjudicate": False,
        "must_route_critical_to_human": True,
    },
    human_gate_policy={
        "auto_route_conditions": [
            "synthetic_summary_detected",
            "empty_file_detected",
            "evidence_confidence!=DIRECT",
        ],
        "auto_pass_conditions": [
            "all_files_present",
            "all_evidence_primary",
            "no_synthetic_summaries",
        ],
    },
    output_schema="evidence_artifact_smoke",
    state_input_contract=[],
    state_output_contract=["source_inventory", "pipeline_limitations"],
)

# ── Compile to SubagentConfig ────────────────────────────

EVIDENCE_ARTIFACT_CURATOR_SMOKE_CONFIG = (
    _EVIDENCE_CURATOR_SMOKE_SPEC.compile_to_subagent_config(_rule_registry)
)

logger.info(
    "Compiled evidence-artifact-curator-smoke config: system_prompt=%d chars",
    len(EVIDENCE_ARTIFACT_CURATOR_SMOKE_CONFIG.system_prompt),
)
