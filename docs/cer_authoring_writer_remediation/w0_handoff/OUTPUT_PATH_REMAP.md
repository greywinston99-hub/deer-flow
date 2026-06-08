# OUTPUT PATH REMAP

> CCD | 2026-05-15

## Old Contaminated Output Paths

```
/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_01启灏/02_AI_BASELINE_OUTPUT_FREEZE/
/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/02_AI_BASELINE_OUTPUT_FREEZE/
/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_03 永新-软件/02_AI_BASELINE_OUTPUT_FREEZE/
```

These contain contaminated CER drafts. Do NOT write regenerated drafts here.

## Quarantine Archive

```
/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer_writer_quarantine/2026-05-15_contaminated_outputs/
```

Contaminated files archived here with SHA256 checksums. Read-only. Regression fixtures only. Not Writer input.

## Future Regenerated Output Path

After writer remediation gates are implemented, regenerated CER drafts will be written to new clean output locations. Claude Code to determine exact paths during W5. Must NOT be same as contaminated paths above.

## Fixture Path

Regression fixtures reference archived copies:
```
.../cer_writer_quarantine/2026-05-15_contaminated_outputs/PILOT_01_QIHAO/CER_draft.md
.../cer_writer_quarantine/2026-05-15_contaminated_outputs/PILOT_02_MIDOS/CER_draft.md
```

## Rules

- New outputs NEVER write to old contaminated paths
- Quarantine files NEVER used as Writer templates
- Fixtures referenced from archive, not from 02_ directories
- Release candidate only from gate-passed regenerated paths

---

*CCD 签发：2026-05-15*
