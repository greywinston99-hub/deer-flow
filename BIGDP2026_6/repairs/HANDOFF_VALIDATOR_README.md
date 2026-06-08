# BIGDP2026.6 R2: Claude Code Writer Handoff Validator

## Validator Locations

### 1. Importable Module (for DeerFlow runtime)
**Path:** `backend/packages/harness/deerflow/runtime/cer_authoring/cer_package_validator.py`
```python
from deerflow.runtime.cer_authoring.cer_package_validator import validate_package_or_exit
validate_package_or_exit(package_dict)
```

### 2. Standalone CLI (for Claude Code skill)
**Path:** `BIGDP2026_6/repairs/writer_package_validator.py`
```bash
python BIGDP2026_6/repairs/writer_package_validator.py <path_to_CER_INPUT_PACKAGE.json>
```

### 3. Claude Code Skill Pre-Flight
**Path:** `~/.claude/skills/cer-authoring-section-writer/SKILL.md`
The skill has a "Pre-Flight Package Validation" section that calls `validate_package_or_exit()` before writing any CER section.

## 8 Runtime Assertions (G.5.1-G.5.8)

| # | Check | Behavior on Fail |
|:---|:---|:---|
| 1 | `CER_INPUT_PACKAGE.json` exists and is valid JSON | Exit 2 |
| 2 | `pre_writer_readiness_gate_report.status == "PASS"` | Exit 2 |
| 3 | `cer_input_package_exported == true` | Exit 2 |
| 4 | All `claim_ids` in matrix resolve to claim_ledger | Exit 2 |
| 5 | All `evidence_ids` in matrix resolve to evidence_registry | Exit 2 |
| 6 | All benchmark endpoints have names | Exit 2 |
| 7 | BR/alignment ledger structures are valid | Exit 2 |
| 8 | `package_schema_version` in `{"1.0.0"}` | Exit 2 |

## Claude Code Skill Invocation

The `cer-authoring-section-writer` skill at `~/.claude/skills/cer-authoring-section-writer/SKILL.md` has been updated with a Pre-Flight Package Validation section. The writer MUST call the validator before writing any CER section.

```python
import json, sys
sys.path.insert(0, "<deer-flow-root>/backend/packages/harness")
from deerflow.runtime.cer_authoring.cer_package_validator import validate_package_or_exit

package = json.load(open("<project_dir>/CER_EVIDENCE_PACKAGE/CER_INPUT_PACKAGE.json"))
validate_package_or_exit(package)
```
