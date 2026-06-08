# SIMILAR / COMPETITOR EVIDENCE SPEC — V2 (REVISED)

> CCD 签发 | 2026-05-12

## Classification

| Relationship | Definition |
|---|---|
| `equivalent_device` | Same intended purpose, technical/biological/clinical equivalence validated |
| `similar_device` | Comparable clinical use, not equivalent |
| `competitor_device` | Market competitor, different design |
| `previous_generation` | Earlier version of subject device |
| `unrelated_device` | Not relevant — excluded from evidence pool |

## Comparability Scoring

Three dimensions, each scored 0-3:
- Technical comparability
- Biological comparability  
- Clinical comparability

| Raw (0-9) | Normalized (0-100) | Band |
|---|---|---|
| 7-9 | 78-100 | HIGH — may support clinical context + SOTA |
| 4-6 | 44-67 | MEDIUM — may support SOTA benchmark only |
| 0-3 | 0-33 | LOW — background only, cannot support claims |

## Allowed Use Rules

| Relationship | May Support | Forbidden | Limits |
|---|---|---|---|
| equivalent | Claims within validated equivalence scope only | Claims outside equivalence scope | Must have equivalence rationale on file |
| similar | Clinical context, SOTA benchmark, risk context | Direct clinical benefit claims for subject device | Must cite relationship + differences |
| competitor | SOTA benchmark only | Subject-device safety/performance/benefit claims | Must disclose competitive relationship |
| previous_gen | Clinical context, risk context | Direct performance claims (unless improvement documented) | Must trace improvement |
| unrelated | NOTHING | All claim types | Excluded from evidence pool |

## Relation Rationale Required

Per similar/competitor/previous-gen evidence item:
- `relation_rationale`: why this device is comparable
- `relation_limitations`: key differences from subject device
- `forbidden_use`: explicit list of disallowed claim types
- `max_conclusion_strength`: capped at "cautious" unless equivalence established

---

*CCD 签发：2026-05-12*
