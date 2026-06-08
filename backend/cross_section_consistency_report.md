# CER Cross-Section Consistency Report

## STY Checks
| Check ID | Status | Detail |
|----------|--------|--------|
| STY-001 | SKIP | Device name or abbreviation not in metadata |
| STY-002 | FAIL | Multiple terms found: {'complication', 'adverse event'}. Prefer: 'adverse event' |
| STY-005 | FAIL | 442 naked percentages found |

## Cross-Chapter Consistency Checks
| Check | Status | Detail |
|-------|--------|--------|
| sample_size | FAIL | Sample size 100 found in {'00_CER_V3_COMPLETE', '07_pmcf', '05_conclusions'} but not in {'04_clinical_evidence', '03_clinical_background_sota'}; Sample size 456 found in {'00_CER_V3_COMPLETE', '05_conclusions'} but not in {'07_pmcf', '04_clinical_evidence', '03_clinical_background_sota'}; Sample size 50 found in {'00_CER_V3_COMPLETE', '07_pmcf'} but not in {'04_clinical_evidence', '05_conclusions', '03_clinical_background_sota'}; Sample size 85 found in {'00_CER_V3_COMPLETE', '07_pmcf'} but not in {'04_clinical_evidence', '05_conclusions', '03_clinical_background_sota'}; Sample size 245 found in {'00_CER_V3_COMPLETE', '04_clinical_evidence'} but not in {'07_pmcf', '05_conclusions', '03_clinical_background_sota'}; Sample size 257 found in {'00_CER_V3_COMPLETE', '05_conclusions', '03_clinical_background_sota'} but not in {'07_pmcf', '04_clinical_evidence'} |
| indication | SKIP | No indication in metadata |
| pmcf | PASS | PMCF chapter consistent with market status |
| limitation | PASS | Conclusion references limitations |
| endpoint | SKIP | No locked endpoints defined |
| DO-001 | PASS | Single variant — no difference matrix needed |
| TM-001 | PASS | No template residues |

## OVERALL: FAIL