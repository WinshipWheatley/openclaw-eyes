#!/usr/bin/env python3
"""Register Legacy GitHub Repo Intake v0 placeholder roots."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from legacy_repo_intake import (
    build_legacy_repo_intake_report,
    format_legacy_repo_intake_report,
    register_placeholder_legacy_repo,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register non-canonical legacy repo intake placeholders.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional run id.")
    parser.add_argument("--root-id", default="github_legacy_openclaw", help="Legacy root id.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = register_placeholder_legacy_repo(
        db_path=args.db,
        run_id=args.run_id,
        root_id=args.root_id,
    )
    report = build_legacy_repo_intake_report(db_path=args.db, run_id=result.run_id)
    if args.format == "json":
        print(stable_json(report), end="")
    else:
        print(format_legacy_repo_intake_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
