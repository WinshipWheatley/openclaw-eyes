#!/usr/bin/env python3
"""Approve one local Cassandra recovery clearance after explicit operator consent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_presence import approve_agent_recovery_clearance, format_agent_recovery_clearance_result, stable_json
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Approve Cassandra recovery clearance without executing recovery.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--clearance-id", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--approval-note", required=True)
    parser.add_argument("--confirm-agent", choices=("cassandra",), required=True)
    parser.add_argument("--confirm-action", choices=("cassandra_systemd_user_start",), required=True)
    parser.add_argument("--ttl-minutes", type=int, default=30)
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        payload = approve_agent_recovery_clearance(
            clearance_id=args.clearance_id,
            approved_by=args.approved_by,
            approval_note=args.approval_note,
            confirm_agent=args.confirm_agent,
            confirm_action=args.confirm_action,
            db_path=args.db,
            ttl_minutes=args.ttl_minutes,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_agent_recovery_clearance_result(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
