#!/usr/bin/env bash
# loop_dashboard_watchdog.sh — keeps dashboard_gen.py running
# Checks every 60 seconds, restarts if missing or stale.

set -euo pipefail

GENERATOR="python3 /home/openclaw/dashboard_gen.py"
GENERATOR_PATTERN="dashboard_gen.py"
GENERATOR_LOG="/mnt/c/OpenClaw/logs/dashboard_gen.out"
NOW_FILE="/home/openclaw/mac_eyes/For Winship 1 - Right Now.md"
LOCK_FILE="/tmp/loop_dashboard_watchdog.lock"
POLL_INTERVAL=60
MAX_STALE_SECONDS=180

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    exit 0
fi

# Ensure downstream helpers inherit bot tokens.
if [ -f "/home/openclaw/.chief.env" ]; then
    set -a
    source /home/openclaw/.chief.env
    set +a
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

generator_count() {
    pgrep -fc "$GENERATOR_PATTERN" || true
}

file_age() {
    local path="$1"
    if [ ! -f "$path" ]; then
        echo 999999
        return
    fi
    echo $(( $(date +%s) - $(stat -c %Y "$path") ))
}

dashboards_stale() {
    local now_age
    now_age=$(file_age "$NOW_FILE")
    [ "$now_age" -gt "$MAX_STALE_SECONDS" ]
}

start_generator() {
    setsid nohup $GENERATOR >> "$GENERATOR_LOG" 2>&1 &
    log "dashboard generator started (PID $!)"
}

restart_generator() {
    pkill -f "$GENERATOR_PATTERN" || true
    sleep 2
    start_generator
}

log "dashboard watchdog online"

while true; do
    count=$(generator_count)
    if [ "$count" -eq 0 ]; then
        log "generator missing; starting"
        start_generator
    elif [ "$count" -gt 1 ]; then
        log "duplicate generators ($count); restarting"
        restart_generator
    elif dashboards_stale; then
        log "dashboards stale; restarting generator"
        restart_generator
    fi
    sleep "$POLL_INTERVAL"
done
