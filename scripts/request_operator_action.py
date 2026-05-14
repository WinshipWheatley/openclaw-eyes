#!/usr/bin/env python3
"""Create an Operator Action Path v0 request."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from operator_action import format_request_result, request_operator_action, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Request a helm-gated operator action.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--action-id", help="Optional deterministic action id.")
    parser.add_argument("--action-type", required=True, help="Allowlisted action type.")
    parser.add_argument("--requested-by", required=True, help="Requester identity.")
    parser.add_argument("--reason", required=True, help="Reason shown to the operator.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = request_operator_action(
        action_type=args.action_type,
        requested_by=args.requested_by,
        reason=args.reason,
        action_id=args.action_id,
        db_path=args.db,
    )
    payload = result.__dict__
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_request_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
