#!/usr/bin/env python3
"""Create Project Capsule v0 rows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from project_capsule import (
    build_project_capsule_report,
    create_demo_project_capsule,
    format_project_capsule_report,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create bounded Project Capsule v0 rows.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional run id.")
    parser.add_argument("--demo", action="store_true", help="Create the synthetic demo capsule.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.demo:
        raise SystemExit("--demo is required in Project Capsule v0")
    result = create_demo_project_capsule(db_path=args.db, run_id=args.run_id)
    report = build_project_capsule_report(db_path=args.db, run_id=result.run_id)
    if args.format == "json":
        print(stable_json(report), end="")
    else:
        print(format_project_capsule_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
