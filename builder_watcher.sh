#!/bin/bash
POLL_INTERVAL=20
STATUS_FILE="/home/openclaw/polish_loop/status.json"
PROMPT_FILE="/home/openclaw/polish_loop/POLISH_PROMPT.md"
LOG_FILE="/home/openclaw/builder_watcher.log"
MAX_LAUNCHES=3

if [ -n "${CODING_RUNNER+x}" ]; then
  RUNNER_EXPLICIT=1
  RUNNER_PREFERRED="$CODING_RUNNER"
else
  RUNNER_EXPLICIT=0
  RUNNER_PREFERRED="claude"
fi

# NOTE: Watcher timeout (900s) intentionally exceeds Orchestrator BUILDER_TIMEOUT (600s).
# Orchestrator parks the task at 600s. Watcher's 900s is a last-resort kill for
# cases where Orchestrator itself is unresponsive. Do not align these values.

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

guard_pattern_for_runner() {
  local runner="$1"
  if [ "$runner" = "codex" ]; then
    local prompt_guard_text
    prompt_guard_text="$(head -c 120 "$PROMPT_FILE" | tr '\n' ' ' | sed 's/[[:space:]][[:space:]]*/ /g')"
    printf 'codex .*%s' "$(printf '%s' "$prompt_guard_text" | sed 's/[][(){}.^$+*?|\\]/\\&/g')"
  else
    printf 'claude.*POLISH_PROMPT'
  fi
}

launch_runner_once() {
  local runner="$1"
  if [ "$runner" = "codex" ]; then
    cd /home/openclaw && timeout 900 codex "$(cat "$PROMPT_FILE")" >> "$LOG_FILE" 2>&1
  else
    cd /home/openclaw && timeout 900 claude --model claude-sonnet-4-5 --dangerously-skip-permissions < "$PROMPT_FILE" >> "$LOG_FILE" 2>&1
  fi
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
    launch_runner="$RUNNER_PREFERRED"
    fallback_runner="codex"
    [ "$launch_runner" = "codex" ] && fallback_runner="claude"

    # Guard: skip launch if the selected runner is already running (crash-restart safety)
    runner_guard_pattern="$(guard_pattern_for_runner "$launch_runner")"
    if pgrep -f "$runner_guard_pattern" >/dev/null 2>&1; then
      log "SKIP: pc_turn transition detected but $launch_runner session already running — skipping launch"
      LAST_STATE="$status"
      sleep "$POLL_INTERVAL"
      continue
    fi
    log "LAUNCH: Starting Builder with runner=$launch_runner (transition from '$LAST_STATE' to 'pc_turn')"
    launch_start_ts=$(date +%s)
    launch_runner_once "$launch_runner"
    exit_code=$?
    launch_elapsed=$(( $(date +%s) - launch_start_ts ))

    if [ "$RUNNER_EXPLICIT" -eq 0 ] && [ "$exit_code" -ne 0 ] && [ "$exit_code" -ne 124 ] && [ "$launch_elapsed" -le 20 ]; then
      fallback_guard_pattern="$(guard_pattern_for_runner "$fallback_runner")"
      if pgrep -f "$fallback_guard_pattern" >/dev/null 2>&1; then
        log "FALLBACK-SKIP: runner=$fallback_runner already running; keeping primary exit=$exit_code"
      else
        log "FALLBACK: runner=$launch_runner failed fast (exit=$exit_code, elapsed=${launch_elapsed}s); trying runner=$fallback_runner once"
        launch_runner="$fallback_runner"
        launch_start_ts=$(date +%s)
        launch_runner_once "$launch_runner"
        exit_code=$?
        launch_elapsed=$(( $(date +%s) - launch_start_ts ))
        log "FALLBACK: runner=$launch_runner completed (exit=$exit_code, elapsed=${launch_elapsed}s)"
      fi
    else
      log "LAUNCH: runner=$launch_runner completed (exit=$exit_code, elapsed=${launch_elapsed}s)"
    fi

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
