"""Evidence-Conclusion Phrase Policy — Embedded authoritative data for Gate 3.

Maps support_level values to allowed/forbidden conclusion phrases.
Handles negation detection for forbidden phrases.

CCD | 2026-05-15 | Authoritative for Gate 3
"""

from __future__ import annotations

import re

# ── Per-strength-level phrase policies ──────────────────────────────────────

INSUFFICIENT_ALLOWED: list[str] = [
    "current evidence is insufficient to conclude",
    "cannot be determined from available data",
    "further clinical evidence is required",
    "claim held pending additional data",
    "no conclusion can be drawn at this stage",
    "evidence does not support a conclusion",
]

INSUFFICIENT_FORBIDDEN: list[str] = [
    "clinical data support",   # catches supports/supporting/supported/in support of
    "demonstrate",             # catches demonstrates/demonstrated
    "confirm",                 # catches confirms/confirmed
    "favourable",
    "favorable",
    "partial support",
    "partially support",
    "the evidence suggests",
    "the data indicate",       # catches indicates/indicating
    "acceptable",
    "adequate",
    "sufficient",
]

CAUTIOUS_ALLOWED: list[str] = [
    "limited evidence suggests",
    "preliminary data indicate",
    "may be associated with",
    "observational data hint at",
    "further confirmation is required",
]

CAUTIOUS_FORBIDDEN: list[str] = [
    "demonstrate",
    "confirm",
    "prove",
    "strong",
    "robust",
    "conclusive",
    "clearly",
    "definitively",
    "fully support",
    "establish",
    "established",
]

MODERATE_ALLOWED: list[str] = [
    "evidence supports",
    "clinical data indicate",
    "studies demonstrate",
    "acceptable benefit-risk",
]

MODERATE_FORBIDDEN: list[str] = [
    "strongly support",
    "conclusively",
    "definitively",
    "without uncertainty",
]

STRONG_ALLOWED: list[str] = [
    "strongly support",
    "confirm",
    "demonstrate with high confidence",
    "robust evidence",
    "well-established",
]

STRONG_FORBIDDEN: list[str] = []  # STRONG is the most permissive level


POLICY_BY_LEVEL: dict[str, dict[str, list[str]]] = {
    "INSUFFICIENT": {"allowed": INSUFFICIENT_ALLOWED, "forbidden": INSUFFICIENT_FORBIDDEN},
    "CAUTIOUS": {"allowed": CAUTIOUS_ALLOWED, "forbidden": CAUTIOUS_FORBIDDEN},
    "MODERATE": {"allowed": MODERATE_ALLOWED, "forbidden": MODERATE_FORBIDDEN},
    "STRONG": {"allowed": STRONG_ALLOWED, "forbidden": STRONG_FORBIDDEN},
}

# INSUFFICIENT aliases — these levels map to INSUFFICIENT policy
INSUFFICIENT_ALIASES: set[str] = {
    "INSUFFICIENT",
    "insufficient",
    "evidence_gap",
    "blocked",
    "BLOCKED",
    "not_allowed",
    "ALLOWED_USE_BLOCKED",
    "retrieval_incomplete",
}

# ── Negation markers ────────────────────────────────────────────────────────

NEGATION_MARKERS: list[str] = [
    "not",
    "no",
    "cannot",
    "does not",
    "do not",
    "did not",
    "insufficient to",
    "fails to",
    "failed to",
    "neither",
    "nor",
    "never",
    "must",
    "need to",
    "should",
]

# ── Core logic ──────────────────────────────────────────────────────────────


def resolve_policy_level(support_level: str | None) -> str | None:
    """Map a raw support_level to a policy level (INSUFFICIENT/CAUTIOUS/MODERATE/STRONG).

    Returns None if the support_level is unrecognised (gate should not run).
    """
    if not support_level:
        return None
    sl = support_level.strip()
    if sl in INSUFFICIENT_ALIASES:
        return "INSUFFICIENT"
    if sl.upper() in POLICY_BY_LEVEL:
        return sl.upper()
    if sl.lower() in {"cautious", "moderate", "strong"}:
        return sl.upper()
    return None


def get_forbidden_phrases(policy_level: str) -> list[str]:
    """Return the forbidden phrase list for a policy level."""
    entry = POLICY_BY_LEVEL.get(policy_level.upper(), {})
    return list(entry.get("forbidden", []))


def has_negation_before(text: str, match_pos: int, window: int = 10) -> bool:
    """Check whether a negation marker appears within `window` words before match_pos in text.

    The `window` parameter controls how many words back to look. Default 10 per spec.
    """
    before = text[:match_pos]
    words_before = before.split()
    check_words = words_before[-window:] if len(words_before) > window else words_before
    before_window = " ".join(check_words).lower()
    for marker in NEGATION_MARKERS:
        if marker in before_window:
            return True
    return False


def _is_word_boundary_match(text: str, phrase: str, idx: int) -> bool:
    """Check that a phrase match at idx is a word-boundary match.

    Prevents substring false positives like 'sufficient' inside 'insufficient'.
    """
    # Check character before match (if any) is a word boundary
    if idx > 0 and text[idx - 1].isalpha():
        return False
    # Check character after match (if any) is a word boundary
    after_pos = idx + len(phrase)
    if after_pos < len(text) and text[after_pos].isalpha():
        return False
    return True


def scan_for_forbidden_phrases(
    text: str,
    forbidden_phrases: list[str],
    negation_window: int = 10,
) -> list[dict]:
    """Scan text for forbidden phrases, returning findings for non-negated matches.

    Uses word-boundary matching to avoid substring false positives
    (e.g. 'sufficient' inside 'insufficient').

    Returns a list of dicts: {phrase, position, surrounding_text, negated, section}
    """
    findings: list[dict] = []
    text_lower = text.lower()
    for phrase in forbidden_phrases:
        phrase_lower = phrase.lower()
        pos = 0
        while True:
            idx = text_lower.find(phrase_lower, pos)
            if idx == -1:
                break
            if _is_word_boundary_match(text_lower, phrase_lower, idx):
                negated = has_negation_before(text, idx, window=negation_window)
                findings.append({
                    "phrase": phrase,
                    "position": idx,
                    "surrounding_text": text[max(0, idx - 60):idx + len(phrase) + 60],
                    "negated": negated,
                    "triggers_fail": not negated,
                })
            pos = idx + 1
    return findings
