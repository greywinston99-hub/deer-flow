"""DomainAgentSpec — minimal spec that compiles to SubagentConfig.

Defines a domain agent with structured calibration references, policies,
and state contracts. The compile() method produces a standard SubagentConfig
with enhanced system_prompt — without modifying SubagentConfig class.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deerflow.agent_capability.rule_registry import RuleRegistry


@dataclass
class DomainAgentSpec:
    """Minimal specification for a domain-aware review agent.

    Compiles to a standard SubagentConfig with calibration rules, evidence
    policy, severity policy, human gate policy, and state contracts injected
    into the system_prompt at compile time.
    """

    # ── Identity ──────────────────────────────────────────
    name: str
    role: str
    description: str
    task_modes: list[str] = field(default_factory=lambda: ["review"])

    # ── Base prompt ───────────────────────────────────────
    system_prompt_base: str = ""

    # ── Tool config (maps 1:1 to SubagentConfig) ─────────
    tools: list[str] | None = None
    disallowed_tools: list[str] | None = None
    model: str = "deepseek-v4-pro"
    max_turns: int = 50
    timeout_seconds: int = 900

    # ── Track C calibration refs ──────────────────────────
    track_c_refs: list[str] = field(default_factory=list)
    rule_registry_refs: list[str] = field(default_factory=list)

    # ── Structured policies ───────────────────────────────
    evidence_policy: dict = field(default_factory=lambda: {
        "required_depth": "PRIMARY",
        "allow_synthetic": False,
        "allow_indirect_with_flag": True,
    })
    severity_policy: dict = field(default_factory=lambda: {
        "can_signal": True,
        "can_adjudicate": False,
        "must_route_critical_to_human": True,
    })
    human_gate_policy: dict = field(default_factory=lambda: {
        "auto_route_conditions": ["severity==CRITICAL", "evidence_confidence!=DIRECT"],
        "auto_pass_conditions": ["severity==LOW", "evidence_confidence==DIRECT"],
    })

    # ── Output contract ───────────────────────────────────
    output_schema: str = ""
    state_input_contract: list[str] = field(default_factory=list)
    state_output_contract: list[str] = field(default_factory=list)

    def compile_to_subagent_config(
        self,
        rule_registry: "RuleRegistry | None" = None,
    ):
        """Compile this spec into a standard SubagentConfig.

        The returned SubagentConfig has an enhanced system_prompt with:
        - Calibration rules from RuleRegistry
        - Evidence policy
        - Severity policy
        - Human gate policy
        - Output schema contract
        - State read/write contracts
        - Advisory Only boundary

        Does NOT modify SubagentConfig class. Returns a new instance.
        Uses lazy import to avoid circular import chain.
        """
        import json
        from pathlib import Path

        # ── Lazy import SubagentConfig to avoid circular imports ──
        from deerflow.subagents.config import SubagentConfig

        # ── Resolve base prompt ───────────────────────────
        prompt = self.system_prompt_base
        if prompt.startswith("@"):
            prompt = Path(prompt[1:]).read_text(encoding="utf-8")

        sections: list[str] = []

        # ── Section 1: Base Role ──────────────────────────
        sections.append("=== Base Role ===")
        sections.append(prompt)

        # ── Section 2: Track C Rule Slice ──────────────────
        if self.rule_registry_refs and rule_registry:
            rules_text = rule_registry.get_agent_rule_slice(self.rule_registry_refs)
            if rules_text:
                sections.append("=== Track C Rule Slice ===")
                sections.append(rules_text)

        # ── Section 3: Evidence Policy ────────────────────
        sections.append("=== Evidence Policy ===")
        sections.append(json.dumps(self.evidence_policy, indent=2))

        # ── Section 4: Severity Policy ────────────────────
        sections.append("=== Severity Policy ===")
        sections.append(json.dumps(self.severity_policy, indent=2))

        # ── Section 5: Human Gate Policy ──────────────────
        sections.append("=== Human Gate Policy ===")
        sections.append(json.dumps(self.human_gate_policy, indent=2))

        # ── Section 6: Output Schema Contract ─────────────
        sections.append("=== Output Schema Contract ===")
        if self.output_schema:
            sections.append(
                f"Your JSON output MUST conform to schema: `{self.output_schema}`."
            )
        else:
            sections.append("Output a single JSON object with your findings.")

        # ── Section 7: State Read/Write Contract ──────────
        sections.append("=== State Read/Write Contract ===")
        if self.state_input_contract:
            sections.append(
                "READ from SharedReviewState: "
                + ", ".join(self.state_input_contract)
            )
        if self.state_output_contract:
            sections.append(
                "WRITE to SharedReviewState: "
                + ", ".join(self.state_output_contract)
            )
            sections.append(
                "Include `state_output` in your JSON response with these fields."
            )

        # ── Section 8: Advisory Only Boundary ─────────────
        sections.append("=== Advisory Only Boundary ===")
        sections.append(
            "ADVISORY OUTPUT ONLY — NOT A REGULATORY DECISION. "
            "All findings require human review. "
            "No terminal PASS/FAIL/APPROVED/REJECTED verdicts. "
            "reviewer_decision must remain PENDING."
        )

        enhanced_prompt = "\n\n".join(sections)

        return SubagentConfig(
            name=self.name,
            description=self.description,
            system_prompt=enhanced_prompt,
            tools=self.tools,
            disallowed_tools=self.disallowed_tools,
            model=self.model,
            max_turns=self.max_turns,
            timeout_seconds=self.timeout_seconds,
        )
