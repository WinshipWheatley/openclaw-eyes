#!/usr/bin/env python3
"""Build Module / Capability Registry v0 rows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from module_registry import (
    build_module_registry_report,
    format_module_registry_report,
    seed_module_registry,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build OpenClaw Module Registry v0 rows.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
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
    result = seed_module_registry(db_path=args.db, run_id=args.run_id)
    report = build_module_registry_report(db_path=args.db, run_id=result.run_id)
    if args.format == "json":
        print(stable_json(report), end="")
    else:
        print(format_module_registry_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
