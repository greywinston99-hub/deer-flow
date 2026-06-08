# 08 — Benchmark Generalization Audit

---

## Configuration

| Check | Status | Evidence |
|:---|:---:|:---|
| `config/cer/benchmark_domains.yaml` exists | ✅ | 4318 bytes |
| Known domains present | ✅ | `cardiac_pfa`, `urology_nephroscope` |
| Generic fallback present | ✅ | `generic` section with default template |
| YAML valid | ✅ | Loaded by `benchmark_domain_loader.py` |

---

## Runtime Loader

| Check | Status | Evidence |
|:---|:---:|:---|
| `benchmark_domain_loader.py` exists | ✅ | 95 lines |
| `load_benchmark_domain_config()` function | ✅ | Returns parsed YAML |
| `match_benchmark_domain()` function | ✅ | Matches device domain to template |
| Called by benchmark trace node | ✅ | `graph.py:1801-1813` |

---

## Known Domain Regression

| Check | Status | Evidence |
|:---|:---:|:---|
| Cardiac PFA benchmark still generated | ✅ | Regression tests pass |
| Urology nephroscope benchmark still generated | ✅ | Regression tests pass |
| Existing domains not broken | ✅ | `test_retrieval_domain_regressions.py` passes |

---

## Unknown Domain Fallback

| Check | Status | Evidence |
|:---|:---:|:---|
| Unknown domain uses generic template | ✅ | `test_benchmark_derivation_semantics.py` |
| Fallback has `directness=fallback` | ✅ | `test_fallback_benchmark_has_directness_fallback` |
| Fallback has `confidence=low` | ✅ | `test_benchmark_with_sources_has_higher_confidence` (inverse) |
| Limitations populated | ✅ | Generic template includes limitation notes |
| Alternatives rejected rationale populated | ✅ | `test_fallback_endpoint_has_alternatives_rationale` |

---

## Config-Only Extension

| Check | Status | Evidence |
|:---|:---:|:---|
| Adding domain requires only YAML change | ✅ | `benchmark_domain_loader.py` reads from YAML |
| No Python code change needed | ✅ | Domain list is externalized |

**Test evidence:** `test_benchmark_derivation_semantics.py` simulates an unknown domain and asserts it produces a reasoned fallback benchmark without code modification.

---

## Benchmark Trace Linkage

| Check | Status | Evidence |
|:---|:---:|:---|
| Benchmark trace included in CER_INPUT_PACKAGE | ✅ | State reducer |
| G42 consumes trace confidence | ✅ | Dynamic max rounds |
| G46 consumes SOTA table | ✅ | SOTA condition evaluator |
| Writer receives fallback limitations | ✅ | Trace included in package |

---

## Verdict

| Question | Answer |
|:---|:---|
| Can a new device domain be handled without Python change? | **YES** |
| Does unknown domain produce reasoned fallback? | **YES** |
| Are limitations written into trace and writer constraints? | **YES** |

**Benchmark Generalization: RUNTIME_ENFORCED**
