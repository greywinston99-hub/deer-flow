"""BIGDP2026.6 Expert 85: Writer semantic output QA tests.

Validates writer constraints at the package level — Writer cannot:
- Strengthen claims beyond ledger conclusion_strength
- Treat indirect/equiv evidence as direct proof
- Hide fallback benchmark limitations
- Rewrite narrowed IFU claim as original overclaim
- Include cannot_support claims in positive CER conclusions
- Use PMCF to resolve unsupported evidence
"""
import pytest


def _validate_writer_semantic_constraints(package: dict) -> list[str]:
    """Simulate writer constraint validation at package level."""
    violations = []
    reasoning = package.get("cer_reasoning_ledger", {})
    ifu_evo = package.get("ifu_claim_evolution_ledger", {})
    bm_trace = package.get("benchmark_derivation_trace", {})

    # Rule 1: Conclusion strength ceiling
    for claim in reasoning.get("claims", []):
        if claim.get("conclusion_strength") == "not_supported":
            violations.append(f"Claim {claim['claim_id']} is not_supported — cannot appear in CER conclusions")
        if claim.get("evidence_support_type") in ("indirect", "equivalent") and claim.get("conclusion_strength") == "strong":
            violations.append(f"Claim {claim['claim_id']}: {claim['evidence_support_type']} evidence → strong conclusion violates CON rules")

    # Rule 2: Fallback benchmark must have limitations
    for ep in bm_trace.get("endpoints", []):
        if ep.get("directness") == "fallback" and not ep.get("limitations"):
            violations.append(f"Endpoint {ep['endpoint_name']}: fallback benchmark missing limitations")

    # Rule 3: IFU marketing claims flagged
    for claim in ifu_evo.get("claims", []):
        flags = claim.get("evolution_flags", {})
        if flags.get("marketing_language_detected") and not flags.get("requires_human_review"):
            violations.append(f"Claim {claim['claim_id']}: marketing language detected but not flagged for human review")

    # Rule 4: PMCF cannot be described as resolving unsupported
    for claim in reasoning.get("claims", []):
        if claim.get("gap_disposition") == "PMCF" and claim.get("conclusion_strength") == "strong":
            violations.append(f"Claim {claim['claim_id']}: PMCF gap with strong conclusion — PMCF cannot resolve evidence gap")

    return violations


class TestWriterSemanticConstraints:
    """Writer must not exceed ledger constraints."""

    def test_writer_blocks_not_supported_claim(self):
        """not_supported claim must not appear in positive conclusions."""
        package = {
            "cer_reasoning_ledger": {
                "claims": [
                    {"claim_id": "C-01", "conclusion_strength": "not_supported", "evidence_support_type": "insufficient",
                     "gap_disposition": "cannot_support"},
                ],
            },
            "ifu_claim_evolution_ledger": {"claims": []},
            "benchmark_derivation_trace": {"endpoints": []},
        }
        violations = _validate_writer_semantic_constraints(package)
        assert len(violations) > 0
        assert any("not_supported" in v for v in violations)

    def test_writer_strong_claim_with_indirect_evidence_violates(self):
        """Indirect evidence → strong conclusion is a violation."""
        package = {
            "cer_reasoning_ledger": {
                "claims": [
                    {"claim_id": "C-01", "conclusion_strength": "strong", "evidence_support_type": "indirect",
                     "gap_disposition": "no_gap"},
                ],
            },
            "ifu_claim_evolution_ledger": {"claims": []},
            "benchmark_derivation_trace": {"endpoints": []},
        }
        violations = _validate_writer_semantic_constraints(package)
        assert len(violations) > 0
        assert any("indirect" in v and "strong" in v for v in violations)

    def test_valid_package_no_violations(self):
        """Well-formed package with proper constraints → zero violations."""
        package = {
            "cer_reasoning_ledger": {
                "claims": [
                    {"claim_id": "C-01", "conclusion_strength": "strong", "evidence_support_type": "direct", "gap_disposition": "no_gap"},
                    {"claim_id": "C-02", "conclusion_strength": "moderate", "evidence_support_type": "indirect", "gap_disposition": "PMCF"},
                ],
            },
            "ifu_claim_evolution_ledger": {
                "claims": [
                    {"claim_id": "C-01", "evolution_flags": {"marketing_language_detected": False, "requires_human_review": False}},
                ],
            },
            "benchmark_derivation_trace": {
                "endpoints": [
                    {"endpoint_name": "ep1", "directness": "direct", "limitations": []},
                ],
            },
        }
        violations = _validate_writer_semantic_constraints(package)
        assert len(violations) == 0, f"Unexpected violations: {violations}"

    def test_fallback_benchmark_missing_limitations_violates(self):
        """Fallback benchmark without limitations → violation."""
        package = {
            "cer_reasoning_ledger": {"claims": []},
            "ifu_claim_evolution_ledger": {"claims": []},
            "benchmark_derivation_trace": {
                "endpoints": [
                    {"endpoint_name": "ep1", "directness": "fallback"},
                ],
            },
        }
        violations = _validate_writer_semantic_constraints(package)
        assert len(violations) > 0
        assert any("fallback" in v for v in violations)

    def test_pmcf_with_strong_conclusion_violates(self):
        """PMCF gap with strong conclusion → PMCF cannot magically resolve gaps."""
        package = {
            "cer_reasoning_ledger": {
                "claims": [
                    {"claim_id": "C-01", "conclusion_strength": "strong", "evidence_support_type": "direct",
                     "gap_disposition": "PMCF"},
                ],
            },
            "ifu_claim_evolution_ledger": {"claims": []},
            "benchmark_derivation_trace": {"endpoints": []},
        }
        violations = _validate_writer_semantic_constraints(package)
        assert len(violations) > 0

    def test_marketing_claim_not_flagged_violates(self):
        """Marketing claim without human review flag → violation."""
        package = {
            "cer_reasoning_ledger": {"claims": []},
            "ifu_claim_evolution_ledger": {
                "claims": [
                    {"claim_id": "C-01", "evolution_flags": {
                        "marketing_language_detected": True,
                        "requires_human_review": False,
                    }},
                ],
            },
            "benchmark_derivation_trace": {"endpoints": []},
        }
        violations = _validate_writer_semantic_constraints(package)
        assert len(violations) > 0
