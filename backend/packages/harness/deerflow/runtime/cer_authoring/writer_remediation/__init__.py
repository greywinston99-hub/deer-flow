"""CER Writer Remediation — Gates and quarantine routing.

W1: Gate 1 (Device Domain Consistency) + Gate 3 (Evidence-Conclusion Consistency)
W2: Gate 2 (IFU Consumption) + Gate 4 (Body Cleanliness)
W3: Gate 5 (QA Gate Hardening)
W4: Release/Quarantine Routing + Regression Fixtures
"""

from .writer_gates import (
    evaluate_device_domain_consistency_gate,
    evaluate_evidence_conclusion_gate,
    evaluate_ifu_consumption_gate,
    evaluate_body_cleanliness_gate,
    evaluate_remediated_qa_gate,
    run_all_writer_gates,
)
from .quarantine import route_to_quarantine, write_failed_gate_report, update_rejection_ledger

__all__ = [
    "evaluate_device_domain_consistency_gate",
    "evaluate_evidence_conclusion_gate",
    "evaluate_ifu_consumption_gate",
    "evaluate_body_cleanliness_gate",
    "evaluate_remediated_qa_gate",
    "run_all_writer_gates",
    "route_to_quarantine",
    "write_failed_gate_report",
    "update_rejection_ledger",
]
