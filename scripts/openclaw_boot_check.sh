#!/usr/bin/env bash
# Task 150 boot-integrity assertion and WSL half-boot detector.
#
# If this script reports that /run/dbus/system_bus_socket is missing, do not
# try to repair D-Bus inside the half-booted distro. From an operator-owned
# PowerShell window run `wsl --shutdown` once, then reopen Ubuntu-E. This script
# never shuts down/terminates a distro, kills a process, restarts a service, or
# changes enablement. It may START an enabled-but-inactive contract unit.
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=scripts/openclaw_boot_manifest.sh
source "${SCRIPT_DIR}/openclaw_boot_manifest.sh"

SYSTEMCTL="${OPENCLAW_BOOT_SYSTEMCTL:-systemctl}"
CURL="${OPENCLAW_BOOT_CURL:-curl}"
PS="${OPENCLAW_BOOT_PS:-ps}"
VOICE="${OPENCLAW_BOOT_VOICE:-${REPO_ROOT}/master_voice.sh}"
SYSTEM_BUS="${OPENCLAW_BOOT_SYSTEM_BUS:-/run/dbus/system_bus_socket}"
MOUNT_PATH="${OPENCLAW_BOOT_MOUNT:-/mnt/e}"
MARKER="${OPENCLAW_BOOT_MARKER:-/mnt/c/OpenClaw/logs/openclaw_boot_integrity.marker}"
STATE_DIR="${OPENCLAW_BOOT_STATE_DIR:-${HOME}/.local/state/openclaw/boot-integrity}"
BOOT_ID_PATH="${OPENCLAW_BOOT_BOOT_ID:-/proc/sys/kernel/random/boot_id}"
CONFLICT_LOG_DIR="${OPENCLAW_BOOT_CONFLICT_LOG_DIR:-/mnt/c/OpenClaw/logs}"
MAX_ATTEMPTS="${OPENCLAW_BOOT_MAX_ATTEMPTS:-36}"
WAIT_BUDGET_SECONDS="${OPENCLAW_BOOT_WAIT_BUDGET_SECONDS:-180}"
RETRY_SECONDS="${OPENCLAW_BOOT_RETRY_SECONDS:-5}"
CONFLICT_WINDOW_SECONDS="${OPENCLAW_BOOT_CONFLICT_WINDOW_SECONDS:-6}"
VOICE_TIMEOUT="${OPENCLAW_BOOT_VOICE_TIMEOUT:-75}"
SYSTEMD_NOTIFY_GRACE="${OPENCLAW_BOOT_SYSTEMD_NOTIFY_GRACE:-15}"

source_name=manual
stale_distro=0
stale_distro_unknown=0

if [[ ! "$MAX_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] || [[ ! "$WAIT_BUDGET_SECONDS" =~ ^[1-9][0-9]*$ ]]; then
  printf 'ERROR: retry budget must use positive integer attempts/seconds.\n' >&2
  exit 64
fi

usage() {
  printf 'Usage: %s [--source user-systemd|windows-task|manual] [--stale-distro-running|--stale-distro-unknown]\n' "$0"
}

while (($#)); do
  case "$1" in
    --source)
      if (($# < 2)); then
        usage >&2
        exit 64
      fi
      source_name="$2"
      shift
      ;;
    --stale-distro-running)
      stale_distro=1
      ;;
    --stale-distro-unknown)
      stale_distro_unknown=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'ERROR: unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 64
      ;;
  esac
  shift
done

while IFS= read -r running_distro; do
  if [[ "$running_distro" == Ubuntu ]]; then
    stale_distro=1
  fi
done < <(printf '%s' "${OPENCLAW_BOOT_RUNNING_DISTROS:-}" | tr ',' '\n')

run_sleep() {
  local seconds="$1"
  if [[ "$seconds" == 0 ]]; then
    return 0
  elif [[ -n "${OPENCLAW_BOOT_SLEEP:-}" ]]; then
    "${OPENCLAW_BOOT_SLEEP}" "$seconds"
  elif [[ "$seconds" != 0 ]]; then
    sleep "$seconds"
  fi
}

write_marker() {
  local status="$1"
  local summary="$2"
  local remedy="${3:--}"
  local marker_dir
  local temp
  marker_dir="$(dirname -- "$MARKER")"
  mkdir -p -- "$marker_dir"
  temp="${MARKER}.tmp.$$"
  umask 077
  {
    printf 'OPENCLAW BOOT INTEGRITY\n'
    printf 'STATUS=%s\n' "$status"
    printf 'OBSERVED_AT=%s\n' "$(date -Is)"
    printf 'SOURCE=%s\n' "$source_name"
    printf 'EVIDENCE=%s\n' "$summary"
    printf 'REMEDY=%s\n' "$remedy"
    printf 'READ_ONLY_WARNING=No distro or process was terminated.\n'
  } > "$temp"
  mv -f -- "$temp" "$MARKER"
}

notify_once() {
  local message="$1"
  local boot_id
  local stamp
  local temp
  local lock
  local notify_fd
  mkdir -p -- "$STATE_DIR"
  boot_id="$(head -n 1 "$BOOT_ID_PATH" 2>/dev/null || true)"
  if [[ -z "$boot_id" ]]; then
    boot_id="unknown-$(date +%Y-%m-%d)"
  fi
  stamp="${STATE_DIR}/last-notified-boot-id"
  lock="${STATE_DIR}/notify.lock"
  exec {notify_fd}> "$lock"
  if ! flock -w "$VOICE_TIMEOUT" "$notify_fd"; then
    printf 'notification=lock-timeout marker=%s\n' "$MARKER" >&2
    exec {notify_fd}>&-
    return 1
  fi
  if [[ -r "$stamp" ]] && [[ "$(head -n 1 "$stamp" 2>/dev/null || true)" == "$boot_id" ]]; then
    printf 'notification=already-reported-this-boot\n'
    flock -u "$notify_fd"
    exec {notify_fd}>&-
    return 0
  fi
  if [[ ! -x "$VOICE" ]]; then
    printf 'notification=unavailable command=%s\n' "$VOICE" >&2
    flock -u "$notify_fd"
    exec {notify_fd}>&-
    return 1
  fi
  if printf '%s\n' "$message" | CUDA_VISIBLE_DEVICES="" timeout "$VOICE_TIMEOUT" "$VOICE"; then
    temp="${stamp}.tmp.$$"
    printf '%s\n' "$boot_id" > "$temp"
    mv -f -- "$temp" "$stamp"
    printf 'notification=sent\n'
    flock -u "$notify_fd"
    exec {notify_fd}>&-
    return 0
  fi
  printf 'notification=failed marker=%s\n' "$MARKER" >&2
  flock -u "$notify_fd"
  exec {notify_fd}>&-
  return 1
}

count_conflicts() {
  local total=0
  local count
  local file
  local files=()
  if [[ -n "${OPENCLAW_BOOT_CONFLICT_COUNTER:-}" ]]; then
    "${OPENCLAW_BOOT_CONFLICT_COUNTER}"
    return
  fi
  shopt -s nullglob
  files=("${CONFLICT_LOG_DIR}"/*.out)
  shopt -u nullglob
  for file in "${files[@]}"; do
    count="$(command grep -F -c -- 'Conflict: terminated by other getUpdates' "$file" 2>/dev/null || true)"
    [[ "$count" =~ ^[0-9]+$ ]] || count=0
    total=$((total + count))
  done
  printf '%d\n' "$total"
}

duplicate_pollers() {
  local process_lines
  local line
  local label
  local count
  local matched
  process_lines="$($PS -eo args= 2>/dev/null || true)"
  for label in maestro chief cassandra guardian niles hermes; do
    count=0
    while IFS= read -r line; do
      matched=0
      case "$label:$line" in
        maestro:*maestro_listener.py*) matched=1 ;;
        chief:*chief_listener.py*) matched=1 ;;
        cassandra:*cassandra_listener.py*) matched=1 ;;
        guardian:*chief_guardian_listener.py*) matched=1 ;;
        niles:*producer_listener.py*) matched=1 ;;
        hermes:*run_openclaw_hermes_gateway.py*) matched=1 ;;
      esac
      count=$((count + matched))
    done <<< "$process_lines"
    if (( count > 1 )); then
      printf '%s=%d\n' "$label" "$count"
    fi
  done
}

is_primary_service() {
  local candidate="$1"
  local primary
  for primary in "${OPENCLAW_BOOT_SERVICES[@]}"; do
    [[ "$candidate" == "$primary" ]] && return 0
  done
  return 1
}

join_by_semicolon() {
  local joined=""
  local item
  for item in "$@"; do
    if [[ -n "$joined" ]]; then
      joined+="; "
    fi
    joined+="$item"
  done
  printf '%s\n' "$joined"
}

wait_deadline=$(( $(date +%s) + WAIT_BUDGET_SECONDS ))
attempts_used=0
while [[ ! -e "$SYSTEM_BUS" ]] && (( attempts_used < MAX_ATTEMPTS )); do
  (( $(date +%s) < wait_deadline )) || break
  attempts_used=$((attempts_used + 1))
  (( attempts_used < MAX_ATTEMPTS )) || break
  run_sleep "$RETRY_SECONDS"
done

if [[ ! -e "$SYSTEM_BUS" ]]; then
  bus_summary="WSL system D-Bus is missing at ${SYSTEM_BUS}."
  if (( stale_distro )); then
    bus_summary+=' Stale WSL distro "Ubuntu" is also running.'
  elif (( stale_distro_unknown )); then
    bus_summary+=' The Windows running-distro check failed.'
  fi
  remedy='Run wsl --shutdown from PowerShell once, then reopen Ubuntu-E.'
  write_marker RED "$bus_summary" "$remedy"
  printf 'RED LINE: %s %s\n' "$bus_summary" "$remedy"
  notify_once "OpenClaw boot warning: ${bus_summary} ${remedy}" || true
  exit 2
fi

conflicts_before="$(count_conflicts)"
[[ "$conflicts_before" =~ ^[0-9]+$ ]] || conflicts_before=0

declare -a readiness_failures=()
declare -A start_requested=()
declare -a started_units=()
service_count=0
timers_armed=1
ollama_up=0

while (( attempts_used < MAX_ATTEMPTS )) && (( $(date +%s) < wait_deadline )); do
  attempts_used=$((attempts_used + 1))
  readiness_failures=()
  service_count=0
  timers_armed=1

  if [[ ! -d "$MOUNT_PATH" ]]; then
    readiness_failures+=("mount ${MOUNT_PATH} unavailable")
  fi

  if "$CURL" -fsS --max-time 3 http://127.0.0.1:11434/api/ps >/dev/null 2>&1; then
    ollama_up=1
  else
    ollama_up=0
    readiness_failures+=("ollama API unavailable")
  fi

  for unit in "${OPENCLAW_BOOT_REQUIRED_SERVICES[@]}"; do
    if "$SYSTEMCTL" --user is-active "$unit" >/dev/null 2>&1; then
      if is_primary_service "$unit"; then
        service_count=$((service_count + 1))
      fi
      continue
    fi
    state="$($SYSTEMCTL --user is-enabled "$unit" 2>/dev/null || true)"
    if [[ "$state" == enabled || "$state" == linked || "$state" == linked-runtime ]]; then
      if [[ -z "${start_requested[$unit]+yes}" ]]; then
        "$SYSTEMCTL" --user --no-block start "$unit" >/dev/null 2>&1 || true
        start_requested["$unit"]=yes
        started_units+=("$unit")
        readiness_failures+=("service ${unit} inactive (enabled; start requested)")
      else
        readiness_failures+=("service ${unit} inactive after start request")
      fi
    else
      readiness_failures+=("service ${unit} inactive (${state:-enablement unknown})")
    fi
  done

  for unit in "${OPENCLAW_BOOT_REQUIRED_TIMERS[@]}"; do
    timer_enabled="$($SYSTEMCTL --user is-enabled "$unit" 2>/dev/null || true)"
    if [[ "$timer_enabled" != enabled && "$timer_enabled" != linked && "$timer_enabled" != linked-runtime ]]; then
      timers_armed=0
      readiness_failures+=("timer ${unit} not enabled (${timer_enabled:-unknown})")
      continue
    fi
    if ! "$SYSTEMCTL" --user is-active "$unit" >/dev/null 2>&1; then
      timers_armed=0
      if [[ -z "${start_requested[$unit]+yes}" ]]; then
        "$SYSTEMCTL" --user --no-block start "$unit" >/dev/null 2>&1 || true
        start_requested["$unit"]=yes
        started_units+=("$unit")
        readiness_failures+=("timer ${unit} inactive (start requested)")
      else
        readiness_failures+=("timer ${unit} inactive after start request")
      fi
    fi
  done

  if ((${#readiness_failures[@]} == 0)); then
    break
  fi
  if (( attempts_used < MAX_ATTEMPTS )) && (( $(date +%s) < wait_deadline )); then
    run_sleep "$RETRY_SECONDS"
  fi
done

declare -a warnings=()

while IFS= read -r duplicate; do
  [[ -n "$duplicate" ]] && warnings+=("duplicate poller ${duplicate}")
done < <(duplicate_pollers)

run_sleep "$CONFLICT_WINDOW_SECONDS"
conflicts_after="$(count_conflicts)"
[[ "$conflicts_after" =~ ^[0-9]+$ ]] || conflicts_after=0
if (( conflicts_after > conflicts_before )); then
  warnings+=("getUpdates conflicts grew ${conflicts_before}->${conflicts_after}")
fi

if (( stale_distro )); then
  warnings+=('stale WSL distro "Ubuntu" is running')
elif (( stale_distro_unknown )); then
  warnings+=("Windows running-distro check failed")
fi

failed_units="$($SYSTEMCTL --failed --no-legend --plain 2>/dev/null || true)"
while IFS= read -r failed_line; do
  [[ -z "$failed_line" ]] && continue
  failed_unit="${failed_line%% *}"
  if [[ "$failed_unit" == getty@tty1.service ]]; then
    continue
  fi
  warnings+=("system failure ${failed_unit}")
done <<< "$failed_units"

if ((${#readiness_failures[@]} == 0 && ${#warnings[@]} == 0)) \
  && ((service_count == ${#OPENCLAW_BOOT_SERVICES[@]} && timers_armed == 1 && ollama_up == 1)); then
  success='Fleet up after restart: 10/10 services, ollama warm, timers armed.'
  write_marker GREEN "$success"
  printf '%s\n' "$success"
  if [[ "$source_name" == user-systemd ]]; then
    run_sleep "$SYSTEMD_NOTIFY_GRACE"
  fi
  notify_once "$success" || true
  exit 0
fi

all_findings=("${readiness_failures[@]}" "${warnings[@]}")
summary="$(join_by_semicolon "${all_findings[@]}")"
starts=none
if ((${#started_units[@]} > 0)); then
  starts="$(IFS=,; printf '%s' "${started_units[*]}")"
fi
boundary="No distro or process was terminated. Enabled-dead start requests: ${starts}."
write_marker RED "$summary" "Inspect the named item. ${boundary}"
printf 'RED LINE: boot integrity incomplete: %s. %s\n' "$summary" "$boundary"
notify_once "OpenClaw boot warning: ${summary}. ${boundary}" || true
exit 1
