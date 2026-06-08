# BIGDP2026.6 — Deployment Manifest

**Date:** 2026-06-08
**Tag:** `BIGDP2026.6-v1.0.0`
**Status:** GO — Ready for deployment

---

## Pre-Deployment Verification

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow
bash BIGDP2026_6/deploy_verify.sh
```
**Result:** ALL 25 CHECKS PASSED ✅

---

## Files to Deploy

### Production Code (must deploy)
| File | Action |
|:---|:---|
| `backend/.../gates.py` | Modified — G46 hardening, MAX_SPIRAL_ROUNDS, expert evaluators |
| `backend/.../graph.py` | Modified — HC-01 rework, Event Bus dedup, 3 ledger nodes, DAG wiring |
| `backend/.../pipeline.py` | Modified — Bug fix + ledger export keys |
| `backend/.../expert_rule_loader.py` | NEW — Expert logic runtime integration |
| `backend/.../benchmark_domain_loader.py` | NEW — Benchmark config runtime loader |
| `backend/.../cer_package_validator.py` | NEW — Claude Code handoff validator |

### Schemas & Config (must deploy)
| File | Action |
|:---|:---|
| `schemas/cer_reasoning_ledger.schema.json` | NEW |
| `schemas/ifu_claim_evolution_ledger.schema.json` | NEW |
| `schemas/benchmark_derivation_trace.schema.json` | NEW |
| `config/cer/benchmark_domains.yaml` | NEW |

### Tests (must deploy)
All test files in `backend/.../tests/` (14 files — 12 new + 2 modified)

### Expert Logic Pack (deploy for reference)
`BIGDP2026_6/expert_logic_pack/` — 11 files

### Claude Code Skill (must update)
`~/.claude/skills/cer-authoring-section-writer/SKILL.md` — Pre-flight section added

---

## Deployment Commands

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow

# 1. Commit all changes
git add -A
git commit -m "BIGDP2026.6: Expert Reasoning CER Execution System

- P0 safety repairs (G46, HC-01, MAX_SPIRAL, Event Bus)
- Expert reasoning ledgers (CER_REASONING, IFU_EVOLUTION, BENCHMARK_TRACE)
- Gate integration (G42 dynamic, G43 ledger, Source Preflight 4-tier)
- Claude Code handoff enforcement
- Benchmark domain generalization
- Expert Logic Pack runtime integration
- 500/500 tests pass, 16/16 audit GAPs closed
- Controller GO decision (D-009)"

# 2. Push with tag
git push origin main
git push origin BIGDP2026.6-v1.0.0

# 3. Verify on target
bash BIGDP2026_6/deploy_verify.sh
.venv/bin/python3 -m pytest backend/packages/harness/deerflow/runtime/cer_authoring/tests/ -q
```

---

## Post-Deployment Verification

```bash
# Quick smoke test
.venv/bin/python3 -c "
from deerflow.runtime.cer_authoring.gates import MAX_SPIRAL_ROUNDS
from deerflow.runtime.cer_authoring.expert_rule_loader import get_conclusion_strength
assert MAX_SPIRAL_ROUNDS == 3
assert get_conclusion_strength('direct', 2) == 'strong'
assert get_conclusion_strength('indirect', 3) != 'strong'
print('Smoke test PASSED')
"

# Package validator
python3 BIGDP2026_6/repairs/writer_package_validator.py --help
```

---

## Rollback

```bash
git revert BIGDP2026.6-v1.0.0
# or
git checkout <previous_commit_sha>
```
