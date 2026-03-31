#!/bin/bash
# loop_control.sh — Unified stop/pause/shutdown control for the OpenClaw loop.
# Called from Mac Obsidian buttons via SSH.
#
# Usage:
#   bash loop_control.sh pause           — pause (let current work finish, no new tasks)
#   bash loop_control.sh resume          — unpause
#   bash loop_control.sh graceful-stop   — clean shutdown, wait for builder, save state
#   bash loop_control.sh emergency       — freeze, audit, report to Telegram
#   bash loop_control.sh kill            — kill everything immediately
#   bash loop_control.sh status          — report what's running

set -euo pipefail

STATUS_FILE="/home/openclaw/polish_loop/status.json"
LOG_FILE="/mnt/c/OpenClaw/logs/loop_control.log"
INTERRUPTED_FILE="/home/openclaw/polish_loop/current/interrupted_output.md"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [loop_control] $*" | tee -a "$LOG_FILE"
}

read_status() {
  python3 -c "import json; d=json.load(open('$STATUS_FILE')); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown"
}

set_status() {
  local new_status="$1"
  python3 -c "
import json
from pathlib import Path
p = Path('$STATUS_FILE')
d = json.loads(p.read_text())
d['status'] = '$new_status'
d['last_updated'] = __import__('datetime').datetime.now().isoformat()
p.write_text(json.dumps(d, indent=2))
print('Status set to: $new_status')
" 2>&1
}

# Get PIDs of builder processes (claude or codex under timeout)
get_builder_pids() {
  pgrep -f 'timeout [0-9]+ (claude|codex)' 2>/dev/null || true
}

get_orchestrator_pid() {
  pgrep -f 'python3.*orchestrator\.py' 2>/dev/null || true
}

get_watcher_pid() {
  pgrep -f 'builder_watcher\.sh' 2>/dev/null || true
}

# ── PAUSE ─────────────────────────────────────────────────────────────
do_pause() {
  log "PAUSE requested"
  local current
  current=$(read_status)

  if [ "$current" = "paused" ]; then
    log "Already paused"
    echo "Already paused."
    return
  fi

  # Save what we were doing so resume knows where to go back
  python3 -c "
import json
from pathlib import Path
p = Path('$STATUS_FILE')
d = json.loads(p.read_text())
d['paused_from'] = d.get('status', 'idle')
d['status'] = 'paused'
d['last_updated'] = __import__('datetime').datetime.now().isoformat()
p.write_text(json.dumps(d, indent=2))
" 2>&1

  log "PAUSED (was: $current). Current builder will finish naturally. No new tasks will start."
  echo "Loop paused. Current work continues to completion. No new tasks will start."
  echo "Use 'loop_control.sh resume' to unpause."
}

# ── RESUME ────────────────────────────────────────────────────────────
do_resume() {
  log "RESUME requested"
  local current
  current=$(read_status)

  if [ "$current" != "paused" ] && [ "$current" != "emergency_freeze" ]; then
    log "Not paused (status=$current), nothing to resume"
    echo "Loop is not paused (status=$current)."
    return
  fi

  # Restore previous status
  python3 -c "
import json
from pathlib import Path
p = Path('$STATUS_FILE')
d = json.loads(p.read_text())
prev = d.pop('paused_from', 'idle')
d['status'] = prev
d['last_updated'] = __import__('datetime').datetime.now().isoformat()
p.write_text(json.dumps(d, indent=2))
print(f'Resumed to: {prev}')
" 2>&1

  log "RESUMED"
  echo "Loop resumed."
}

# ── GRACEFUL STOP ─────────────────────────────────────────────────────
do_graceful_stop() {
  log "GRACEFUL STOP requested"

  # Step 1: Pause to prevent new work
  set_status "paused"
  log "Set to paused — no new tasks"

  # Step 2: Wait for active builder (up to 60s)
  local builder_pids wait_count=0
  builder_pids=$(get_builder_pids)

  if [ -n "$builder_pids" ]; then
    log "Waiting for active builder (PIDs: $builder_pids) to finish (max 60s)..."
    echo "Waiting for builder to finish (max 60s)..."
    while [ "$wait_count" -lt 60 ]; do
      builder_pids=$(get_builder_pids)
      [ -z "$builder_pids" ] && break
      sleep 2
      wait_count=$(( wait_count + 2 ))
    done

    builder_pids=$(get_builder_pids)
    if [ -n "$builder_pids" ]; then
      log "Builder still running after 60s — killing (PIDs: $builder_pids)"
      echo "Builder didn't finish in 60s — saving partial work and killing."

      # Save partial output
      {
        echo "# Interrupted Output"
        echo "Interrupted by graceful stop at $(date '+%Y-%m-%d %H:%M:%S')"
        echo "Builder PIDs at interrupt: $builder_pids"
        echo ""
        echo "## Last 50 lines of builder log"
        tail -50 /home/openclaw/builder_watcher.log 2>/dev/null || echo "(no log)"
      } > "$INTERRUPTED_FILE"

      kill $builder_pids 2>/dev/null || true
      sleep 2
      kill -9 $builder_pids 2>/dev/null || true
      log "Builder killed. Partial output saved to $INTERRUPTED_FILE"
    else
      log "Builder finished naturally"
      echo "Builder finished."
    fi
  else
    log "No active builder"
  fi

  # Step 3: Kill orchestrator and watcher
  local orch_pid watcher_pid
  orch_pid=$(get_orchestrator_pid)
  watcher_pid=$(get_watcher_pid)

  [ -n "$orch_pid" ] && { kill $orch_pid 2>/dev/null || true; log "Killed orchestrator (PID $orch_pid)"; }
  [ -n "$watcher_pid" ] && { kill $watcher_pid 2>/dev/null || true; log "Killed watcher (PID $watcher_pid)"; }

  # Step 4: Set stopped status
  set_status "stopped"

  log "GRACEFUL STOP complete"
  echo "Loop stopped cleanly. Use 'start_chief.sh' or the Start button to restart."
}

# ── EMERGENCY ─────────────────────────────────────────────────────────
do_emergency() {
  log "EMERGENCY STOP requested — freezing and auditing"

  # Step 1: Freeze immediately
  python3 -c "
import json
from pathlib import Path
p = Path('$STATUS_FILE')
d = json.loads(p.read_text())
d['paused_from'] = d.get('status', 'idle')
d['status'] = 'emergency_freeze'
d['last_updated'] = __import__('datetime').datetime.now().isoformat()
p.write_text(json.dumps(d, indent=2))
" 2>&1
  log "Status set to emergency_freeze"

  # Step 2: Audit what's running
  local audit_report=""
  audit_report+="=== EMERGENCY AUDIT $(date '+%Y-%m-%d %H:%M:%S') ===\n"

  local builder_pids orch_pid watcher_pid
  builder_pids=$(get_builder_pids)
  orch_pid=$(get_orchestrator_pid)
  watcher_pid=$(get_watcher_pid)

  audit_report+="\nBuilder PIDs: ${builder_pids:-none}\n"
  audit_report+="Orchestrator PID: ${orch_pid:-none}\n"
  audit_report+="Watcher PID: ${watcher_pid:-none}\n"

  # What is the builder doing?
  if [ -n "$builder_pids" ]; then
    for pid in $builder_pids; do
      audit_report+="\n--- Builder PID $pid ---\n"
      local runtime
      runtime=$(ps -o etime= -p "$pid" 2>/dev/null || echo "unknown")
      audit_report+="Runtime: $runtime\n"

      # Check /proc status for stopped state
      local proc_state
      proc_state=$(cat /proc/"$pid"/status 2>/dev/null | grep "^State:" || echo "State: unknown")
      audit_report+="$proc_state\n"

      # Recent file activity
      local recent_files
      recent_files=$(find /home/openclaw -maxdepth 2 -newer /tmp/builder_watcher.lock -name "*.py" -o -name "*.sh" -o -name "*.md" 2>/dev/null | head -10)
      audit_report+="Recently modified files:\n${recent_files:-none}\n"
    done
  fi

  # Last builder log lines
  audit_report+="\n--- Last 20 builder log lines ---\n"
  audit_report+="$(tail -20 /home/openclaw/builder_watcher.log 2>/dev/null || echo '(no log)')\n"

  # Current task
  local task_name
  task_name=$(python3 -c "import json; print(json.load(open('$STATUS_FILE')).get('task_name','unknown'))" 2>/dev/null || echo "unknown")
  audit_report+="\nCurrent task: $task_name\n"

  # Write audit to file
  echo -e "$audit_report" > /mnt/c/OpenClaw/logs/emergency_audit.txt
  log "Audit written to /mnt/c/OpenClaw/logs/emergency_audit.txt"

  # Step 3: Try to send audit to Telegram via Guardian
  python3 -c "
import sys
sys.path.insert(0, '/home/openclaw')
try:
    from chief_sender import send_message
    report = open('/mnt/c/OpenClaw/logs/emergency_audit.txt').read()
    truncated = report[:3500] + '...(truncated)' if len(report) > 3500 else report
    send_message('🚨 EMERGENCY AUDIT\\n\\n' + truncated + '\\n\\nReply: KILL-ALL, RESUME, or check manually.')
    print('Audit sent to Telegram')
except Exception as e:
    print(f'Telegram send failed: {e}')
" 2>&1 || log "Telegram notification failed (non-blocking)"

  echo ""
  echo "=== EMERGENCY FREEZE ACTIVE ==="
  echo "No new work will start. Active processes are still running."
  echo "Audit report: /mnt/c/OpenClaw/logs/emergency_audit.txt"
  echo ""
  echo "Options:"
  echo "  loop_control.sh kill    — kill everything now"
  echo "  loop_control.sh resume  — unfreeze and continue"
  echo "  Review audit report and decide"
  echo ""

  # Step 4: Auto-timeout — kill everything after 5 minutes if still frozen
  (
    sleep 300
    local status
    status=$(python3 -c "import json; print(json.load(open('$STATUS_FILE')).get('status',''))" 2>/dev/null)
    if [ "$status" = "emergency_freeze" ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [loop_control] EMERGENCY AUTO-KILL: 5 min timeout, no response — killing all" >> "$LOG_FILE"
      # Kill builders
      for pid in $(pgrep -f 'timeout [0-9]+ (claude|codex)' 2>/dev/null); do
        kill -9 "$pid" 2>/dev/null || true
      done
      # Kill orchestrator/watcher
      pkill -f 'python3.*orchestrator\.py' 2>/dev/null || true
      pkill -f 'builder_watcher\.sh' 2>/dev/null || true
      python3 -c "
import json; from pathlib import Path
p = Path('$STATUS_FILE')
d = json.loads(p.read_text())
d['status'] = 'stopped'
d['last_updated'] = __import__('datetime').datetime.now().isoformat()
p.write_text(json.dumps(d, indent=2))
" 2>/dev/null
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [loop_control] EMERGENCY AUTO-KILL complete" >> "$LOG_FILE"
    fi
  ) &
  disown
}

# ── KILL EVERYTHING ───────────────────────────────────────────────────
do_kill() {
  log "KILL ALL requested"

  # Kill builders first (most dangerous)
  pkill -9 -f 'timeout [0-9]+ (claude|codex)' 2>/dev/null || true
  pkill -9 -f 'claude.*--print' 2>/dev/null || true
  pkill -9 -f 'codex exec' 2>/dev/null || true

  # Kill orchestrator and watcher
  pkill -f 'python3.*orchestrator\.py' 2>/dev/null || true
  pkill -f 'builder_watcher\.sh' 2>/dev/null || true

  # Kill any loop dashboard/watcher helpers
  pkill -f 'loop_dashboard_gen' 2>/dev/null || true
  pkill -f 'loop_status_watch' 2>/dev/null || true

  # Set status to stopped
  set_status "stopped"

  # Remove PID locks
  rm -f /tmp/builder_watcher.lock 2>/dev/null || true

  log "KILL ALL complete — everything terminated"
  echo "All loop processes killed. Use 'start_chief.sh' to restart."
}

# ── STATUS ────────────────────────────────────────────────────────────
do_status() {
  local status builder_pids orch_pid watcher_pid
  status=$(read_status)
  builder_pids=$(get_builder_pids)
  orch_pid=$(get_orchestrator_pid)
  watcher_pid=$(get_watcher_pid)

  echo "Loop status: $status"
  echo "Orchestrator: ${orch_pid:-not running}"
  echo "Builder watcher: ${watcher_pid:-not running}"
  echo "Active builders: ${builder_pids:-none}"

  if [ -n "$builder_pids" ]; then
    for pid in $builder_pids; do
      local runtime
      runtime=$(ps -o etime= -p "$pid" 2>/dev/null || echo "?")
      echo "  PID $pid running for $runtime"
    done
  fi

  local task_name
  task_name=$(python3 -c "import json; print(json.load(open('$STATUS_FILE')).get('task_name','none'))" 2>/dev/null || echo "unknown")
  echo "Current task: $task_name"
}

# ── MAIN ──────────────────────────────────────────────────────────────
case "${1:-}" in
  pause)          do_pause ;;
  resume)         do_resume ;;
  graceful-stop)  do_graceful_stop ;;
  emergency)      do_emergency ;;
  kill)           do_kill ;;
  status)         do_status ;;
  *)
    echo "Usage: loop_control.sh {pause|resume|graceful-stop|emergency|kill|status}"
    exit 1
    ;;
esac
