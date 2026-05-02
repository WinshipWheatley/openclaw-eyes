#!/usr/bin/env bash
set -euo pipefail

usage() {
	cat <<'USAGE'
Usage: start_openclaw_brains.sh [--dry-run]

Slice 4 contract:
  no args     Report the refused legacy poller launch. No live action occurs.
  --dry-run   Report the refused legacy poller launch. No live action occurs.
  --help      Show this usage.

No live poller execution flags are available for this script in Slice 4. Legacy
poller ownership is deferred to Slice 8.
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
Slice 4 legacy launcher refusal: start_openclaw_brains.sh
No live process action was requested or taken.

Refused historical behavior:
  - terminate chief_album_brain.py and chief_billing_brain.py
  - launch chief_album_brain.py and chief_billing_brain.py as detached pollers

Reason: these legacy/manual polling processes remain frozen until Slice 8 decides
their ownership and allowed control path.
REPORT
}

if (( dry_run )); then
	report_refusal
	exit 0
fi

printf 'ERROR: no live poller execution mode is available for start_openclaw_brains.sh in Slice 4.\n' >&2
usage >&2
exit 2
