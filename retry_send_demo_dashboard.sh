#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="/mnt/c/OpenClaw/logs/demo_dashboard_retry.log"
MAX_ATTEMPTS=5
SLEEP_SECONDS=600

cd /home/openclaw
set -a
[ -f /home/openclaw/.chief.env ] && . /home/openclaw/.chief.env
set +a

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$ts] attempt=$attempt sending dashboard email" >> "$LOG_FILE"

  if /home/openclaw/chief_env/bin/python /home/openclaw/send_demo_dashboard.py >> "$LOG_FILE" 2>&1; then
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$ts] success on attempt=$attempt" >> "$LOG_FILE"
    exit 0
  fi

  if [ "$attempt" -lt "$MAX_ATTEMPTS" ]; then
    sleep "$SLEEP_SECONDS"
  fi
done

ts="$(date '+%Y-%m-%d %H:%M:%S')"
echo "[$ts] exhausted retries (max=$MAX_ATTEMPTS)" >> "$LOG_FILE"
exit 1
