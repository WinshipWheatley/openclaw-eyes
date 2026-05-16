#!/usr/bin/env python3
"""Export Cassandra/Clara review-only fact packet read-models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from cassandra_clara_fact_packet import (
    DEFAULT_ARTIFACT_ROOT,
    export_cassandra_clara_fact_packet,
    format_cassandra_clara_fact_packet,
    build_cassandra_clara_fact_packet,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the Cassandra/Clara review-only fact packet."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument(
        "--artifact-root",
        default=str(DEFAULT_ARTIFACT_ROOT),
        help="Generated review artifact folder.",
    )
    parser.add_argument(
        "--export-root",
        default="generated/read_models",
        help="Generated read-model export root.",
    )
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_cassandra_clara_fact_packet(
        db_path=args.db,
        artifact_root=args.artifact_root,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        payload = build_cassandra_clara_fact_packet(
            db_path=args.db,
            artifact_root=args.artifact_root,
        )
        print(format_cassandra_clara_fact_packet(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
