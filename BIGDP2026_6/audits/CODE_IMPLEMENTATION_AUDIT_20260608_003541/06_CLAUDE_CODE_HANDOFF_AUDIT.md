# 06 — Claude Code Handoff Audit

**Scope:** Whether the Claude Code Writer handoff is enforced at runtime.

---

## DeerFlow Side (Package Export)

| Check | Status | Evidence |
|:---|:---|:---|
| `CER_INPUT_PACKAGE.json` export node exists | ✅ CODE_CONFIRMED | `graph.py` `_node_cer_input_package_export` |
| Reference integrity check before export | ⚠️ PARTIAL | `cer_package_validator.py` exists but not verified to be called by export node |
| Orphan evidence detection | ✅ CODE_CONFIRMED | `cer_package_validator.py:45-80` iterates evidence references |
| Claim_id resolution | ✅ CODE_CONFIRMED | `cer_package_validator.py:81-110` checks claim references |
| Evidence_id resolution | ✅ CODE_CONFIRMED | `cer_package_validator.py:45-80` |
| Benchmark_id resolution | ✅ CODE_CONFIRMED | `cer_package_validator.py:111-140` |
| BR/alignment reference resolution | ✅ CODE_CONFIRMED | `cer_package_validator.py:141-170` |
| `package_schema_version` field | ❌ NOT_FOUND | No schema version field found in export node or validator |
| Export BLOCKED on orphan | ⚠️ INFERRED | Validator returns validation report; export node behavior not fully verified |

**Verdict:** PARTIAL. `cer_package_validator.py` is a real module with 170+ lines of validation logic. But its integration into the export node is not CODE_CONFIRMED.

---

## Claude Code Skill Side

| Check | Status | Evidence |
|:---|:---|:---|
| Skill entrypoint found | ❌ NOT_FOUND | `.claude/skills/cer-authoring-section-writer/` not found |
| Runtime assertion: package exists | ❌ NOT_FOUND | No skill code inspected |
| Runtime assertion: G46=PASS | ❌ NOT_FOUND | No skill code inspected |
| Runtime assertion: cer_input_package_exported=true | ❌ NOT_FOUND | No skill code inspected |
| Runtime assertion: claim_ids resolve | ❌ NOT_FOUND | No skill code inspected |
| Runtime assertion: evidence_ids resolve | ❌ NOT_FOUND | No skill code inspected |
| Runtime assertion: benchmark_ids resolve | ❌ NOT_FOUND | No skill code inspected |
| Runtime assertion: package_schema_version supported | ❌ NOT_FOUND | No skill code inspected |
| Skill refuses invalid package | ❌ NOT_FOUND | No skill code inspected |

**Verdict:** NOT_FOUND. The Claude Code skill was not found in the expected location. The `.claude/skills/` directory does not contain `cer-authoring-section-writer`.

---

## DF_WRITING_ENGINE Default

| Check | Status | Evidence |
|:---|:---|:---|
| `DF_WRITING_ENGINE=claude_code` is default | ✅ CODE_CONFIRMED | `graph.py:2308` (per evidence pack) still valid |
| Legacy deerflow mode still available | ✅ CODE_CONFIRMED | `graph.py:2360-2370` conditional registration |

**Verdict:** PASS. Default is claude_code. Legacy mode gated.

---

## Handoff Integrity

| Layer | Status | Notes |
|:---|:---|:---|
| DeerFlow graph terminates at export | ✅ SAFE | Graph ends at `cer_input_package_export` when claude_code mode |
| DeerFlow export validates package | ⚠️ PARTIAL | Validator exists. Integration not fully verified. |
| Claude Code skill validates package | ❌ NOT_FOUND | Skill not found |
| Writer can run without gate-passed package | ⚠️ UNSAFE | If Claude Code skill does not validate, Writer could write without package |

---

## Critical Finding

**Red Flag:** The Claude Code handoff is **one-sided**.

- DeerFlow side: Graph construction enforces termination at export. Package validator exists.
- Claude Code side: **Skill not found.** No runtime assertions verified.

If the Claude Code skill does not validate the package, the Writer could theoretically:
1. Receive no package
2. Receive a package with G46 BLOCKED
3. Write claims without verified evidence links
4. Write benchmarks without acceptable rationale

**This is a P1 gap, not P0, because:**
- The graph construction makes it unlikely (Writer nodes are not registered)
- But defense-in-depth requires the Writer to validate independently

**Recommended repair:**
1. Locate the Claude Code skill (may be in a different directory)
2. Add runtime assertions as specified in Master Plan Phase 4
3. If skill does not exist, create it before Phase 4 is marked complete
