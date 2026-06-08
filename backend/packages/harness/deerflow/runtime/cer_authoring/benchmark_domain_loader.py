"""BIGDP2026.6 Phase 5: Benchmark domain configuration loader.

Loads `config/cer/benchmark_domains.yaml` at runtime and provides
domain matching, endpoint lookup, and generic fallback for unknown domains.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Cache: loaded once, reused across calls
_config_cache: dict[str, Any] | None = None
_CONFIG_PATH = None


def _find_config_path() -> Path:
    """Locate benchmark_domains.yaml relative to the project root."""
    global _CONFIG_PATH
    if _CONFIG_PATH:
        return Path(_CONFIG_PATH)

    # Try relative to this file's location
    candidates = [
        Path(__file__).resolve().parents[5] / "config" / "cer" / "benchmark_domains.yaml",
        Path(__file__).resolve().parents[4] / "config" / "cer" / "benchmark_domains.yaml",
        Path("config/cer/benchmark_domains.yaml"),
    ]
    for p in candidates:
        if p.exists():
            _CONFIG_PATH = str(p)
            return p

    raise FileNotFoundError(
        "benchmark_domains.yaml not found. Expected at config/cer/benchmark_domains.yaml "
        "relative to project root."
    )


def load_benchmark_domain_config() -> dict[str, Any]:
    """Load the benchmark domain configuration (cached)."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    path = _find_config_path()
    logger.info("Loading benchmark domain config from %s", path)
    with open(path, "r") as f:
        _config_cache = yaml.safe_load(f) or {}
    return _config_cache


def match_benchmark_domain(
    clinical_domain: str = "",
    keywords: list[str] | None = None,
    device_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Match a device to its benchmark domain configuration.

    Returns the matched domain config, or the generic fallback if no match.
    """
    config = load_benchmark_domain_config()
    domains = config.get("domains", {})
    fallback = config.get("generic_fallback", {})

    # Strategy 1: exact clinical_domain match
    if clinical_domain:
        for domain_key, domain_cfg in domains.items():
            if domain_cfg.get("clinical_domain", "").lower() == clinical_domain.lower():
                return {"domain_key": domain_key, "matched_by": "exact_domain", **domain_cfg}

    # Strategy 2: keyword match from device_profile
    search_terms = list(keywords or [])
    if device_profile:
        search_terms.extend([
            str(device_profile.get("clinical_domain", "")),
            str(device_profile.get("intended_use", "")),
            str(device_profile.get("device_name", "")),
        ])

    if search_terms:
        search_text = " ".join(search_terms).lower()
        best_match = None
        best_score = 0
        for domain_key, domain_cfg in domains.items():
            domain_kw = domain_cfg.get("keywords", [])
            score = sum(1 for kw in domain_kw if kw.lower() in search_text)
            if score > best_score:
                best_score = score
                best_match = (domain_key, domain_cfg)

        if best_match and best_score >= 1:
            domain_key, domain_cfg = best_match
            return {"domain_key": domain_key, "matched_by": f"keyword_match(score={best_score})", **domain_cfg}

    # Strategy 3: fallback
    logger.warning("No benchmark domain matched for clinical_domain='%s'. Using generic fallback.", clinical_domain)
    return {"domain_key": "generic_fallback", "matched_by": "fallback", **fallback}


def get_endpoints_for_domain(domain_config: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract typical endpoints from a domain config."""
    return domain_config.get("typical_endpoints", [])


def get_acceptability_criteria(domain_config: dict[str, Any]) -> list[str]:
    """Extract acceptability criteria from a domain config."""
    return domain_config.get("acceptability_criteria", [])


def get_benchmark_requirements(domain_config: dict[str, Any]) -> dict[str, Any]:
    """Extract benchmark source requirements from a domain config."""
    return domain_config.get("benchmark_sources", {})
