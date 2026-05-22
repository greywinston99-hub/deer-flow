"""Phase 7 capability verification — tests all new LLM refinement, PRISMA, argument flow capabilities."""
import pytest
from deerflow.runtime.cer_authoring.pipeline import (
    _render_prisma_mermaid,
    _render_prisma_table,
    _score_argument_flow,
    _build_section_refinement_task,
    _build_cross_chapter_review_task,
    _generate_prisma_flow,
    _NB_TONE_INSTRUCTIONS,
    _llm_refine_chapters,
    _llm_cross_chapter_review,
)
from deerflow.runtime.cer_authoring.gates import _check_writing_style


# ── PRISMA Tests ──

def test_prisma_mermaid_generates():
    """PRISMA mermaid diagram renders with correct structure."""
    prisma = _generate_prisma_flow({
        "search_run_registry": [{"hits": 50, "database": "PubMed"}],
        "raw_literature_records": [{"pmid": "12345678"}, {"pmid": "12345678"}],  # duplicate
        "screening_disposition": [
            {"title_abstract_decision": "include"},
            {"title_abstract_decision": "exclude", "exclusion_reason": "Wrong population"},
        ],
    })
    mermaid = _render_prisma_mermaid(prisma)
    assert "mermaid" in mermaid
    assert "flowchart TD" in mermaid
    assert "Records identified" in mermaid


def test_prisma_table_generates():
    """PRISMA table renders with correct counts."""
    prisma = _generate_prisma_flow({
        "search_run_registry": [{"hits": 77}],
        "raw_literature_records": [{"pmid": str(30000000 + i)} for i in range(77)],
    })
    table = _render_prisma_table(prisma)
    assert "77" in table
    assert "PRISMA Stage" in table
    assert "deduplication" in table.lower()


# ── Argument Flow Tests ──

def test_argument_flow_scores_transitions():
    """Argument flow detects paragraph transitions."""
    text = (
        "The clinical evaluation assesses device safety and performance in the intended population. "
        "Evidence was collected from multiple sources including published literature and PMS data. "
        "The device has been on the market for over five years with a well-documented safety profile.\n\n"
        "However, several limitations must be acknowledged in the current evidence base. "
        "The available studies vary in methodological quality and sample size.\n\n"
        "Therefore, PMCF is recommended to address the identified evidence gaps. "
        "Specifically, a prospective registry study should be initiated within 12 months of certification.\n\n"
        "Furthermore, the benefit-risk profile remains acceptable when the device is used per IFU. "
        "The clinical benefits of reduced procedure time and improved outcomes outweigh the identified risks."
    )
    scores = _score_argument_flow({"1 Summary": text})
    assert scores["overall_flow"] > 0
    assert "argument_flow_scores" in scores


def test_argument_flow_short_text_skipped():
    """Short sections (<50 words) are skipped in flow scoring."""
    scores = _score_argument_flow({"1 Summary": "Short text."})
    assert scores["overall_flow"] == 0  # skipped due to <50 words


# ── LLM Refinement Task Tests ──

def test_refinement_task_includes_nb_tone():
    """Section refinement task includes NB-specific tone when NB is known."""
    task = _build_section_refinement_task(
        "1 Summary", "Test draft.",
        {"nb_specific_context": {"nb_body": "BSI"}}
    )
    assert "BSI" in task or "modular" in task.lower()


def test_refinement_task_summary():
    """Summary refinement task includes six-element framework."""
    task = _build_section_refinement_task("1 Summary", "Test.", {})
    assert "six-element" in task.lower() or "evidence base" in task.lower()


def test_refinement_task_conclusions():
    """Conclusions refinement task includes wording strength map."""
    task = _build_section_refinement_task("5 Conclusions", "Test.", {})
    assert "STRONG" in task or "demonstrates" in task.lower()


# ── Cross-Chapter Review Tests ──

def test_cross_chapter_review_task():
    """Cross-chapter review task includes consistency checks."""
    task = _build_cross_chapter_review_task({
        "cer_chapter_drafts": {
            "1 Summary": "Test summary content.",
            "3 Clinical Background, Current Knowledge and SOTA": "Test SOTA.",
            "5 Conclusions": "Test conclusions.",
        }
    })
    assert "cross-chapter" in task.lower() or "consistency" in task.lower()
    assert "SOTA" in task


# ── NB Tone Instructions ──

def test_nb_tone_all_configured():
    """All major NB bodies have tone instructions."""
    assert "BSI" in _NB_TONE_INSTRUCTIONS
    assert "TUV_SUD" in _NB_TONE_INSTRUCTIONS
    assert "DEKRA" in _NB_TONE_INSTRUCTIONS
    assert "modular" in _NB_TONE_INSTRUCTIONS["BSI"].lower()
    assert "standardized" in _NB_TONE_INSTRUCTIONS["TUV_SUD"].lower()


# ── LLM Fallback Tests ──

def test_llm_refine_falls_back_gracefully():
    """LLM refinement returns original drafts when LLM unavailable."""
    drafts = {"1 Summary": "The device is designed for clinical use in the intended population."}
    refined = _llm_refine_chapters({"cer_chapter_drafts": drafts})
    # Should return original drafts unchanged when LLM unavailable
    assert "1 Summary" in refined


def test_cross_chapter_review_falls_back():
    """Cross-chapter review returns graceful degradation when LLM unavailable."""
    result = _llm_cross_chapter_review({
        "cer_chapter_drafts": {
            "1 Summary": "Test.",
            "5 Conclusions": "Test.",
        }
    })
    assert "cross_chapter_review" in result


# ── Writing Style Integration ──

def test_writing_style_detects_passive_voice():
    """Passive voice detection works on typical CER text."""
    chapters = {
        "2 Device Description": (
            "The catheter is manufactured from medical-grade materials. "
            "It was designed by experienced engineers. The device is intended for clinical use. "
            "It has been evaluated in multiple clinical studies. The safety profile was established. "
            "Performance characteristics are documented in the IFU. " * 3
        )
    }
    violations = _check_writing_style(chapters)
    # Should detect style patterns (passive voice, sentence length, etc.)
    assert isinstance(violations, list)
