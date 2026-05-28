"""DomainAgentBuilder — orchestrates DomainAgentSpec → SubagentConfig compilation.

Takes a DomainAgentSpec, RuleRegistry, and optional SharedReviewState metadata
and produces a valid SubagentConfig with Track C calibration injected into
the system_prompt. All DeerFlow imports are lazy to avoid circular import chain.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deerflow.agent_capability.domain_agent_spec import DomainAgentSpec
    from deerflow.agent_capability.rule_registry import RuleRegistry
    from deerflow.subagents.config import SubagentConfig

logger = logging.getLogger(__name__)


class DomainAgentBuilder:
    """Builds SubagentConfigs from DomainAgentSpecs with rule injection.

    Usage:
        registry = RuleRegistry("path/to/calibration_pack.json")
        spec = DomainAgentSpec(name="my-agent", role="reviewer", ...)
        config = DomainAgentBuilder(spec, registry).build()
        # config is now a standard SubagentConfig suitable for BUILTIN_SUBAGENTS
    """

    def __init__(
        self,
        spec: "DomainAgentSpec",
        rule_registry: "RuleRegistry | None" = None,
    ):
        self.spec = spec
        self.rule_registry = rule_registry

    def build(self) -> "SubagentConfig":
        """Compile the spec into a SubagentConfig.

        The system_prompt is enhanced with:
        1. Base role prompt
        2. Track C calibration rule slice
        3. Evidence policy
        4. Severity policy
        5. Human gate policy
        6. Output schema contract
        7. State read/write contract
        8. Advisory Only boundary
        """
        # Resolve base prompt
        prompt = self.spec.system_prompt_base
        if prompt.startswith("@"):
            prompt = Path(prompt[1:]).read_text(encoding="utf-8")

        sections: list[str] = []

        # 1. Base Role
        sections.append("=== Base Role ===")
        sections.append(prompt)

        # 2. Track C Rule Slice
        if self.spec.rule_registry_refs and self.rule_registry:
            rules_text = self.rule_registry.get_agent_rule_slice(
                self.spec.rule_registry_refs
            )
            if rules_text:
                sections.append("=== Track C Rule Slice ===")
                sections.append(rules_text)

        # 3-5. Policies
        import json

        sections.append("=== Evidence Policy ===")
        sections.append(json.dumps(self.spec.evidence_policy, indent=2))

        sections.append("=== Severity Policy ===")
        sections.append(json.dumps(self.spec.severity_policy, indent=2))

        sections.append("=== Human Gate Policy ===")
        sections.append(json.dumps(self.spec.human_gate_policy, indent=2))

        # 6. Output Schema Contract
        sections.append("=== Output Schema Contract ===")
        if self.spec.output_schema:
            sections.append(
                f"Output MUST conform to schema: {self.spec.output_schema}"
            )
        sections.append(
            "Emit a single JSON object (optionally wrapped in ```json fences). "
            "No prose outside the JSON payload."
        )

        # 7. State Read/Write Contract
        sections.append("=== State Read/Write Contract ===")
        if self.spec.state_input_contract:
            sections.append(
                "READ from SharedReviewState: "
                + ", ".join(self.spec.state_input_contract)
            )
        if self.spec.state_output_contract:
            sections.append(
                "WRITE to SharedReviewState: "
                + ", ".join(self.spec.state_output_contract)
            )
            sections.append(
                "Include a `state_output` key in your JSON response with: "
                + ", ".join(self.spec.state_output_contract)
            )

        # 8. Advisory Only Boundary
        sections.append("=== Advisory Only Boundary ===")
        sections.append(
            "ADVISORY OUTPUT ONLY — NOT A REGULATORY DECISION. "
            "No terminal PASS/FAIL/APPROVED/REJECTED verdicts. "
            "All reviewer_decision values must remain PENDING. "
            "All findings require human review before any regulatory use."
        )

        enhanced_prompt = "\n\n".join(sections)
        logger.info(
            "Built enhanced system_prompt for %s (%d chars, %d sections)",
            self.spec.name,
            len(enhanced_prompt),
            len(sections),
        )

        # Lazy import to avoid circular dependency
        from deerflow.subagents.config import SubagentConfig

        return SubagentConfig(
            name=self.spec.name,
            description=self.spec.description,
            system_prompt=enhanced_prompt,
            tools=self.spec.tools,
            disallowed_tools=self.spec.disallowed_tools,
            model=self.spec.model,
            max_turns=self.spec.max_turns,
            timeout_seconds=self.spec.timeout_seconds,
        )
