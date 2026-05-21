#!/bin/zsh

set -euo pipefail

APP_PATH="/Library/Input Methods/WeType.app"
STATE_FILE="${TMPDIR:-/tmp}/wetype-wake-watch.last"
LOCK_DIR="${TMPDIR:-/tmp}/wetype-wake-watch.lock"
MAX_WAKE_AGE_SECONDS=180

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  exit 0
fi

cleanup() {
  rmdir "${LOCK_DIR}" 2>/dev/null || true
}

trap cleanup EXIT

if [[ ! -d "${APP_PATH}" ]]; then
  exit 0
fi

last_wake_line="$(
  pmset -g log \
    | awk '/^[0-9-]{4}-[0-9-]{2}-[0-9-]{2} [0-9:]{8} [+-][0-9]{4} Wake[[:space:]]+Wake from / { line = $0 } END { if (line) print line }'
)"

if [[ -z "${last_wake_line}" ]]; then
  exit 0
fi

wake_timestamp="$(printf '%s\n' "${last_wake_line}" | cut -c1-19)"
wake_epoch="$(date -j -f '%Y-%m-%d %H:%M:%S' "${wake_timestamp}" '+%s' 2>/dev/null || true)"

if [[ -z "${wake_epoch}" ]]; then
  exit 0
fi

last_seen_epoch=0
if [[ -f "${STATE_FILE}" ]]; then
  last_seen_epoch="$(cat "${STATE_FILE}" 2>/dev/null || echo 0)"
fi

if (( wake_epoch <= last_seen_epoch )); then
  exit 0
fi

printf '%s\n' "${wake_epoch}" > "${STATE_FILE}"

now_epoch="$(date '+%s')"
if (( now_epoch - wake_epoch > MAX_WAKE_AGE_SECONDS )); then
  exit 0
fi

if pgrep -x WeType >/dev/null 2>&1; then
  killall WeType || true
  sleep 1
fi

open "${APP_PATH}" || true
