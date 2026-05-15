#!/usr/bin/env python3
"""Query OpenClaw Steel Thread Frontier Radar v0."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from steel_thread_radar import (
    PATTERN_CATEGORIES,
    REPORT_SECTIONS,
    build_steel_thread_report,
    format_steel_thread_report,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query OpenClaw Steel Thread Frontier Radar v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--report", choices=tuple(sorted(REPORT_SECTIONS - {"category"})), default="summary")
    parser.add_argument("--category", choices=tuple(sorted(PATTERN_CATEGORIES)), help="Filter by pattern category.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    report = "category" if args.category else args.report
    payload = build_steel_thread_report(db_path=args.db, report=report, category=args.category)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_steel_thread_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

