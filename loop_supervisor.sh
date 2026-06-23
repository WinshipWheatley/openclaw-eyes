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
#   5. ceo_briefing_worker.py           (PC — resilient 8:00 AM EST briefing sender)
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

# NOTE (2026-06-23): the orchestrator is NO LONGER supervised here. It moved from a standing
# poll loop to an EVENT-TRIGGERED model — `orchestrator.py --loop` is deprecated/disabled and
# exits 2, so supervising it here just thrashed (RESTART FAILED every cycle). The orchestrator is
# now driven by a cron tick calling `orchestrator.py --once` (one Phase-C ledger event per tick).
# See Operator/POLISH-LOOP-REVIVAL-PACKET.md.

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

check_ceo_briefing_worker() {
    if pgrep -f "ceo_briefing_worker.py" > /dev/null 2>&1; then
        return 0
    fi
    log "DEAD: ceo_briefing_worker.py not running — restarting"
    cd /home/openclaw
    setsid nohup /home/openclaw/chief_env/bin/python /home/openclaw/ceo_briefing_worker.py >> /mnt/c/OpenClaw/logs/ceo_briefing_worker.out 2>&1 &
    sleep 2
    if pgrep -f "ceo_briefing_worker.py" > /dev/null 2>&1; then
        log "RESTART OK: ceo_briefing_worker.py (PID $(pgrep -f 'ceo_briefing_worker.py' | head -1))"
    else
        log "RESTART FAILED: ceo_briefing_worker.py — manual intervention needed"
    fi
}

check_mac_watcher() {
    # Check via SSH if the Mac loop_watcher is alive
    # Prefer auto-restart via SSH. If restart fails, fall back to manual warning.
    local mac_alive
    mac_alive=$(ssh -o ConnectTimeout=5 -o BatchMode=yes mac \
        'pgrep -f loop_watcher.sh > /dev/null 2>&1 && echo "yes" || echo "no"' 2>/dev/null || echo "unreachable")

    if [ "$mac_alive" = "yes" ]; then
        return 0
    elif [ "$mac_alive" = "unreachable" ]; then
        log "WARN: Mac unreachable via SSH — cannot check loop_watcher"
    else
        log "WARN: Mac loop_watcher.sh is DEAD — attempting SSH restart"
        ssh -o ConnectTimeout=8 -o BatchMode=yes mac \
            'cd ~/Eyes && nohup bash loop_watcher.sh >> ~/Eyes/loop_watcher.out 2>&1 & disown' \
            >/dev/null 2>&1
        sleep 2
        mac_alive=$(ssh -o ConnectTimeout=5 -o BatchMode=yes mac \
            'pgrep -f loop_watcher.sh > /dev/null 2>&1 && echo "yes" || echo "no"' 2>/dev/null || echo "unreachable")

        if [ "$mac_alive" = "yes" ]; then
            log "RESTART OK: Mac loop_watcher.sh restarted via SSH"
            return 0
        fi

        log "RESTART FAILED: Mac loop_watcher.sh still down after SSH restart attempt"
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
    # Only the (deprecated) standing-loop daemon should ever be a duplicate; transient
    # `orchestrator.py --once` cron ticks are short-lived and must NOT be counted/killed.
    local orch_count
    orch_count=$(pgrep -fc "orchestrator.py --loop" 2>/dev/null || echo 0)
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

# --- Queue balancer: maintain healthy tier mix ---

run_queue_balancer() {
    # Runs every BALANCE_EVERY cycles (~10 min with INTERVAL=60).
    # Generates easy quick/surgical tasks when queue is all hard tasks.
    local result
    result=$(python3 /home/openclaw/queue_balancer.py --apply 2>&1)
    if echo "$result" | grep -q "GENERATED:"; then
        log "BALANCE: $result"
    fi
}

# --- Main loop ---

log "Starting loop supervisor (interval=${INTERVAL}s)"

BALANCE_EVERY=10   # run queue balancer every N cycles
cycle=0

while true; do
    # orchestrator is cron-driven via `--once` now (see note above) — not supervised here
    check_builder_watcher
    check_dashboard_gen
    check_dashboard_watchdog
    check_ceo_briefing_worker
    check_mac_watcher
    check_status_health
    check_duplicates

    cycle=$((cycle + 1))
    if [ $((cycle % BALANCE_EVERY)) -eq 0 ]; then
        run_queue_balancer
    fi

    sleep "$INTERVAL"
done
