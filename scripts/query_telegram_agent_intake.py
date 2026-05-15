#!/usr/bin/env python3
"""Query Telegram Agent Intake readiness and storage records."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from telegram_agent_intake import REPORT_SECTIONS, build_telegram_agent_intake_report, format_telegram_agent_intake_report, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Telegram Agent Intake v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--report", choices=tuple(sorted(REPORT_SECTIONS)), default="summary")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_telegram_agent_intake_report(db_path=args.db, report=args.report)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_telegram_agent_intake_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
