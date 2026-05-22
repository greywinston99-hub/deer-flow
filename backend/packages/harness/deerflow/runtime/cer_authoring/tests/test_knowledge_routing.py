"""Per-node knowledge routing verification tests."""
from deerflow.runtime.cer_authoring.pipeline import (
    _get_knowledge_for_node,
    _NODE_TO_KAI_COMPONENT,
)


def test_all_42_nodes_mapped():
    """Verify all 42 LangGraph nodes are in the mapping."""
    assert len(_NODE_TO_KAI_COMPONENT) == 42
    # Key nodes
    for node in ["cer_writing", "gates", "sota_search", "device_profile",
                 "claim_decomposition", "evidence_appraisal", "gap_pmcf",
                 "controlled_compromise", "export", "initialize"]:
        assert node in _NODE_TO_KAI_COMPONENT, f"Missing node: {node}"


def test_cer_writing_routing():
    """cer_writing node should get writer_guards + slots."""
    kw = _get_knowledge_for_node("cer_writing", {})
    assert kw["_node"] == "cer_writing"
    assert "writer_guards" in kw["_components"]
    assert "slots" in kw["_components"]


def test_gates_routing():
    """gates node should only get gates component."""
    kw = _get_knowledge_for_node("gates", {})
    assert kw["_node"] == "gates"
    assert kw["_components"] == ["gates"]


def test_initialize_routing():
    """initialize node has no KAI components."""
    kw = _get_knowledge_for_node("initialize", {})
    assert kw["_node"] == "initialize"
    assert kw["_components"] == []


def test_unknown_node_routing():
    """Unknown node should return empty components."""
    kw = _get_knowledge_for_node("nonexistent_node", {})
    assert kw["_node"] == "nonexistent_node"
    assert kw["_components"] == []
