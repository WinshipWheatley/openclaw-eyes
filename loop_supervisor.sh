#!/usr/bin/env bash
# loop_supervisor.sh — Process health watchdog for the OpenClaw loop.
#
# Checks every INTERVAL seconds that critical loop processes are alive.
# Restarts any that die. Logs all actions.
#
# Monitored processes:
#   1. orchestrator.py --loop          (PC — state machine)
#   2. builder_watcher.sh              (PC — launches coding runners)
#   3. dashboard_gen.py                (PC — generates VS Code dashboard files)
#   4. loop_dashboard_watchdog.sh      (PC — keeps dashboard_gen alive)
#
# Mac loop_watcher.sh is NOT monitored here because it must be started
# from a local Mac terminal (Claude CLI auth requires macOS Keychain).
# If it dies, supervisor logs a warning but cannot auto-restart it.
#
# Usage:
#   setsid nohup bash loop_supervisor.sh >> /mnt/c/OpenClaw/logs/supervisor.out 2>&1 &

set -euo pipefail

INTERVAL=60  # seconds between health checks
LOG="/mnt/c/OpenClaw/logs/supervisor.log"
MAX_LOG_LINES=500

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [supervisor] $1"
    echo "$msg" >> "$LOG"
    # Trim log if too long
    if [ -f "$LOG" ]; then
        local lines
        lines=$(wc -l < "$LOG" 2>/dev/null || echo 0)
        if [ "$lines" -gt "$MAX_LOG_LINES" ]; then
            tail -n "$((MAX_LOG_LINES / 2))" "$LOG" > "${LOG}.tmp" && mv "${LOG}.tmp" "$LOG"
        fi
    fi
}

# --- Process checks ---

check_orchestrator() {
    if pgrep -f "orchestrator.py --loop" > /dev/null 2>&1; then
        return 0
    fi
    log "DEAD: orchestrator.py not running — restarting"
    cd /home/openclaw
    setsid nohup python3 polish_loop/orchestrator.py --loop >> /mnt/c/OpenClaw/logs/orchestrator.out 2>&1 &
    sleep 2
    if pgrep -f "orchestrator.py --loop" > /dev/null 2>&1; then
        log "RESTART OK: orchestrator.py (PID $(pgrep -f 'orchestrator.py --loop' | head -1))"
    else
        log "RESTART FAILED: orchestrator.py — manual intervention needed"
    fi
}

check_builder_watcher() {
    if pgrep -f "builder_watcher.sh" > /dev/null 2>&1; then
        return 0
    fi
    log "DEAD: builder_watcher.sh not running — restarting"
    cd /home/openclaw
    setsid nohup bash builder_watcher.sh >> /mnt/c/OpenClaw/logs/builder_watcher.out 2>&1 &
    sleep 2
    if pgrep -f "builder_watcher.sh" > /dev/null 2>&1; then
        log "RESTART OK: builder_watcher.sh (PID $(pgrep -f 'builder_watcher.sh' | head -1))"
    else
        log "RESTART FAILED: builder_watcher.sh — manual intervention needed"
    fi
}

check_dashboard_gen() {
    if pgrep -f "dashboard_gen.py" > /dev/null 2>&1; then
        return 0
    fi
    log "DEAD: dashboard_gen.py not running — restarting"
    cd /home/openclaw
    setsid nohup python3 dashboard_gen.py >> /mnt/c/OpenClaw/logs/dashboard_gen.out 2>&1 &
    sleep 2
    if pgrep -f "dashboard_gen.py" > /dev/null 2>&1; then
        log "RESTART OK: dashboard_gen.py (PID $(pgrep -f 'dashboard_gen.py' | head -1))"
    else
        log "RESTART FAILED: dashboard_gen.py — manual intervention needed"
    fi
}

check_dashboard_watchdog() {
    if pgrep -f "loop_dashboard_watchdog.sh" > /dev/null 2>&1; then
        return 0
    fi
    log "DEAD: loop_dashboard_watchdog.sh not running — restarting"
    cd /home/openclaw
    setsid nohup bash loop_dashboard_watchdog.sh >> /mnt/c/OpenClaw/logs/dashboard_watchdog.out 2>&1 &
    sleep 2
    if pgrep -f "loop_dashboard_watchdog.sh" > /dev/null 2>&1; then
        log "RESTART OK: loop_dashboard_watchdog.sh (PID $(pgrep -f 'loop_dashboard_watchdog.sh' | head -1))"
    else
        log "RESTART FAILED: loop_dashboard_watchdog.sh — manual intervention needed"
    fi
}

check_mac_watcher() {
    # Check via SSH if the Mac loop_watcher is alive
    # We CANNOT restart it — it must be started from a local Mac terminal
    local mac_alive
    mac_alive=$(ssh -o ConnectTimeout=5 -o BatchMode=yes mac \
        'pgrep -f loop_watcher.sh > /dev/null 2>&1 && echo "yes" || echo "no"' 2>/dev/null || echo "unreachable")

    if [ "$mac_alive" = "yes" ]; then
        return 0
    elif [ "$mac_alive" = "unreachable" ]; then
        log "WARN: Mac unreachable via SSH — cannot check loop_watcher"
    else
        log "WARN: Mac loop_watcher.sh is DEAD — requires manual restart from Mac terminal"
        log "WARN: Run on Mac: cd ~/Eyes && nohup bash loop_watcher.sh >> ~/Eyes/loop_watcher.out 2>&1 & disown"
    fi
}

# --- Status file health ---

check_status_health() {
    local status_file="/home/openclaw/polish_loop/status.json"
    if [ ! -f "$status_file" ]; then
        log "WARN: status.json missing"
        return
    fi

    # Check for stale status (stuck in same state for >30 min with no update)
    local age_seconds
    age_seconds=$(python3 -c "
import json, datetime
try:
    d = json.load(open('$status_file'))
    ts = d.get('last_updated', '')
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
        try:
            dt = datetime.datetime.strptime(ts, fmt)
            print(int((datetime.datetime.now() - dt).total_seconds()))
            break
        except ValueError:
            continue
    else:
        print(-1)
except Exception:
    print(-1)
" 2>/dev/null || echo "-1")

    if [ "$age_seconds" -gt 1800 ]; then
        local state
        state=$(python3 -c "
import json
try:
    print(json.load(open('$status_file')).get('status', 'unknown'))
except Exception:
    print('unknown')
" 2>/dev/null || echo "unknown")
        
        # Only warn for active states that shouldn't be stuck
        case "$state" in
            pc_turn|mac_turn)
                log "STALE: status=$state unchanged for $((age_seconds / 60))m — may be stuck"
                ;;
        esac
    fi
}

# --- Duplicate process detection ---

check_duplicates() {
    local orch_count
    orch_count=$(pgrep -fc "orchestrator.py" 2>/dev/null || echo 0)
    if [ "$orch_count" -gt 1 ]; then
        log "WARN: $orch_count orchestrator processes running (expected 1) — killing extras"
        # Keep the oldest (lowest PID), kill the rest
        local pids
        pids=$(pgrep -f "orchestrator.py --loop" | sort -n)
        local keep
        keep=$(echo "$pids" | head -1)
        for pid in $pids; do
            if [ "$pid" != "$keep" ]; then
                kill "$pid" 2>/dev/null && log "Killed duplicate orchestrator PID $pid"
            fi
        done
    fi
}

# --- Main loop ---

log "Starting loop supervisor (interval=${INTERVAL}s)"

while true; do
    check_orchestrator
    check_builder_watcher
    check_dashboard_gen
    check_dashboard_watchdog
    check_mac_watcher
    check_status_health
    check_duplicates
    sleep "$INTERVAL"
done
