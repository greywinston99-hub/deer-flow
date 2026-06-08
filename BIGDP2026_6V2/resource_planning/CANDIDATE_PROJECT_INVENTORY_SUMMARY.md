# BIGDP2026.6V_2 — Candidate Project Inventory Summary

**Phase:** A1 — Local Resource Discovery (PARTIAL)
**Scanner:** Claude Code (read-only)
**Scan Date:** 2026-06-08
**Confidence Levels:** HIGH (content sampled) / MEDIUM (folder structure only) / LOW (filename inferred) / NOT_FOUND
**Note:** All entries are CANDIDATES — not authorized, not confirmed. Owner selection required (A2).

---

## Summary

| Metric | Value |
|:---|:---|
| Total candidate directories scanned | 188 (CER-RAG) + 15 (deer-flow artifacts) |
| Candidates selected for inventory | 11 |
| HIGH confidence | 1 |
| MEDIUM confidence | 8 |
| LOW confidence | 2 |
| Calibration candidates | 4 |
| Stress candidates | 4 |
| Holdout candidates | 3 |
| NOT_FOUND paths | 0 |

## Key Gaps

- **No project with confirmed iTClamp/血管闭合器 device type** — CAND-001 likely matches but folder content not inspected beyond structure
- **No project with confirmed NB feedback** — NB feedback availability unknown across all candidates
- **No project with confirmed manual search gold** — Cannot determine from folder structure alone
- **187 projects not inspected in CER-RAG** — could contain more calibration candidates

## Next Step for A1 Completion

Claude Code should perform deep scan of CAND-001 through CAND-011 (reading PROJECT_FILE_MANIFEST.csv / project_profile.yaml / input files) after Owner authorization in A2.
