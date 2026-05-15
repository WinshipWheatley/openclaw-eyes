#!/usr/bin/env python3
"""Query Intent Router v0 rows from the Business Ops ledger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from intent_router import REPORT_SECTIONS, build_intent_router_report, format_intent_router_report, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query OpenClaw Intent Router v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument(
        "--report",
        choices=tuple(sorted(REPORT_SECTIONS)),
        default="summary",
        help="Report section.",
    )
    parser.add_argument("--agent", help="Agent id for by-agent report.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_intent_router_report(db_path=args.db, report=args.report, agent=args.agent)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_intent_router_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
