#!/usr/bin/env python3
"""Build OpenClaw Work Board v0 cards."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from work_board import DEFAULT_BOARD_ID, build_work_board, format_build_result, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build OpenClaw Work Board v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--board-id", default=DEFAULT_BOARD_ID, help="Board id.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_work_board(db_path=args.db, board_id=args.board_id, run_id=args.run_id)
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_build_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
