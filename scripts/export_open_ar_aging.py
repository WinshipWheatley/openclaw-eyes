#!/usr/bin/env python3
"""Export the open AR aging read model (read-only; no sends, no ledger writes)."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import open_ar_aging


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the open AR aging read model.")
    parser.add_argument("--money-source", default=str(open_ar_aging.DEFAULT_MONEY_SOURCE_PATH))
    parser.add_argument("--terms", default=str(open_ar_aging.DEFAULT_TERMS_PATH))
    parser.add_argument("--today", default=None, help="ISO date override (tests).")
    parser.add_argument("--export-root", default=str(open_ar_aging.DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    today = date.fromisoformat(args.today) if args.today else None
    summary = open_ar_aging.export_open_ar_aging(
        money_source_path=args.money_source, terms_path=args.terms, export_root=args.export_root, today=today
    )
    if args.format == "json":
        print(open_ar_aging.stable_json(summary), end="")
    else:
        print("Open AR Aging Export v0")
        print("")
        print(f"JSON: `{summary['json_path']}`")
        print(f"Operator: `{summary['operator_path']}`")
        print(f"Open rows: `{summary['open_row_count']}`  Oldest: `{summary['oldest_days_past_due']}` days past due")
        print("")
        print("Boundary: read-only; no sends, no ledger writes, no amounts beyond the money source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
