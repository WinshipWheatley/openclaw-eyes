#!/usr/bin/env python3
"""Build Recent File Context v0 candidates from File Event Queue metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from recent_file_context import (
    build_recent_file_context,
    build_recent_file_context_report,
    format_recent_file_context_report,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Recent File Context v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum source file events.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_recent_file_context(db_path=args.db, run_id=args.run_id, limit=args.limit)
    payload = build_recent_file_context_report(db_path=args.db, report="summary", run_id=result.run_id)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_recent_file_context_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
