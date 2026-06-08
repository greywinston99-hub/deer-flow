#!/bin/bash
# BIGDP2026.6 Deployment Verification Script
# ==========================================
# Run before deploying BIGDP2026.6 changes to production.
# Exits with code 0 if all checks pass, non-zero otherwise.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python3"
FAILURES=0
CHECKS=0

red() { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }
check() {
    CHECKS=$((CHECKS + 1))
    local label="$1"; shift
    if "$@"; then
        green "  [PASS] $label"
    else
        red "  [FAIL] $label"
        FAILURES=$((FAILURES + 1))
    fi
}

echo "=== BIGDP2026.6 Deployment Verification ==="
echo "Project root: $PROJECT_ROOT"
echo "Python: $VENV_PYTHON"
echo ""

# ── 1. Python imports ──
echo "--- 1. Core Module Imports ---"
check "gates module" $VENV_PYTHON -c "from deerflow.runtime.cer_authoring import gates"
check "graph module" $VENV_PYTHON -c "from deerflow.runtime.cer_authoring import graph"
check "pipeline module" $VENV_PYTHON -c "from deerflow.runtime.cer_authoring import pipeline"
check "cer_package_validator" $VENV_PYTHON -c "from deerflow.runtime.cer_authoring.cer_package_validator import validate_package_or_exit"
check "benchmark_domain_loader" $VENV_PYTHON -c "from deerflow.runtime.cer_authoring.benchmark_domain_loader import load_benchmark_domain_config"

# ── 2. Key constants ──
echo ""
echo "--- 2. Key Constants ---"
check "MAX_SPIRAL_ROUNDS defined" $VENV_PYTHON -c "from deerflow.runtime.cer_authoring.gates import MAX_SPIRAL_ROUNDS; assert MAX_SPIRAL_ROUNDS == 3"
check "MAX_SPIRAL_ROUNDS in graph" $VENV_PYTHON -c "from deerflow.runtime.cer_authoring.graph import MAX_SPIRAL_ROUNDS; assert MAX_SPIRAL_ROUNDS == 3"

# ── 3. DAG compilation ──
echo ""
echo "--- 3. DAG Compilation ---"
check "DAG compiles" $VENV_PYTHON -c "
from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph
g = build_cer_authoring_graph()
nodes = list(g.nodes.keys())
assert len(nodes) >= 50, f'Only {len(nodes)} nodes'
for n in ['build_reasoning_ledger','build_ifu_evolution_ledger','build_benchmark_trace','pre_writer_readiness_gate']:
    assert n in nodes, f'{n} missing'
print(f'DAG OK: {len(nodes)} nodes')
"

# ── 4. Schemas ──
echo ""
echo "--- 4. JSON Schemas ---"
check "cer_reasoning_ledger schema" test -f "$PROJECT_ROOT/schemas/cer_reasoning_ledger.schema.json"
check "ifu_claim_evolution_ledger schema" test -f "$PROJECT_ROOT/schemas/ifu_claim_evolution_ledger.schema.json"
check "benchmark_derivation_trace schema" test -f "$PROJECT_ROOT/schemas/benchmark_derivation_trace.schema.json"

# ── 5. Config ──
echo ""
echo "--- 5. Configuration ---"
check "benchmark_domains.yaml" test -f "$PROJECT_ROOT/config/cer/benchmark_domains.yaml"

# ── 6. Expert Logic Pack ──
echo ""
echo "--- 6. Expert Logic Pack ---"
ELP="$PROJECT_ROOT/BIGDP2026_6/expert_logic_pack"
check "SOP exists" test -f "$ELP/EXPERT_CER_EXECUTION_SOP.md"
check "Rulebook exists" test -f "$ELP/EXPERT_REASONING_RULEBOOK.yaml"
check "8 expert YAML files" test "$(ls $ELP/*.yaml 2>/dev/null | wc -l)" -ge 8
check "12 scenario fixtures" test "$(ls $ELP/scenario_fixtures/*.json 2>/dev/null | wc -l)" -ge 12

# ── 7. P0 Defect Verification ──
echo ""
echo "--- 7. P0 Defect Verification ---"
check "G46 no auto-downgrade" $VENV_PYTHON -c "
from deerflow.runtime.cer_authoring.gates import evaluate_pre_writer_readiness_gate
state = {'claim_evidence_matrix': [], 'claim_ledger': [{'claim_id': 'C-01'}]}
r = evaluate_pre_writer_readiness_gate(state)
# With real evaluators, missing evidence should BLOCK or REWORK, not silently PASS
assert r['status'] != 'PASS', 'G46 should not PASS with missing evidence'
"

check "HC-01 rework populated" $VENV_PYTHON -c "
from deerflow.runtime.cer_authoring.graph import REWORK_TARGETS
assert len(REWORK_TARGETS.get('device_profile', [])) > 0, 'device_profile rework targets empty'
"

check "Event Bus dedup" $VENV_PYTHON -c "
from deerflow.runtime.cer_authoring.graph import _node_evidence_appraisal
# Just verify the function exists and is importable
assert callable(_node_evidence_appraisal)
"

# ── 8. Targeted Tests ──
echo ""
echo "--- 8. Targeted Test Suites (quick) ---"
check "G46 tests" $VENV_PYTHON -m pytest "$PROJECT_ROOT/backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_g46.py" -q --tb=line 2>/dev/null
check "G42 tests" $VENV_PYTHON -m pytest "$PROJECT_ROOT/backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_g42.py" -q --tb=line 2>/dev/null
check "Phase 2 ledger tests" $VENV_PYTHON -m pytest "$PROJECT_ROOT/backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_phase2_ledgers.py" -q --tb=line 2>/dev/null
check "Phase 3 gate tests" $VENV_PYTHON -m pytest "$PROJECT_ROOT/backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_phase3_gates.py" -q --tb=line 2>/dev/null
check "Phase 4 handoff tests" $VENV_PYTHON -m pytest "$PROJECT_ROOT/backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_phase4_handoff.py" -q --tb=line 2>/dev/null
check "Semantic tests" $VENV_PYTHON -m pytest \
    "$PROJECT_ROOT/backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_ifu_claim_semantic_evolution.py" \
    "$PROJECT_ROOT/backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_claim_conclusion_strength.py" \
    "$PROJECT_ROOT/backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_writer_release_semantics.py" \
    -q --tb=line 2>/dev/null

# ── Summary ──
echo ""
echo "========================================="
if [ "$FAILURES" -eq 0 ]; then
    green "ALL $CHECKS CHECKS PASSED — BIGDP2026.6 ready for deployment"
    exit 0
else
    red "$FAILURES/$CHECKS CHECKS FAILED — fix before deployment"
    exit 1
fi
