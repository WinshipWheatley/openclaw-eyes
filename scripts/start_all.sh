#!/usr/bin/env bash
set -euo pipefail

usage() {
	cat <<'USAGE'
Usage: scripts/start_all.sh [--dry-run]

Slice 4 contract:
  no args     Report the refused legacy full-stack launch. No live action occurs.
  --dry-run   Report the refused legacy full-stack launch. No live action occurs.
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
Slice 4 legacy launcher refusal: scripts/start_all.sh
No live service or process action was requested or taken.

Refused historical behavior:
  - broad restart of openclaw-stack.target
  - delegated legacy poller launch through start_openclaw_brains.sh
  - live process inspection for chief/cassandra workers

Reason: this launcher overlaps systemd-owned services and legacy/manual
pollers frozen by docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md.
Its live/manual future, if any, belongs to a later explicit ownership decision.
REPORT
}

if (( dry_run )); then
	report_refusal
	exit 0
fi

printf 'ERROR: no live execution mode is available for scripts/start_all.sh in Slice 4.\n' >&2
usage >&2
exit 2
