#!/usr/bin/env bash
set -euo pipefail

# Lean single-entry startup for Cassandra runtime.
# Starts only Cassandra services and avoids loop/autopilot orchestration.

ROOT="/home/openclaw"
LOG_DIR="/mnt/c/OpenClaw/logs"
STARTUP_FAILURES=()

cd "$ROOT"

if [ -f "$HOME/chief_env/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$HOME/chief_env/bin/activate"
fi

if [ -f "$ROOT/.chief.env" ]; then
    # shellcheck disable=SC1091
    source "$ROOT/.chief.env"
fi

mkdir -p "$LOG_DIR"

PYTHON_BIN="$(command -v python || true)"
SYSTEMD_RUN_BIN="$(command -v systemd-run || true)"
SYSTEMCTL_BIN="$(command -v systemctl || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: no python executable found after venv activation" >&2
    exit 1
fi

required_env=(
    CASSANDRA_BOT_TOKEN
    TELEGRAM_AUTHORIZED_USER_ID
)

for env_name in "${required_env[@]}"; do
    if [ -z "${!env_name:-}" ]; then
        echo "ERROR: required environment variable '$env_name' is not set" >&2
        exit 1
    fi
done

log_startup() {
    local log_path="$1"
    local message="$2"
    printf '[startup] %s | %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$message" >> "$log_path"
}

systemd_user_available() {
    [ -n "$SYSTEMD_RUN_BIN" ] && [ -n "$SYSTEMCTL_BIN" ] && systemctl --user is-active default.target >/dev/null 2>&1
}

start_py_nohup() {
    local script="$1"
    local log_path="$2"
    local pid=""

    log_startup "$log_path" "starting $script via nohup fallback using $PYTHON_BIN"
    nohup "$PYTHON_BIN" -u "$ROOT/$script" </dev/null >> "$log_path" 2>&1 &
    pid="$!"
    disown "$pid" 2>/dev/null || true

    sleep 2
    if ps -p "$pid" >/dev/null 2>&1; then
        log_startup "$log_path" "confirmed running with pid $pid"
        echo "started: $script (pid $pid)"
        return 0
    fi

    log_startup "$log_path" "nohup process exited before verification window closed"
    return 1
}

start_py() {
    local pattern="$1"
    local script="$2"
    local log_name="$3"
    local log_path="$LOG_DIR/$log_name"
    local main_pid=""
    local unit_name=""

    case "$script" in
        cassandra_listener.py) unit_name="cassandra-listener.service" ;;
        cassandra_watcher.py) unit_name="cassandra-watcher.service" ;;
        cassandra_briefing_scheduler.py) unit_name="cassandra-briefing-scheduler.service" ;;
        *) unit_name="" ;;
    esac

    if systemd_user_available && [ -n "$unit_name" ] && systemctl --user cat "$unit_name" >/dev/null 2>&1; then
        log_startup "$log_path" "restarting $script via systemd user unit $unit_name"
        if systemctl --user restart "$unit_name" >/dev/null 2>&1; then
            sleep 2
            if systemctl --user is-active "$unit_name" >/dev/null 2>&1; then
                main_pid="$(systemctl --user show "$unit_name" --property MainPID --value 2>/dev/null || true)"
                log_startup "$log_path" "confirmed running via $unit_name pid ${main_pid:-unknown}"
                echo "started: $script (service $unit_name pid ${main_pid:-unknown})"
                return 0
            fi
            log_startup "$log_path" "systemd service $unit_name exited before verification window closed"
            systemctl --user status "$unit_name" --no-pager >> "$log_path" 2>&1 || true
        else
            log_startup "$log_path" "systemctl restart failed for $unit_name"
        fi
    fi

    [ -n "$SYSTEMCTL_BIN" ] && [ -n "$unit_name" ] && systemctl --user stop "$unit_name" >/dev/null 2>&1 || true
    [ -n "$SYSTEMCTL_BIN" ] && [ -n "$unit_name" ] && systemctl --user reset-failed "$unit_name" >/dev/null 2>&1 || true
    pkill -f "$pattern" 2>/dev/null || true
    : > "$log_path"

    if start_py_nohup "$script" "$log_path"; then
        return 0
    fi

    STARTUP_FAILURES+=("$script")
    return 1
}

start_py "cassandra_listener.py" "cassandra_listener.py" "cassandra_listener.out" || true
start_py "cassandra_watcher.py" "cassandra_watcher.py" "cassandra_watcher.out" || true
start_py "cassandra_briefing_scheduler.py" "cassandra_briefing_scheduler.py" "cassandra_briefing_scheduler.out" || true

if [ "${#STARTUP_FAILURES[@]}" -gt 0 ]; then
    echo "Cassandra core startup finished with failures: ${STARTUP_FAILURES[*]}" >&2
    exit 1
fi

echo "Cassandra core startup complete."
