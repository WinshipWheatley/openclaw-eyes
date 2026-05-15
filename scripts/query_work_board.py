#!/usr/bin/env python3
"""Query OpenClaw Work Board v0 cards."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from work_board import (
    BOARD_COLUMNS,
    DEFAULT_BOARD_ID,
    REPORT_SECTIONS,
    build_work_board_report,
    format_work_board_report,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query OpenClaw Work Board v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--board-id", default=DEFAULT_BOARD_ID, help="Board id.")
    parser.add_argument("--report", choices=tuple(sorted(REPORT_SECTIONS)), default="summary")
    parser.add_argument("--agent", help="Optional agent filter.")
    parser.add_argument("--world", help="Optional world filter.")
    parser.add_argument("--column", choices=tuple(sorted(BOARD_COLUMNS)), help="Optional column filter.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_work_board_report(
        db_path=args.db,
        board_id=args.board_id,
        report=args.report,
        agent=args.agent,
        world=args.world,
        column=args.column,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_work_board_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
