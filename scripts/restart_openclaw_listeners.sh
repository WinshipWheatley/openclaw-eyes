#!/usr/bin/env bash
# Task 149 (deploy hygiene, class-level fix): restart EVERY *-listener + gateway +
# processor systemd --user unit.
#
# Root cause: niles-listener.service ran a stale pre-fix binary through a deploy whose
# hand-maintained restart list simply omitted it, so the task-141 refusal tap was never
# actually loaded into the running process. A hand-maintained list silently drifts as new
# listeners get added over time. This script discovers the target unit set dynamically
# from the live systemd --user unit list instead of hardcoding names, so a newly-added
# *-listener.service is restarted automatically without anyone remembering to add it here.
#
# This is an OPERATIONAL deploy step -- run it explicitly as part of a deploy, never as
# part of an automated test suite (tests must not restart real services).
set -euo pipefail

mapfile -t UNITS < <(
  systemctl --user list-units --type=service --all --plain --no-legend 2>/dev/null \
    | awk '{print $1}' \
    | grep -E '(-listener\.service$|gateway\.service$|^openclaw-request-response\.service$)'
)

if [ "${#UNITS[@]}" -eq 0 ]; then
  echo "restart_openclaw_listeners: no matching units found -- refusing to proceed silently" >&2
  exit 1
fi

echo "restart_openclaw_listeners: restarting ${#UNITS[@]} unit(s):"
printf '  %s\n' "${UNITS[@]}"

for unit in "${UNITS[@]}"; do
  systemctl --user restart "$unit"
done

echo "restart_openclaw_listeners: done."
