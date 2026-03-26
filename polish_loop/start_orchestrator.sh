#!/usr/bin/env bash
# start_orchestrator.sh
# Launches orchestrator.py as a nohup background daemon.
# Safe to run from any directory. Creates a PID file at polish_loop/orchestrator.pid.
# Logs to /mnt/c/OpenClaw/logs/orchestrator.log (same file orchestrator.py writes to).

set -euo pipefail

LOOP_DIR="/home/openclaw/polish_loop"
VENV="/home/openclaw/chief_env/bin/activate"
PID_FILE="$LOOP_DIR/orchestrator.pid"
LOG_FILE="/mnt/c/OpenClaw/logs/orchestrator.log"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[start_orchestrator] Already running (PID $PID). Exiting."
        exit 0
    else
        echo "[start_orchestrator] Stale PID file found (PID $PID not running). Removing."
        rm -f "$PID_FILE"
    fi
fi

# Source venv and launch
source "$VENV"
nohup python3 "$LOOP_DIR/orchestrator.py" >> "$LOG_FILE" 2>&1 &
ORCH_PID=$!
echo "$ORCH_PID" > "$PID_FILE"
echo "[start_orchestrator] Orchestrator started (PID $ORCH_PID). Log: $LOG_FILE"
