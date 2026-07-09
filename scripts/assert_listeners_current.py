#!/usr/bin/env python3
"""Task 149 (deploy hygiene, class-level fix): post-deploy assertion that every
*-listener + gateway + processor systemd --user unit is CURRENT -- its
ActiveEnterTimestamp is at or after the deploy timestamp.

A unit reported "active" by systemctl can still be running STALE code if it was never
actually bounced during the deploy (exactly how niles-listener.service ran a Jun-30
binary through a deploy that should have restarted it). "active" alone does not prove
"current" -- ActiveEnterTimestamp does.

Usage:
    python3 scripts/assert_listeners_current.py --deploy-timestamp 2026-07-09T12:00:00

Exit code 0 = every discovered unit is current. Exit code 1 = at least one is stale
(names printed to stderr).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from typing import Callable, Iterable, Optional


_UNIT_SUFFIXES = ("-listener.service", "gateway.service")
_UNIT_EXACT = ("openclaw-request-response.service",)


def _is_target_unit(name: str) -> bool:
    return name.endswith(_UNIT_SUFFIXES) or name in _UNIT_EXACT


def discover_target_units() -> list[str]:
    """Enumerate the live systemd --user unit set and filter to the deploy-relevant
    targets. Real subprocess call -- not used in unit tests (those inject unit lists
    directly)."""
    out = subprocess.run(
        ["systemctl", "--user", "list-units", "--type=service", "--all", "--plain", "--no-legend"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    units = []
    for line in out.splitlines():
        parts = line.split()
        if parts and _is_target_unit(parts[0]):
            units.append(parts[0])
    return units


def _parse_systemd_timestamp(raw: str) -> Optional[datetime]:
    """Parse systemd's ActiveEnterTimestamp format, e.g. "Wed 2026-07-09 11:50:23 EDT".
    Returns None for the "n/a" (never started) sentinel or an unparseable value."""
    raw = raw.strip()
    if not raw or raw == "n/a":
        return None
    parts = raw.split()
    if len(parts) < 3:
        return None
    try:
        return datetime.strptime(f"{parts[1]} {parts[2]}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def fetch_active_enter_timestamp(unit: str) -> Optional[datetime]:
    """Real subprocess call -- not used in unit tests (those inject a lookup function)."""
    out = subprocess.run(
        ["systemctl", "--user", "show", unit, "--property=ActiveEnterTimestamp", "--value"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return _parse_systemd_timestamp(out)


def find_stale_units(
    deploy_timestamp: datetime,
    units: Iterable[str],
    *,
    timestamp_lookup: Callable[[str], Optional[datetime]] = fetch_active_enter_timestamp,
) -> list[str]:
    """Pure(ish) core: given a deploy timestamp and a unit list, return the names of any
    units whose ActiveEnterTimestamp is missing or older than the deploy -- i.e. units
    that were NOT actually restarted as part of this deploy. timestamp_lookup is
    injectable so tests never call the real systemctl."""
    stale = []
    for unit in units:
        enter_ts = timestamp_lookup(unit)
        if enter_ts is None or enter_ts < deploy_timestamp:
            stale.append(unit)
    return stale


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--deploy-timestamp",
        required=True,
        help="ISO timestamp marking when this deploy began, e.g. 2026-07-09T12:00:00",
    )
    args = parser.parse_args(argv)
    deploy_ts = datetime.fromisoformat(args.deploy_timestamp)

    units = discover_target_units()
    if not units:
        print("assert_listeners_current: no matching units found -- refusing to pass silently", file=sys.stderr)
        return 1

    stale = find_stale_units(deploy_ts, units)
    if stale:
        print("STALE (not restarted as part of this deploy):", file=sys.stderr)
        for unit in stale:
            print(f"  {unit}", file=sys.stderr)
        return 1

    print(f"All {len(units)} listener/gateway/processor unit(s) are current as of this deploy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
