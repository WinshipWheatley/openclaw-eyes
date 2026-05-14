#!/usr/bin/env python3
"""Query Context Selection / Knowledge Packet v0 rows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from context_selection import (
    build_context_selection_report,
    format_context_selection_report,
    format_context_selection_section,
    query_context_selection_report_section,
    stable_json,
)


REPORT_SECTIONS = ("summary", "items", "sources", "exclusions", "receipts")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query context selection packet reports.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Context selection run id. Defaults to latest.")
    parser.add_argument("--packet-id", help="Context packet id. Defaults to latest for run.")
    parser.add_argument(
        "--report",
        choices=REPORT_SECTIONS,
        default="summary",
        help="Report section to emit.",
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
    if args.report == "summary":
        payload = build_context_selection_report(db_path=args.db, run_id=args.run_id)
    else:
        payload = query_context_selection_report_section(
            db_path=args.db,
            run_id=args.run_id,
            packet_id=args.packet_id,
            section=args.report,
        )
    if args.format == "json":
        print(stable_json(payload), end="")
    elif args.report == "summary":
        print(format_context_selection_report(payload))
    else:
        print(format_context_selection_section(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
