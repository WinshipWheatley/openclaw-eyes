#!/usr/bin/env python3
"""Fetch/ingest approved Steel Thread source registry items."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from steel_thread_radar import fetch_steel_thread_sources, format_fetch_result, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch approved Steel Thread source items.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional deterministic feed run id.")
    parser.add_argument("--dry-run", action="store_true", help="Report enabled sources without writing feed items.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = fetch_steel_thread_sources(db_path=args.db, run_id=args.run_id, dry_run=args.dry_run)
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_fetch_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

