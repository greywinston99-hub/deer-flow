"""
V21 Statistical Context Evaluator — Deterministic computation, NOT LLM reasoning.
GS extracts numbers from claim text. This tool computes statistical context.
All functions return structured dicts, never natural language judgments.
"""

import re
from typing import Dict, Any, Optional, List

# EUDAMED 2023 Annual Report — Complaint Rates by Device Class
EUDAMED_BENCHMARKS = {
    "I":    {"rate": 1.25, "serious_rate": 0.2,  "label": "0.5-2 per 100 device-years"},
    "IIa":  {"rate": 2.0,  "serious_rate": 0.55, "label": "1-3 per 100 device-years"},
    "IIb":  {"rate": 3.5,  "serious_rate": 1.0,  "label": "2-5 per 100 device-years"},
    "III":  {"rate": 5.5,  "serious_rate": 2.0,  "label": "3-8 per 100 device-years"},
}

# MDCG 2020-7 PMCF Proportionality — Minimum Proactive Sources by Device Class
PMCF_PROPORTIONALITY = {
    "I":    {"min_proactive_sources": 0, "note": "PMS data may suffice"},
    "IIa":  {"min_proactive_sources": 1, "note": "≥1 proactive source"},
    "IIb":  {"min_proactive_sources": 2, "note": "≥2 proactive sources"},
    "III":  {"min_proactive_sources": 3, "note": "≥3 proactive sources (incl. ≥1 clinical investigation or registry)"},
}

# Sample size benchmarks by device class and claim type (MDCG 2020-6)
SAMPLE_SIZE_BENCHMARKS = {
    "safety_claim": {
        "I":    (30, 100),
        "IIa":  (50, 200),
        "IIb":  (100, 500),
        "III":  (200, 1000),
    },
    "performance_claim": {
        "I":    (15, 50),
        "IIa":  (30, 100),
        "IIb":  (50, 200),
        "III":  (100, 500),
    },
    "equivalence_justification": {
        "I":    (10, 30),
        "IIa":  (20, 60),
        "IIb":  (40, 120),
        "III":  (80, 300),
    },
}

# Methodology detection keywords
METHODOLOGY_PATTERNS = {
    "sample_size_justification": [
        r"sample\s*size\s*(calculation|justification|rationale|determination)",
        r"power\s*(analysis|calculation)",
        r"n\s*=\s*\d+",
        r"sample\s*size\s*(of|:)\s*\d+",
        r"样本量\s*(计算|估计|确定|:)\s*\d+",
    ],
    "statistical_test_named": [
        r"(t[\s-]test|chi[\s-]square|fisher[s']?\s*exact|wilcoxon|mann[\s-]whitney|kruskal[\s-]wallis)",
        r"(anova|ancova|log[\s-]rank|kaplan[\s-]meier|cox\s*regression|linear\s*regression|logistic\s*regression)",
        r"(meta[\s-]analysis|systematic\s*review|randomi[sz]ed\s*controlled\s*trial)",
        r"p\s*[<≤]\s*0\.\d+",
    ],
    "confidence_interval_reported": [
        r"(95%|99%|90%)\s*(CI|confidence\s*interval)",
        r"confidence\s*interval.*?(95%|99%|90%)",
        r"\[[\d.]+\s*[,;]\s*[\d.]+\].*?(CI|confidence)",
        r"置信区间",
    ],
    "p_value_reported": [
        r"p\s*[<≤=]\s*0\.\d+",
        r"p[\s-]*value\s*[<≤=]",
        r"P\s*[<≤=]\s*0\.\d+",
    ],
}


def evaluate_zero_events(events: int, device_years: float, device_class: str) -> Dict[str, Any]:
    """
    Rule of Three: 95% confidence upper bound for zero observed events.
    3/N gives the upper 95% confidence bound when zero events are observed in N device-years.

    Args:
        events: Number of events observed (must be 0 for Rule of Three)
        device_years: Total device-years of exposure
        device_class: Device class (I, IIa, IIb, III)

    Returns:
        Structured dict with upper bound, benchmark comparison, and methodology flags
    """
    if device_years <= 0:
        return {
            "error": "device_years must be > 0",
            "upper_bound": None,
            "benchmark_comparison": None,
        }

    benchmark = EUDAMED_BENCHMARKS.get(device_class, {})
    benchmark_rate = benchmark.get("rate", 0)
    expected_events = benchmark_rate * device_years / 100.0

    if events == 0:
        # Rule of Three: upper 95% confidence bound = 3 / N
        upper_bound = 3.0 / device_years
        upper_bound_per_100 = upper_bound * 100

        # Compare: is the upper bound below, at, or above the benchmark?
        if upper_bound_per_100 < benchmark_rate * 0.5:
            comparison = "upper_bound_below_benchmark"
            note = f"Even the worst case (upper bound {upper_bound_per_100:.1f}/100 device-years) is below the EUDAMED benchmark ({benchmark['label']}). Zero events is consistent with expected rates."
        elif upper_bound_per_100 < benchmark_rate * 1.5:
            comparison = "upper_bound_near_benchmark"
            note = f"Upper bound ({upper_bound_per_100:.1f}/100 device-years) is near the EUDAMED benchmark ({benchmark['label']}). Statistical validity of zero-event claim requires biostatistics expertise."
        else:
            comparison = "upper_bound_exceeds_benchmark"
            note = f"Upper bound ({upper_bound_per_100:.1f}/100 device-years) exceeds the EUDAMED benchmark ({benchmark['label']}). The device-years may be insufficient to rule out a rate consistent with the benchmark."
    else:
        upper_bound = None
        comparison = "events_observed"
        note = "Rule of Three applies only to zero events. Observed rate should be compared directly to benchmark."

    return {
        "events_observed": events,
        "device_years": device_years,
        "device_class": device_class,
        "upper_bound_per_100_device_years": round(upper_bound_per_100, 2) if upper_bound else None,
        "benchmark_rate_per_100_device_years": benchmark_rate,
        "benchmark_label": benchmark.get("label", "unknown"),
        "expected_events_at_benchmark_rate": round(expected_events, 2),
        "comparison": comparison,
        "note": note,
        "method": "Rule of Three (3/N) — 95% confidence upper bound for zero events",
        "human_verification_flag": "Statistical validity requires biostatistics expertise. AI provides context only.",
    }


def evaluate_sample_size(sample_size: int, device_class: str, claim_type: str) -> Dict[str, Any]:
    """
    Evaluate whether a claimed sample size is within typical benchmarks for the device class and claim type.

    Args:
        sample_size: Total sample size (N) claimed
        device_class: Device class (I, IIa, IIb, III)
        claim_type: Type of claim (safety_claim, performance_claim, equivalence_justification)

    Returns:
        Structured dict with benchmark range and position assessment
    """
    benchmarks = SAMPLE_SIZE_BENCHMARKS.get(claim_type, {})
    if not benchmarks:
        return {"error": f"Unknown claim_type: {claim_type}. Valid: {list(SAMPLE_SIZE_BENCHMARKS.keys())}"}

    bench_range = benchmarks.get(device_class)
    if not bench_range:
        return {"error": f"Unknown device_class: {device_class}. Valid: I, IIa, IIb, III"}

    low, high = bench_range

    if sample_size < low:
        position = "below_typical_range"
        note = f"Sample size {sample_size} is below the typical range for {claim_type} ({device_class}: {low}-{high})."
    elif sample_size <= high:
        position = "within_typical_range"
        note = f"Sample size {sample_size} is within the typical range for {claim_type} ({device_class}: {low}-{high})."
    else:
        position = "above_typical_range"
        note = f"Sample size {sample_size} is above the typical range for {claim_type} ({device_class}: {low}-{high})."

    return {
        "sample_size": sample_size,
        "device_class": device_class,
        "claim_type": claim_type,
        "benchmark_range": f"{low}-{high}",
        "position": position,
        "note": note,
        "source": "MDCG 2020-6 clinical evidence expectations",
        "human_verification_flag": "Sample size adequacy depends on study design and endpoints. AI provides benchmark comparison only.",
    }


def detect_statistical_methodology(text: str) -> Dict[str, Any]:
    """
    Detect presence/absence of statistical methodology elements in text.
    Keyword-based detection — NOT statistical evaluation.

    Args:
        text: Text content to scan

    Returns:
        Structured dict with presence/absence flags for each methodology element
    """
    results = {}
    for key, patterns in METHODOLOGY_PATTERNS.items():
        found = False
        matched_patterns = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                found = True
                matched_patterns.extend(matches[:3])  # Up to 3 examples
        results[key] = {
            "detected": found,
            "examples": matched_patterns[:3] if matched_patterns else [],
        }

    methodology_score = sum(1 for k, v in results.items() if v["detected"])

    return {
        "methodology_elements": results,
        "methodology_score": f"{methodology_score}/4 elements detected",
        "note": "Detection is keyword-based. Presence does not imply adequacy. Absence does not imply inadequacy. AI reports presence/absence only.",
        "human_verification_flag": "Statistical methodology adequacy requires biostatistics expertise.",
    }


def evaluate_temporal_applicability(data_year: int, device_changes_since: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Evaluate whether clinical data from a given year is still applicable,
    considering any device design changes since that time.

    Args:
        data_year: Year the clinical data was generated
        device_changes_since: List of design/manufacturing changes since data_year

    Returns:
        Structured dict with applicability flags
    """
    from datetime import datetime
    current_year = datetime.now().year
    age = current_year - data_year

    if age <= 3:
        age_flag = "current"
        age_note = f"Data is {age} years old — generally current for medical device evidence."
    elif age <= 5:
        age_flag = "aging"
        age_note = f"Data is {age} years old — may still be applicable if SOTA has not changed. Check for newer evidence."
    elif age <= 10:
        age_flag = "stale"
        age_note = f"Data is {age} years old — justification required for why older data remains applicable."
    else:
        age_flag = "significantly_stale"
        age_note = f"Data is {age} years old — only applicable for well-established technology (WET) with long PMS history."

    device_changes = device_changes_since or []
    changes_relevant = len(device_changes) > 0

    if changes_relevant and age_flag in ("aging", "stale", "significantly_stale"):
        applicability = "questionable"
        applicability_note = f"Data is {age_flag} AND device has changed since data was collected ({', '.join(device_changes[:3])}). The changes may invalidate the older data's applicability."
    elif changes_relevant:
        applicability = "needs_review"
        applicability_note = f"Data is relatively current but device has changed since collection. Review whether changes affect data applicability."
    elif age_flag in ("stale", "significantly_stale"):
        applicability = "needs_justification"
        applicability_note = f"Data is {age_flag}. Justification needed for continued applicability."
    else:
        applicability = "acceptable"
        applicability_note = "Data is current and no device changes detected."

    return {
        "data_year": data_year,
        "data_age_years": age,
        "age_flag": age_flag,
        "age_note": age_note,
        "device_changes_since": device_changes,
        "applicability": applicability,
        "applicability_note": applicability_note,
        "reference": "MDR Article 61 requires clinical data to be 'up-to-date.' Applicability is relative to device type and SOTA velocity.",
        "human_verification_flag": "Clinical judgment required to determine if device changes invalidate older data.",
    }


# Aggregate function — GS calls this once per quantitative claim
def evaluate_quantitative_claim(
    claim_text: str = "",
    events: Optional[int] = None,
    device_years: Optional[float] = None,
    device_class: str = "IIb",
    sample_size: Optional[int] = None,
    claim_type: str = "safety_claim",
    data_year: Optional[int] = None,
    device_changes_since: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Aggregate evaluation of a quantitative claim. GS extracts numbers from text,
    passes them here. This function calls the individual evaluators and returns
    a combined result.

    All results are advisory. No terminal judgments.
    """
    result = {
        "claim_text_preview": claim_text[:500] if claim_text else "",
        "device_class": device_class,
        "evaluations": {},
    }

    if events is not None and device_years is not None:
        result["evaluations"]["zero_events"] = evaluate_zero_events(events, device_years, device_class)

    if sample_size is not None:
        result["evaluations"]["sample_size"] = evaluate_sample_size(sample_size, device_class, claim_type)

    if claim_text:
        result["evaluations"]["methodology"] = detect_statistical_methodology(claim_text)

    if data_year is not None:
        result["evaluations"]["temporal"] = evaluate_temporal_applicability(data_year, device_changes_since)

    return result


# ============================================================
# CLI ENTRY POINT (V2.1 — called by GS Stage 2d)
# ============================================================

if __name__ == "__main__":
    import sys as _sys, json as _json

    if len(_sys.argv) < 2:
        print("Usage: python3 statistical_context_evaluator.py <command> [args...]")
        print("Commands:")
        print("  zero-events <events:int> <device_years:float> <device_class:str>")
        print("  sample-size <size:int> <device_class:str>")
        print("  detect-methodology '<text>'")
        print("  all <events:int> <device_years:float> <size:int> <device_class:str> '<text>'")
        _sys.exit(1)

    command = _sys.argv[1]

    if command == "zero-events":
        result = evaluate_zero_events(int(_sys.argv[2]), float(_sys.argv[3]), _sys.argv[4])
    elif command == "sample-size":
        result = evaluate_sample_size(int(_sys.argv[2]), _sys.argv[3], "safety_claim")
    elif command == "detect-methodology":
        result = detect_statistical_methodology(_sys.argv[2])
    elif command == "all":
        result = {
            "zero_events": evaluate_zero_events(int(_sys.argv[2]), float(_sys.argv[3]), _sys.argv[5]),
            "sample_size": evaluate_sample_size(int(_sys.argv[4]), _sys.argv[5], "safety_claim"),
            "methodology": detect_statistical_methodology(_sys.argv[6]),
        }
    else:
        result = {"error": f"Unknown command: {command}"}

    print(_json.dumps(result, indent=2, ensure_ascii=False))
