#!/usr/bin/env python3
"""Request a local operator clearance for one bounded agent recovery action."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_presence import format_agent_recovery_clearance_result, request_agent_recovery_clearance, stable_json
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Request Cassandra recovery clearance without executing recovery.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--agent", choices=("cassandra",), required=True)
    parser.add_argument("--requested-by", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--ttl-minutes", type=int, default=30)
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = request_agent_recovery_clearance(
        agent_id=args.agent,
        requested_by=args.requested_by,
        reason=args.reason,
        db_path=args.db,
        ttl_minutes=args.ttl_minutes,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_agent_recovery_clearance_result(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
