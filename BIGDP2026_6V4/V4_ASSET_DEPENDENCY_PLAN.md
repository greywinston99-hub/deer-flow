# V4 — Asset Dependency Plan

**Current Asset State:** Patch A Tier 2 — 18 projects, Tier 1 PASS, Tier 2 PARTIAL.
**V4 Asset Needs:** Mostly regulatory documents + strategy exemplars. Less dependent on gold clinical labels than V3.

---

## 1. Per-Batch Asset Requirements

| Batch | Required Assets | Source | Status |
|:---|:---|:---|:---|
| I | MDR Annex XIV, MEDDEV 2.7/1 Rev.4, MDCG 2020-5, MDCG 2020-6 | Regulatory pack | PARTIAL (files exist, content not indexed for rules) |
| I | WET/legacy/equivalence exemplar projects (2–3) | Patch A projects | PARTIAL (projects exist, WET/legacy classification not done) |
| J | Literature with known roles (10+ articles) | Patch A B4 PMID trace | PARTIAL |
| K | CER blueprints per route (structural — can derive from regulatory docs) | Regulatory pack + strategy framework | PARTIAL |
| L | 2–3 projects for dry-run validation | Patch A projects | PARTIAL |

---

## 2. V4-Specific New Assets Needed

| Asset | Why V4 Needs It | Can Derive from Existing? |
|:---|:---|:---|
| WET determination exemplars | Calibrate WET 6-condition check | Can derive from MDR/MEDDEV text |
| Legacy gap analysis exemplars | Calibrate legacy sufficiency check | Can derive from MDR Annex XIV |
| Strategy route gold labels | Verify route correctness | NOT available — need expert classification of 5–10 projects |
| Literature role gold labels | Verify role classifier accuracy | NOT available — need expert role assignment per article |
| NB explainability exemplar | Format template | Can design from CEAR template |

---

## 3. Asset Degradation Policy

| Asset State | Batch I | Batch J | Batch K | Batch L |
|:---|:---|:---|:---|:---|
| Regulatory docs READY | FULLY_CLOSED possible for rule-based decisions | DERIVED | DERIVED | DERIVED |
| Regulatory docs PARTIAL | HEURISTIC (rule logic from known text) | HEURISTIC | HEURISTIC | HEURISTIC |
| Strategy gold labels READY | FULLY_CLOSED | — | DERIVED | FULLY_CLOSED |
| Strategy gold labels NOT_FOUND | HEURISTIC (route from device factors only) | — | HEURISTIC | HEURISTIC |
| Literature gold labels READY | — | FULLY_CLOSED | — | DERIVED |
| Literature gold labels NOT_FOUND | — | HEURISTIC (rules only) | — | HEURISTIC |
| Dry-run projects READY | — | — | — | DERIVED |
| Dry-run projects NOT_FOUND | — | — | — | SYNTHETIC_ONLY |

---

## 4. What V4 Needs from Owner

| Item | Priority | Description |
|:---|:--:|:---|
| Regulatory document indexing | P0 | MDR Annex XIV + MEDDEV + MDCG indexed by clause for rule extraction |
| Strategy route gold labels | P0.5 | For 5–10 projects: expert classification of strategy route (WET/legacy/own-data/equivalence/literature/innovation) |
| WET/legacy project classification | P0.5 | For 5–10 projects: is this WET? Legacy? Own-data? Equivalence? Literature? Without these, Batch I route accuracy unverified |
| Literature role gold labels | P1 | For 20–30 articles: correct primary role + secondary roles + data-point-level roles |
| NB explainability exemplars | P1 | 3–5 NB explainability packet examples from real or representative projects |
| Dry-run validation projects | P1 | 2–3 projects with different strategy routes for Batch L validation |
