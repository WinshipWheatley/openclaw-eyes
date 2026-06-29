#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: start_chief_logged.sh [--dry-run]

Slice 4 contract:
  no args     Report the refused legacy Chief stack launch. No live action occurs.
  --dry-run   Report the refused legacy Chief stack launch. No live action occurs.
  --help      Show this usage.

No live execution flags are available for this script in Slice 4. Any future
manual/live behavior belongs to a later explicit ownership decision.
USAGE
}

dry_run=0
if (($# == 0)); then
    dry_run=1
fi

while (($#)); do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'ERROR: unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

report_refusal() {
    cat <<'REPORT'
Slice 4 legacy launcher refusal: start_chief_logged.sh
No live service, process, private environment, or log action was requested or taken.

Refused historical behavior:
  - venv activation and credential-dependent startup
  - pkill of systemd-owned chief_listener/worker/memory_worker/state_worker
  - unmanaged duplicate (bare-python, nohup) listener/worker startup into listener.out
  - duplicate getUpdates poller creation that conflicts with the systemd-owned Chief bot

Reason: this launcher overlaps systemd-owned services/listeners/workers (chief-listener,
chief-worker, chief-memory-worker, chief-state-worker are all `enabled`; user lingering is on,
so systemd --user is the canonical auto-start). Running it pkills the managed processes and
relaunches unmanaged duplicates, producing a "terminated by other getUpdates request" conflict
on the Chief bot. Frozen by docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md.
Its live/manual future, if any, belongs to a later explicit ownership decision.
REPORT
}

if (( dry_run )); then
    report_refusal
    exit 0
fi

printf 'ERROR: no live execution mode is available for start_chief_logged.sh in Slice 4.\n' >&2
usage >&2
exit 2
