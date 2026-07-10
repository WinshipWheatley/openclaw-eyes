#!/usr/bin/env bash
# Task 150 enablement assertion (VERIFY ONLY).
#
# The July 9 incident was a WSL half-boot with a missing system D-Bus, not
# disabled units. This script deliberately never enables or starts anything.
# A dead bus is UNKNOWN, never misreported as disabled. When genuine drift is
# observable it prints the exact command an operator may choose to run.
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/openclaw_boot_manifest.sh
source "${SCRIPT_DIR}/openclaw_boot_manifest.sh"

SYSTEMCTL="${OPENCLAW_BOOT_SYSTEMCTL:-systemctl}"
LOGINCTL="${OPENCLAW_BOOT_LOGINCTL:-loginctl}"
SYSTEM_BUS="${OPENCLAW_BOOT_SYSTEM_BUS:-/run/dbus/system_bus_socket}"
TARGET_USER="${OPENCLAW_BOOT_USER:-${USER:-openclaw}}"

drift=0
unknown=0

report() {
  local scope="$1"
  local unit="$2"
  local state="$3"
  local verdict="$4"
  local suggestion="${5:--}"
  printf '%-12s %-48s %-18s %-8s %s\n' "$scope" "$unit" "$state" "$verdict" "$suggestion"
}

printf '%-12s %-48s %-18s %-8s %s\n' SCOPE UNIT STATE VERDICT SUGGESTION

if [[ ! -e "$SYSTEM_BUS" ]]; then
  report system-dbus "$SYSTEM_BUS" BUS_UNAVAILABLE UNKNOWN "Run wsl --shutdown from PowerShell once, then reopen Ubuntu-E."
  printf 'SUMMARY drift=0 unknown=1\n'
  exit 2
fi

linger_state="$($LOGINCTL show-user "$TARGET_USER" -p Linger --value 2>/dev/null)"
linger_rc=$?
if (( linger_rc != 0 )); then
  report user linger QUERY_FAILED UNKNOWN "loginctl show-user ${TARGET_USER} -p Linger"
  unknown=$((unknown + 1))
elif [[ "$linger_state" == yes ]]; then
  report user linger yes OK
else
  report user linger "${linger_state:-no}" DRIFT "sudo loginctl enable-linger ${TARGET_USER}"
  drift=$((drift + 1))
fi

check_unit() {
  local scope="$1"
  local unit="$2"
  local user_flag="$3"
  local state
  local rc
  local suggestion

  if [[ "$user_flag" == user ]]; then
    state="$($SYSTEMCTL --user is-enabled "$unit" 2>/dev/null)"
    rc=$?
    suggestion="systemctl --user enable ${unit}"
  else
    state="$($SYSTEMCTL is-enabled "$unit" 2>/dev/null)"
    rc=$?
    suggestion="sudo systemctl enable ${unit}"
  fi

  if (( rc == 0 )) && [[ "$state" == enabled || "$state" == linked || "$state" == linked-runtime ]]; then
    report "$scope" "$unit" "$state" OK
  elif [[ "$state" == disabled || "$state" == masked || "$state" == not-found ]]; then
    report "$scope" "$unit" "${state:-disabled}" DRIFT "$suggestion"
    drift=$((drift + 1))
  else
    report "$scope" "$unit" "${state:-QUERY_FAILED}" UNKNOWN "systemctl ${user_flag/user/--user} is-enabled ${unit}"
    unknown=$((unknown + 1))
  fi
}

for unit in "${OPENCLAW_ENABLEMENT_USER_UNITS[@]}"; do
  if [[ "$unit" == *.timer ]]; then
    check_unit user-timer "$unit" user
  else
    check_unit user-unit "$unit" user
  fi
done
check_unit system-service ollama.service system

printf 'SUMMARY drift=%d unknown=%d\n' "$drift" "$unknown"
if (( unknown > 0 )); then
  exit 2
fi
if (( drift > 0 )); then
  exit 1
fi
exit 0
