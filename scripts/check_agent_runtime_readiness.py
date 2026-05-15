#!/usr/bin/env python3
"""Build and print Agent Runtime Readiness v0."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_runtime_readiness import (
    build_agent_runtime_readiness,
    build_agent_runtime_readiness_report,
    format_agent_runtime_readiness_report,
    stable_json,
)
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check OpenClaw Agent Runtime Readiness v0.")
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
    result = build_agent_runtime_readiness(db_path=args.db, run_id=args.run_id)
    payload = build_agent_runtime_readiness_report(
        db_path=args.db,
        run_id=result.run_id,
        report="summary",
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_agent_runtime_readiness_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
