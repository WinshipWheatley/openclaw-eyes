#!/usr/bin/env python3
"""Build Local Tool Inventory v0 into the existing Business Ops ledger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from tool_inventory import (
    DEFAULT_HOST_KIND,
    DEFAULT_ROOT,
    DEFAULT_ROOT_ID,
    build_tool_inventory_report,
    format_tool_inventory_report,
    run_tool_inventory,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record observed local tool metadata without installs or integration."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--root", default=DEFAULT_ROOT.as_posix(), help="Observed root path.")
    parser.add_argument("--root-id", default=DEFAULT_ROOT_ID, help="Root id.")
    parser.add_argument("--host-kind", default=DEFAULT_HOST_KIND, help="Host kind.")
    parser.add_argument("--run-id", help="Optional deterministic inventory run id.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = run_tool_inventory(
        db_path=args.db,
        root=args.root,
        root_id=args.root_id,
        host_kind=args.host_kind,
        run_id=args.run_id,
    )
    report = build_tool_inventory_report(db_path=args.db, run_id=result.run_id)
    if args.format == "json":
        print(stable_json(report), end="")
    else:
        print(format_tool_inventory_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
