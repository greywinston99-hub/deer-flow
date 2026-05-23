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

### Quick Test

```bash
# Preview the alert payload without sending
bash scripts/test_slack_webhook.sh

# Configure and test with your real Slack webhook
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
bash scripts/test_slack_webhook.sh
```

### Persistent Configuration

Add to your shell profile (`~/.bash_profile`, `~/.zshrc`, etc.):

```bash
# DeerFlow alerting
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
export ALERT_EMAIL="ops@yourcompany.com"  # optional, requires `mail` command
export DISK_THRESHOLD=80
export KEEP_PER_THREAD=15
```

Then reload:
```bash
source ~/.zshrc  # or ~/.bash_profile
```

### Alert Payload Format

The wrapper script sends a Slack message with:
- **text**: Alert summary (disk alerts / maintenance failure)
- **attachments.color**: `danger` (alert) or `good` (normal)
- **fields**: Disk alerts count, checkpoints cleaned, report path
- **footer**: "DeerFlow Maintenance" + timestamp

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
