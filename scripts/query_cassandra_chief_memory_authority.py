#!/usr/bin/env python3
"""Query Cassandra/Chief Memory Authority metadata-only read-models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from cassandra_chief_memory_authority import (
    build_cassandra_chief_memory_authority_read_model,
    build_cassandra_chief_memory_dry_run,
    format_cassandra_chief_memory_authority_read_model,
    format_cassandra_chief_memory_dry_run,
    format_cassandra_chief_memory_operator_review,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query Cassandra/Chief Memory Authority metadata-only posture."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument(
        "--report",
        choices=("summary", "dry-run", "review"),
        default="summary",
        help="Report section.",
    )
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.report == "dry-run":
        payload = build_cassandra_chief_memory_dry_run(db_path=args.db)
        operator_text = format_cassandra_chief_memory_dry_run(payload)
    elif args.report == "review":
        payload = build_cassandra_chief_memory_dry_run(db_path=args.db)
        operator_text = format_cassandra_chief_memory_operator_review(payload)
    else:
        payload = build_cassandra_chief_memory_authority_read_model(db_path=args.db)
        operator_text = format_cassandra_chief_memory_authority_read_model(payload)

    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(operator_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
