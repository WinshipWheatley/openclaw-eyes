#!/usr/bin/env python3
"""Query Sync Health reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from sync_health import build_sync_health_report, format_sync_health_report, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Sync Health reports.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--report", choices=("summary", "proof"), default="summary")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_sync_health_report(db_path=args.db, report=args.report)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_sync_health_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
