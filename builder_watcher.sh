#!/bin/bash
POLL_INTERVAL=20
STATUS_FILE="/home/openclaw/polish_loop/status.json"
PROMPT_FILE="/home/openclaw/polish_loop/POLISH_PROMPT.md"
LOG_FILE="/home/openclaw/builder_watcher.log"
MAX_LAUNCHES=3
CODING_RUNNER="${CODING_RUNNER:-claude}"

# NOTE: Watcher timeout (900s) intentionally exceeds Orchestrator BUILDER_TIMEOUT (600s).
# Orchestrator parks the task at 600s. Watcher's 900s is a last-resort kill for
# cases where Orchestrator itself is unresponsive. Do not align these values.

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

LAST_STATE=""
LAUNCH_COUNT=0
PARKED=0

log "=== builder_watcher restarted (PID $$) ==="
source /home/openclaw/.chief.env
export PATH="/home/openclaw/.nvm/versions/node/v24.14.0/bin:$PATH"

# PID lock — prevent multiple instances
LOCKFILE="/tmp/builder_watcher.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ABORT: builder_watcher already running (PID lock)" >> "$LOG_FILE"; exit 1; }
echo $$ > "$LOCKFILE"

while true; do
  status=$(python3 -c "import json; d=json.load(open('$STATUS_FILE')); print(d.get('status',''))" 2>/dev/null)
  log "Polled status: '$status'"

  if [ "$status" != "pc_turn" ]; then
    if [ "$LAUNCH_COUNT" -gt 0 ]; then
      log "RESET: State changed to '$status'. Clearing launch counter."
    fi
    LAUNCH_COUNT=0
    PARKED=0
  fi

  if [ "$status" = "pc_turn" ] && [ "$LAST_STATE" != "pc_turn" ]; then
    # Guard: skip launch if the selected runner is already running (crash-restart safety)
    if [ "$CODING_RUNNER" = "codex" ]; then
      prompt_guard_text="$(head -c 120 "$PROMPT_FILE" | tr '\n' ' ' | sed 's/[[:space:]][[:space:]]*/ /g')"
      runner_guard_pattern="codex .*$(printf '%s' "$prompt_guard_text" | sed 's/[][(){}.^$+*?|\\]/\\&/g')"
    else
      runner_guard_pattern="claude.*POLISH_PROMPT"
    fi
    if pgrep -f "$runner_guard_pattern" >/dev/null 2>&1; then
      log "SKIP: pc_turn transition detected but $CODING_RUNNER session already running — skipping launch"
      LAST_STATE="$status"
      sleep "$POLL_INTERVAL"
      continue
    fi
    log "LAUNCH: Starting Builder (transition from '$LAST_STATE' to 'pc_turn')"
    if [ "$CODING_RUNNER" = "codex" ]; then
      cd /home/openclaw && timeout 900 codex "$(cat "$PROMPT_FILE")" >> "$LOG_FILE" 2>&1
    else
      cd /home/openclaw && timeout 900 claude --model claude-sonnet-4-5 --dangerously-skip-permissions < "$PROMPT_FILE" >> "$LOG_FILE" 2>&1
    fi
    exit_code=$?
    if [ "$exit_code" -eq 124 ]; then
      log "BUILDER: Session TIMED OUT after 900s (exit=124)"
    else
      log "BUILDER: Session ended (exit=$exit_code)"
    fi
    LAUNCH_COUNT=$(( LAUNCH_COUNT + 1 ))
    if [ "$LAUNCH_COUNT" -ge "$MAX_LAUNCHES" ]; then
      log "ERROR: Max launches ($MAX_LAUNCHES) reached for this pc_turn cycle. Parking. Manual intervention required."
      PARKED=1
    fi
  elif [ "$status" = "pc_turn" ] && [ "$LAST_STATE" = "pc_turn" ]; then
    if [ "$PARKED" -eq 0 ]; then
      log "HOLD: Status still pc_turn after Builder exit. Waiting for state change before re-launch."
    fi
  fi

  LAST_STATE="$status"
  sleep "$POLL_INTERVAL"
done
