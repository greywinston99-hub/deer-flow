"""Central model policy for the CER review production line."""

CER_REVIEW_DEFAULT_MODEL = "inherit"
CER_REVIEW_SIMPLE_MODEL = "kimi-k2.6-api"
CER_REVIEW_REASONING_MODEL = "kimi-k2.6-api"
CER_REVIEW_DEEPSEEK_CANDIDATE_MODEL = "deepseek-v4-pro"

CER_REVIEW_AGENT_MODEL_MAP = {
    # Structured / intake-oriented steps use the direct Kimi API path.
    "cer-intake-reviewer": CER_REVIEW_SIMPLE_MODEL,
    "cer-structure-compliance-reviewer": CER_REVIEW_SIMPLE_MODEL,
    "cer-intended-purpose-reviewer": CER_REVIEW_SIMPLE_MODEL,
    "cer-cep-methodology-reviewer": CER_REVIEW_SIMPLE_MODEL,
    "cer-ifu-sscp-label-reviewer": CER_REVIEW_SIMPLE_MODEL,
    "cer-cear-formatter-reviewer": CER_REVIEW_SIMPLE_MODEL,
    # Deep CER review / synthesis steps stay on the same direct Kimi API path.
    "cer-clinical-evidence-panel-reviewer": CER_REVIEW_REASONING_MODEL,
    "cer-qa-gate-reviewer": CER_REVIEW_REASONING_MODEL,
    "cer-human-boundary-reviewer": CER_REVIEW_REASONING_MODEL,
    "cer-gate-closure-reviewer": CER_REVIEW_REASONING_MODEL,
}


def get_cer_review_model_for_agent(agent_name: str) -> str:
    """Return the production model for a CER review subagent."""
    return CER_REVIEW_AGENT_MODEL_MAP.get(agent_name, CER_REVIEW_SIMPLE_MODEL)
