#!/usr/bin/env python3
"""Export Cassandra/Chief Memory Authority read-models."""

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
    export_cassandra_chief_memory_authority_read_model,
    format_cassandra_chief_memory_authority_read_model,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Cassandra/Chief Memory Authority metadata-only read-models."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--export-root", default="generated/read_models", help="Read-model export root.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_cassandra_chief_memory_authority_read_model(
        db_path=args.db,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        read_model = build_cassandra_chief_memory_authority_read_model(db_path=args.db)
        print(format_cassandra_chief_memory_authority_read_model(read_model), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
