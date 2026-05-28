"""Minimal SharedReviewState — structured state passed between workflow stages.

JSON-serializable dataclass that accumulates findings, severity signals,
human gate items, and pipeline limitations as agents execute sequentially.

V1 handoff mechanism: prompt injection (state serialized as JSON in task_prompt).
"""

from dataclasses import dataclass, field, asdict


@dataclass
class SharedReviewState:
    """State passed between review-assist workflow stages.

    Each agent reads from contracted input fields and writes to contracted
    output fields. State is serialized to JSON for prompt injection (V1).
    """

    # ── Project identity ──────────────────────────────────
    project_profile: dict = field(default_factory=dict)

    # ── Source inventory (Stage 1 output) ─────────────────
    source_inventory: list[dict] = field(default_factory=list)
    # Each entry: {path, doc_type, evidence_pack, evidence_depth,
    #              external_dependency_status, pipeline_limitation,
    #              file_size_bytes, exists}

    # ── Candidate findings (accumulated across stages) ────
    candidate_findings: list[dict] = field(default_factory=list)
    # Each entry: {finding_id, stage_id, agent_name, type, subtype,
    #              severity, source_ref, excerpt, evidence_confidence,
    #              evidence_depth, human_gate_flag, calibration_rule_ref,
    #              rationale, reviewer_decision}

    # ── Severity signals ──────────────────────────────────
    severity_signals: list[dict] = field(default_factory=list)
    # Each entry: {finding_id, signal_type, severity,
    #              calibration_rule_ref, rationale}

    # ── Human gate queue ──────────────────────────────────
    human_gate_items: list[dict] = field(default_factory=list)
    # Each entry: {finding_id, reason, triggered_by,
    #              auto_route, gate_decision}

    # ── Pipeline limitations (informational only) ─────────
    pipeline_limitations: list[dict] = field(default_factory=list)
    # Each entry: {description, affected_files, limitation_type}

    # ── Artifact index ────────────────────────────────────
    artifact_index: list[str] = field(default_factory=list)

    # ── Run metadata ──────────────────────────────────────
    run_id: str = ""
    workflow_version: str = "1.1"

    # ── Serialization ─────────────────────────────────────

    def to_json(self) -> str:
        import json
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "SharedReviewState":
        import json
        data = json.loads(json_str)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    # ── Read/write by contract ───────────────────────────

    def read_fields(self, fields: list[str]) -> dict:
        """Return only the fields listed in the contract."""
        return {f: getattr(self, f) for f in fields if hasattr(self, f)}

    def write_fields(self, updates: dict) -> None:
        """Merge updates into state fields."""
        for field_name, value in updates.items():
            if hasattr(self, field_name):
                current = getattr(self, field_name)
                if isinstance(current, list) and isinstance(value, list):
                    current.extend(value)
                elif isinstance(current, dict) and isinstance(value, dict):
                    current.update(value)
                else:
                    setattr(self, field_name, value)
