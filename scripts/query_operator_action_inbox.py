#!/usr/bin/env python3
"""Query Operator Action Inbox v0 import provenance."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from operator_action_inbox import (
    build_operator_action_inbox_report,
    format_operator_action_inbox_report,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query operator action inbox imports.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--import-run-id", help="Optional import run filter.")
    parser.add_argument(
        "--report",
        choices=("summary", "imports", "rejections"),
        default="summary",
        help="Report section.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_operator_action_inbox_report(
        db_path=args.db,
        report=args.report,
        import_run_id=args.import_run_id,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_operator_action_inbox_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
