"""Skill registry loading and selection tests."""
from deerflow.runtime.cer_authoring.pipeline import (
    _load_skill_registry,
    _select_skills_for_node,
)


def test_registry_loads():
    """Verify skill_registry.json loads with 30 skills."""
    reg = _load_skill_registry()
    skills = reg.get("skills", [])
    assert len(skills) == 30, f"Expected 30 skills, got {len(skills)}"

    # Check key skills exist
    skill_ids = {s["id"] for s in skills}
    required = {"S-DPROF-03", "S-CLAIM-04", "S-SOTA-07", "W-SUM-18",
                "S-QA-25", "S-G42-15", "W-CLEAN-24"}
    missing = required - skill_ids
    assert not missing, f"Missing skills: {missing}"


def test_skill_schema():
    """Verify each skill has required fields."""
    reg = _load_skill_registry()
    for skill in reg.get("skills", []):
        for field in ["id", "name", "category", "target_node", "description"]:
            assert field in skill, f"Skill {skill.get('id', '?')} missing field: {field}"


def test_select_skills_writer():
    """Writer node should get writing skills."""
    skills = _select_skills_for_node("cer_writing", {})
    skill_ids = {s["id"] for s in skills}
    assert "W-SUM-18" in skill_ids
    assert "W-DD-19" in skill_ids
    assert "W-CONC-23" in skill_ids
    # Should NOT include non-writer skills
    assert "S-DPROF-03" not in skill_ids


def test_select_skills_empty():
    """Unknown node should get empty skill list."""
    skills = _select_skills_for_node("nonexistent", {})
    assert skills == []
