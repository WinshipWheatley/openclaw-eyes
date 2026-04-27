#!/usr/bin/env bash
set -euo pipefail

# Short-lived sync window for Legal planning docs (PC -> Mac)
# Runs for a maximum of 20 minutes (1200 seconds), checking every 60 seconds.

SOURCE_DIR="/home/openclaw/docs/planning/openclaw_legal/law_program/"
SYNC_CMD=(/home/openclaw/mac_eyes/Launchers/sync_legal_planning_to_mac.sh --apply)
LOG_FILE="/tmp/openclaw_legal_planning_sync_window.log"
LOCK_FILE="/tmp/openclaw_legal_planning_sync.lock"
REF_FILE="/tmp/openclaw_legal_planning_sync.ref"

MAX_DURATION_SEC=${MAX_DURATION_SEC:-1200}
CHECK_INTERVAL_SEC=${CHECK_INTERVAL_SEC:-60}

log() {
  echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"
}

if [[ -f "$LOCK_FILE" ]]; then
  pid=$(cat "$LOCK_FILE")
  if ps -p "$pid" > /dev/null 2>&1; then
    echo "Sync window already running (PID: $pid). Exiting."
    exit 0
  else
    echo "Stale lock file found for PID $pid. Cleaning up."
    rm -f "$LOCK_FILE"
  fi
fi

echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"; log "Sync window closed."' EXIT

log "Starting Legal planning sync window for ${MAX_DURATION_SEC}s (checking every ${CHECK_INTERVAL_SEC}s)"

start_time=$(date +%s)

log "Running initial sync..."
if "${SYNC_CMD[@]}" >> "$LOG_FILE" 2>&1; then
    log "Initial sync successful."
else
    log "Initial sync failed."
fi
touch "$REF_FILE"

while true; do
  current_time=$(date +%s)
  if [[ $((current_time - start_time)) -ge $MAX_DURATION_SEC ]]; then
    break
  fi

  # Check if any .md file is newer than our reference file
  CHANGED=$(find "$SOURCE_DIR" -type f -name "*.md" -newer "$REF_FILE" -print -quit || true)

  if [[ -n "$CHANGED" ]]; then
    log "Changes detected (e.g., $CHANGED). Syncing..."
    # Update reference file before sync to avoid missing files modified during sync
    touch "$REF_FILE"
    if "${SYNC_CMD[@]}" >> "$LOG_FILE" 2>&1; then
      log "Sync successful."
    else
      log "Sync failed. Check $LOG_FILE for details."
    fi
  fi

  sleep "$CHECK_INTERVAL_SEC"
done

log "Max duration reached ($MAX_DURATION_SEC seconds). Exiting."
