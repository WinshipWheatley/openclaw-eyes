#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: start_chief.sh [--dry-run]

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
Slice 4 legacy launcher refusal: start_chief.sh
No live service, process, private environment, or log action was requested or taken.

Refused historical behavior:
  - private environment loading and credential-dependent startup
  - log directory creation and runner registry refresh
  - process termination of systemd-owned listeners/workers
  - unmanaged duplicate listener/worker startup
  - guardian listener and loop supervisor startup

Reason: this launcher overlaps systemd-owned services/listeners/workers and
private runtime surfaces frozen by docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md.
Its live/manual future, if any, belongs to a later explicit ownership decision.
REPORT
}

if (( dry_run )); then
    report_refusal
    exit 0
fi

printf 'ERROR: no live execution mode is available for start_chief.sh in Slice 4.\n' >&2
usage >&2
exit 2
