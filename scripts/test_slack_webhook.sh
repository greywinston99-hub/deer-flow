#!/bin/bash
# Test Slack webhook integration for DeerFlow maintenance alerts.
#
# Usage:
#   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/XXX/YYY/ZZZ"
#   bash scripts/test_slack_webhook.sh
#
# Without SLACK_WEBHOOK_URL set, prints the payload to stdout for inspection.

set -euo pipefail

WEBHOOK="${SLACK_WEBHOOK_URL:-}"
TIMESTAMP=$(date +%s)

PAYLOAD=$(cat <<EOF
{
  "text": "🧪 *DeerFlow Slack Webhook Test*",
  "attachments": [
    {
      "color": "#36a64f",
      "fields": [
        {"title": "Status", "value": "Webhook configured successfully", "short": true},
        {"title": "Project", "value": "deer-flow", "short": true},
        {"title": "Next Run", "value": "Weekly Sun 03:00", "short": false}
      ],
      "footer": "DeerFlow Maintenance",
      "ts": ${TIMESTAMP}
    }
  ]
}
EOF
)

if [[ -z "${WEBHOOK}" ]]; then
    echo "SLACK_WEBHOOK_URL not set. Here's the payload that would be sent:"
    echo ""
    echo "${PAYLOAD}"
    echo ""
    echo "To test with a real webhook, set the URL first:"
    echo "  export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'"
    echo "  bash scripts/test_slack_webhook.sh"
    exit 1
fi

echo "Sending test message to Slack..."
curl -s -X POST "${WEBHOOK}" \
    -H 'Content-type: application/json' \
    -d "${PAYLOAD}"
echo ""
echo "✅ Test message sent. Check your Slack channel."
