"""WS10: Regulatory Style Fingerprint and Body/Annex Release Gates.

Converts style feedback into measurable release controls.  Produces
`regulatory_style_fingerprint_report.json` with sentence/paragraph metrics,
GSPR paragraph completeness, literature appraisal structure, and body/annex
boundary checks.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


def _count_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


def _count_words(text: str) -> int:
    return len(text.split())


def _is_passive(sentence: str) -> bool:
    passive_patterns = [
        r'\b(is|are|was|were|be|been|being)\s+\w+ed\b',
        r'\b(is|are|was|were|be|been|being)\s+\w+en\b',
        r'\b(is|are|was|were|be|been|being)\s+\w+(?:ized|ified|ated)\b',
    ]
    return any(re.search(p, sentence, re.I) for p in passive_patterns)


def build_regulatory_style_fingerprint(
    cer_body_text: str = "",
    chapter_texts: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a regulatory style fingerprint for the CER body text.

    Checks:
    - Sentence length distribution by chapter
    - Passive voice ratio
    - GSPR paragraph completeness (requirement/evidence/reasoning/judgment)
    - Literature appraisal paragraph structure (source/method/result/relevance/quality/limitation)
    - Body vs annex boundary
    - Conclusion completeness
    """
    now = datetime.now(timezone.utc).isoformat()
    chapter_texts = chapter_texts or {"body": cer_body_text}
    sentences = _count_sentences(cer_body_text)
    total_sentences = len(sentences)
    total_words = _count_words(cer_body_text)

    sentence_lengths = [_count_words(s) for s in sentences]
    avg_sentence_length = round(sum(sentence_lengths) / total_sentences, 1) if total_sentences else 0

    passive_count = sum(1 for s in sentences if _is_passive(s))
    passive_ratio = round(passive_count / total_sentences, 3) if total_sentences else 0
    passive_in_range = 0.15 <= passive_ratio <= 0.25

    conclusion_sentences = _count_sentences(chapter_texts.get("conclusions") or chapter_texts.get("§5") or "")
    conclusion_lengths = [_count_words(s) for s in conclusion_sentences]
    conclusion_avg = round(sum(conclusion_lengths) / len(conclusion_sentences), 1) if conclusion_sentences else 0
    conclusion_under_20 = all(l <= 20 for l in conclusion_lengths) if conclusion_lengths else False

    long_sentences = [(i, l) for i, l in enumerate(sentence_lengths) if l > 32]
    very_long_sentences = [(i, l) for i, l in enumerate(sentence_lengths) if l > 40]

    gspr_completeness = _check_gspr_paragraphs(cer_body_text)
    lit_appraisal_completeness = _check_literature_appraisal(cer_body_text)
    conclusion_completeness = _check_conclusion_completeness(cer_body_text)
    body_annex_boundary = _check_body_annex_boundary(cer_body_text)

    all_checks_pass = (
        avg_sentence_length <= 32
        and passive_in_range
        and conclusion_under_20
        and gspr_completeness["status"] == "PASS"
        and lit_appraisal_completeness["status"] == "PASS"
        and conclusion_completeness["status"] == "PASS"
        and body_annex_boundary["status"] == "PASS"
    )

    return {
        "schema": "regulatory_style_fingerprint_v1",
        "generated_at": now,
        "metrics": {
            "total_sentences": total_sentences,
            "total_words": total_words,
            "avg_sentence_length": avg_sentence_length,
            "sentence_length_acceptable": avg_sentence_length <= 32,
            "conclusion_avg_sentence_length": conclusion_avg,
            "conclusion_under_20_words": conclusion_under_20,
            "passive_count": passive_count,
            "passive_ratio": passive_ratio,
            "passive_in_range_15_25_pct": passive_in_range,
            "long_sentences_over_32": len(long_sentences),
            "very_long_sentences_over_40": len(very_long_sentences),
        },
        "gspr_paragraphs": gspr_completeness,
        "literature_appraisal": lit_appraisal_completeness,
        "conclusion": conclusion_completeness,
        "body_annex_boundary": body_annex_boundary,
        "overall_status": "PASS" if all_checks_pass else "FAIL",
    }


def _check_gspr_paragraphs(text: str) -> dict[str, Any]:
    text_lower = text.lower()
    has_requirement = bool(re.search(r'gspr\s*\d+|general safety and performance requirement|article\s*\d+', text_lower))
    has_evidence_source = bool(re.search(r'(source|reference|study|literature|clinical data|bench test)', text_lower))
    has_evidence_summary = bool(re.search(r'(demonstrated|showed|indicated|confirmed|reported|found)', text_lower))
    has_reasoning = bool(re.search(r'(therefore|thus|accordingly|consequently|based on|it follows)', text_lower))
    text_flat = " ".join(text_lower.split())
    has_compliance_judgment = bool(re.search(r'(compliance|conformity|satisfied|fulfilled|meets the requirement|is met)', text_flat))
    all_present = all([has_requirement, has_evidence_source, has_evidence_summary, has_reasoning, has_compliance_judgment])
    return {
        "status": "PASS" if all_present else "FAIL",
        "has_requirement_statement": has_requirement,
        "has_evidence_source": has_evidence_source,
        "has_evidence_summary": has_evidence_summary,
        "has_reasoning": has_reasoning,
        "has_compliance_judgment": has_compliance_judgment,
        "missing": [k for k, v in {
            "requirement": has_requirement, "evidence_source": has_evidence_source,
            "evidence_summary": has_evidence_summary, "reasoning": has_reasoning,
            "compliance_judgment": has_compliance_judgment,
        }.items() if not v],
    }


def _check_literature_appraisal(text: str) -> dict[str, Any]:
    text_lower = text.lower()
    has_source = bool(re.search(r'(pubmed|study|article|publication|reference|trial)', text_lower))
    has_method = bool(re.search(r'(method|design|rct|cohort|case.control|prospective|retrospective)', text_lower))
    has_result = bool(re.search(r'(result|finding|outcome|endpoint|data show|reported)', text_lower))
    has_relevance = bool(re.search(r'(relevant|applicable|generalizable|appropriate|suitable)', text_lower))
    has_quality = bool(re.search(r'(quality|bias|limitation|confound|grade|jadad|newcastle.ottawa)', text_lower))
    has_limitation = bool(re.search(r'(limitation|weakness|caveat|caution|not generaliz|small sample)', text_lower))
    all_present = all([has_source, has_method, has_result, has_relevance, has_quality, has_limitation])
    return {
        "status": "PASS" if all_present else "FAIL",
        "has_source": has_source, "has_method": has_method, "has_result": has_result,
        "has_relevance": has_relevance, "has_quality": has_quality, "has_limitation": has_limitation,
        "missing": [k for k, v in {
            "source": has_source, "method": has_method, "result": has_result,
            "relevance": has_relevance, "quality": has_quality, "limitation": has_limitation,
        }.items() if not v],
    }


def _check_conclusion_completeness(text: str) -> dict[str, Any]:
    text_lower = text.lower()
    has_safety = bool(re.search(r'(safety|safe|adverse event|complication)', text_lower))
    has_performance = bool(re.search(r'(performance|efficacy|effectiveness|clinical benefit|outcome)', text_lower))
    has_benefit_risk = bool(re.search(r'(benefit.risk|risk.benefit|favourable.*profile)', text_lower))
    has_pms_pmcf = bool(re.search(r'(pms|pmcf|post.market|surveillance|follow.up)', text_lower))
    has_limitation = bool(re.search(r'(limitation|uncertainty|gap|insufficient|requires further|pending)', text_lower))
    all_present = all([has_safety, has_performance, has_benefit_risk, has_pms_pmcf, has_limitation])
    return {
        "status": "PASS" if all_present else "FAIL_WITH_GAPS",
        "has_safety_conclusion": has_safety, "has_performance_conclusion": has_performance,
        "has_benefit_risk_conclusion": has_benefit_risk, "has_pms_pmcf_limitation": has_pms_pmcf,
        "has_limitation_statement": has_limitation,
        "missing": [k for k, v in {
            "safety": has_safety, "performance": has_performance,
            "benefit_risk": has_benefit_risk, "pms_pmcf": has_pms_pmcf, "limitation": has_limitation,
        }.items() if not v],
    }


def _check_body_annex_boundary(text: str) -> dict[str, Any]:
    text_lower = text.lower()
    annex_reference_in_body = bool(re.search(r'(see annex|refer to annex|annex \w|appendix \w)', text_lower))
    body_only_reference = bool(re.search(r'(as shown in|as detailed in|as summarized in).{0,50}(annex|appendix|table \d)', text_lower))
    return {
        "status": "PASS",
        "annex_referenced_in_body": annex_reference_in_body,
        "body_only_references_without_narrative": body_only_reference,
        "warning": "Body contains table/annex references without standalone narrative reasoning" if body_only_reference and not annex_reference_in_body else "",
    }
