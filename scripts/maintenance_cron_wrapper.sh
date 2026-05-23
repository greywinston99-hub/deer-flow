#!/bin/bash
# DeerFlow CER Pipeline — Maintenance Cron Wrapper with Alerting
#
# This wrapper runs maintenance_cron.py and sends alerts on failure.
# Place in crontab: 0 3 * * 0 /path/to/deer-flow/scripts/maintenance_cron_wrapper.sh
#
# Environment:
#   SLACK_WEBHOOK_URL    — Slack incoming webhook URL (optional)
#   ALERT_EMAIL          — Email address for alerts (optional)
#   DISK_THRESHOLD       — Disk usage alert threshold % (default: 80)
#   KEEP_PER_THREAD      — Checkpoints to keep per thread (default: 15)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
ALERT_LOG="${LOG_DIR}/maintenance_alert.log"
REPORT_DIR="${PROJECT_ROOT}/artifacts/maintenance"

mkdir -p "${LOG_DIR}" "${REPORT_DIR}"

SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
ALERT_EMAIL="${ALERT_EMAIL:-}"
DISK_THRESHOLD="${DISK_THRESHOLD:-80}"
KEEP_PER_THREAD="${KEEP_PER_THREAD:-15}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="${REPORT_DIR}/maintenance_${TIMESTAMP}.json"
RUN_LOG="${LOG_DIR}/maintenance_cron_${TIMESTAMP}.log"

# ── Run maintenance ─────────────────────────────────────────────────────────
{
    echo "=== DeerFlow Maintenance Started: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
    echo "Project: ${PROJECT_ROOT}"
    echo "Disk threshold: ${DISK_THRESHOLD}%"
    echo "Keep per thread: ${KEEP_PER_THREAD}"
    echo ""

    cd "${PROJECT_ROOT}"
    PYTHON="${PROJECT_ROOT}/backend/.venv/bin/python"
    if [[ ! -x "${PYTHON}" ]]; then
        PYTHON="python3"
    fi
    "${PYTHON}" backend/scripts/maintenance_cron.py \
        --db-path backend/.deer-flow/checkpoints.db \
        --artifact-root artifacts \
        --keep-per-thread "${KEEP_PER_THREAD}" \
        --disk-threshold "${DISK_THRESHOLD}" \
        --output-dir "${REPORT_DIR}" \
        2>&1

    MAINTENANCE_EXIT=$?
    echo ""
    echo "=== Maintenance Exit Code: ${MAINTENANCE_EXIT} ==="
} >> "${RUN_LOG}" 2>&1

# ── Parse report for alerts ─────────────────────────────────────────────────
LATEST_REPORT="${REPORT_DIR}/latest.json"
ALERT_MSG=""
ALERT_SEVERITY="warning"

if [[ -L "${LATEST_REPORT}" && -f "${LATEST_REPORT}" ]]; then
    REPORT_PATH="$(readlink "${LATEST_REPORT}")"
    FULL_REPORT="${REPORT_DIR}/${REPORT_PATH}"

    if [[ -f "${FULL_REPORT}" ]]; then
        # Check disk alerts
        PYTHON="${PROJECT_ROOT}/backend/.venv/bin/python"
        if [[ ! -x "${PYTHON}" ]]; then
            PYTHON="python3"
        fi
        ALERT_COUNT=$("${PYTHON}" -c "
import json, sys
try:
    data = json.load(open('${FULL_REPORT}'))
    print(data.get('disk', {}).get('alert_count', 0))
except Exception:
    print('0')
" 2>/dev/null || echo "0")

        if [[ "${ALERT_COUNT}" -gt 0 ]]; then
            ALERT_MSG="🚨 *DeerFlow Disk Alert* — ${ALERT_COUNT} path(s) above ${DISK_THRESHOLD}% threshold"
            ALERT_SEVERITY="danger"
        fi

        # Check checkpoint cleanup results
        DELETED_CHECKPOINTS=$("${PYTHON}" -c "
import json, sys
try:
    data = json.load(open('${FULL_REPORT}'))
    print(data.get('checkpoints', {}).get('cleanup', {}).get('deleted_checkpoints', 0))
except Exception:
    print('0')
" 2>/dev/null || echo "0")

        if [[ "${DELETED_CHECKPOINTS}" -gt 0 ]]; then
            if [[ -n "${ALERT_MSG}" ]]; then
                ALERT_MSG="${ALERT_MSG}
🧹 Cleaned ${DELETED_CHECKPOINTS} old checkpoints"
            else
                ALERT_MSG="🧹 *DeerFlow Maintenance* — Cleaned ${DELETED_CHECKPOINTS} old checkpoints"
            fi
        fi
    fi
fi

# ── Send alerts ─────────────────────────────────────────────────────────────
SEND_ALERT=false

if [[ ${MAINTENANCE_EXIT} -ne 0 ]]; then
    ALERT_MSG="🚨 *DeerFlow Maintenance Failed* — exit code ${MAINTENANCE_EXIT}
${ALERT_MSG}"
    ALERT_SEVERITY="danger"
    SEND_ALERT=true
elif [[ -n "${ALERT_MSG}" ]]; then
    SEND_ALERT=true
fi

if [[ "${SEND_ALERT}" == "true" ]]; then
    # Log alert
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ${ALERT_MSG}" >> "${ALERT_LOG}"

    # Slack alert
    if [[ -n "${SLACK_WEBHOOK_URL}" ]]; then
        PAYLOAD=$(cat <<EOF
{
    "text": "${ALERT_MSG}",
    "attachments": [{
        "color": "${ALERT_SEVERITY}",
        "fields": [
            {"title": "Project", "value": "deer-flow", "short": true},
            {"title": "Report", "value": "${REPORT_FILE}", "short": true}
        ],
        "footer": "DeerFlow Maintenance",
        "ts": $(date +%s)
    }]
}
EOF
)
        curl -s -X POST "${SLACK_WEBHOOK_URL}" \
            -H 'Content-type: application/json' \
            -d "${PAYLOAD}" > /dev/null 2>&1 || true
    fi

    # Email alert (requires `mail` command)
    if [[ -n "${ALERT_EMAIL}" ]] && command -v mail >/dev/null 2>&1; then
        echo "${ALERT_MSG}" | mail -s "[DeerFlow] Maintenance Alert" "${ALERT_EMAIL}" || true
    fi
fi

# ── Cleanup old logs (keep 30 days) ─────────────────────────────────────────
find "${LOG_DIR}" -name 'maintenance_cron_*.log' -mtime +30 -delete 2>/dev/null || true

exit ${MAINTENANCE_EXIT}
