# DeerFlow CER Pipeline — Operations Cron Setup

## Weekly Maintenance (Recommended)

Add to your system crontab (`crontab -e`):

```cron
# DeerFlow CER pipeline maintenance — Sundays 03:00
# Cleanup checkpoint DB, expired feedback, disk monitoring
0 3 * * 0 cd /Users/winstonwei/Documents/Playground/deer-flow && \
  python backend/scripts/maintenance_cron.py \
    --db-path backend/.deer-flow/checkpoints.db \
    --artifact-root artifacts \
    --keep-per-thread 15 \
    --disk-threshold 80 \
    >> logs/maintenance_cron.log 2>&1

# Daily lightweight disk check (no cleanup)
0 6 * * * cd /Users/winstonwei/Documents/Playground/deer-flow && \
  python backend/scripts/maintenance_cron.py \
    --skip-checkpoints --skip-feedback \
    --disk-threshold 85 \
    >> logs/disk_check.log 2>&1
```

## Alerting Integration

The maintenance script exits with code 1 when:
- Disk usage exceeds `--disk-threshold`
- Checkpoint DB maintenance fails
- Feedback cleanup fails

Use the exit code in your alerting pipeline:

```bash
# Slack webhook example (add to cron wrapper script)
if ! python backend/scripts/maintenance_cron.py --disk-threshold 80; then
  curl -X POST "$SLACK_WEBHOOK_URL" \
    -H 'Content-type: application/json' \
    -d '{"text":"🚨 DeerFlow maintenance alert — check logs/maintenance_cron.log"}'
fi
```

## Report Persistence

Reports are written to `artifacts/maintenance/`:
- `maintenance_YYYYMMDD_HHMMSS.json` — timestamped report
- `latest.json` — symlink to most recent report

Key report fields:
- `disk.alert_count` — number of paths above threshold
- `checkpoints.cleanup.deleted_checkpoints` — cleaned checkpoints
- `feedback.total_removed` — expired feedback files removed

## Manual Invocation

```bash
# Dry-run (analyze only, no deletion)
python backend/scripts/maintenance_cron.py --dry-run

# Custom thresholds
python backend/scripts/maintenance_cron.py \
  --keep-per-thread 20 \
  --disk-threshold 75 \
  --artifact-root /path/to/custom/artifacts

# Skip phases
python backend/scripts/maintenance_cron.py --skip-checkpoints --skip-feedback
```
