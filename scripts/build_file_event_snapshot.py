#!/usr/bin/env python3
"""Build a bounded File Event Queue v0 snapshot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from file_event_queue import (
    build_file_event_report,
    build_file_event_snapshot,
    format_file_event_report,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a poll/snapshot File Event Queue v0 run for an allowlisted root."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--root", required=True, help="Allowlisted root to snapshot.")
    parser.add_argument("--root-id", help="Optional root id override.")
    parser.add_argument("--run-id", help="Optional run id.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_file_event_snapshot(
        db_path=args.db,
        root=args.root,
        root_id=args.root_id,
        run_id=args.run_id,
    )
    payload = build_file_event_report(
        db_path=args.db,
        run_id=result.run_id,
        section="summary",
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_file_event_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

