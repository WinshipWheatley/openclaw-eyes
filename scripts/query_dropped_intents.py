#!/usr/bin/env python3
"""Query/report Dropped Intent Registry v0 rows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from dropped_intent_registry import (
    REPORT_SECTIONS,
    build_dropped_intent_report,
    format_dropped_intent_report,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query OpenClaw Dropped Intent Registry v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument(
        "--report",
        choices=tuple(sorted(REPORT_SECTIONS)),
        default="summary",
        help="Report to emit.",
    )
    parser.add_argument("--agent", help="Optional agent/lane owner filter.")
    parser.add_argument("--world", help="Optional world filter.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum rows to show.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_dropped_intent_report(
        db_path=args.db,
        report=args.report,
        agent=args.agent,
        world=args.world,
        limit=args.limit,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_dropped_intent_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
