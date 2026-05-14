#!/usr/bin/env python3
"""Approve an Operator Action Path v0 request."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from operator_action import approve_operator_action, format_approval_result, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Approve a helm-gated operator action.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--action-id", required=True, help="Operator action id.")
    parser.add_argument("--approved-by", required=True, help="Approver identity.")
    parser.add_argument("--approval-note", required=True, help="Explicit approval note.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = approve_operator_action(
        action_id=args.action_id,
        approved_by=args.approved_by,
        approval_note=args.approval_note,
        db_path=args.db,
    )
    payload = result.__dict__
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_approval_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
