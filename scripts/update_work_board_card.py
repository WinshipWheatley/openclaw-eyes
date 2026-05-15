#!/usr/bin/env python3
"""Safely update OpenClaw Work Board v0 card metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from work_board import BOARD_COLUMNS, format_update_result, stable_json, update_work_board_card


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update OpenClaw Work Board card metadata.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--card-id", required=True, help="Card id to update.")
    parser.add_argument("--column", choices=tuple(sorted(BOARD_COLUMNS)), help="Target board column.")
    parser.add_argument("--status", help="Optional status label.")
    parser.add_argument("--blocker", help="Add blocker note and move to blocked.")
    parser.add_argument("--changed-by", default="operator", help="Actor label.")
    parser.add_argument("--change-reason", default="metadata_only_update", help="Metadata-only change reason.")
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Allow explicit metadata-only transitions where supported; never executes or approves.",
    )
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = update_work_board_card(
        db_path=args.db,
        card_id=args.card_id,
        board_column=args.column,
        status=args.status,
        blocker_reason=args.blocker,
        changed_by=args.changed_by,
        change_reason=args.change_reason,
        metadata_only=args.metadata_only,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_update_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
