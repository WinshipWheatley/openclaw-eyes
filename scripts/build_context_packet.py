#!/usr/bin/env python3
"""Build an evidence-grounded Context Selection / Knowledge Packet v0."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from context_selection import (
    DEFAULT_PACKET_ROOT,
    compile_context_packet,
    format_context_selection_report,
    build_context_selection_report,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile a deterministic evidence-grounded context packet."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--world", help="Optional world filter, such as build or music_art.")
    parser.add_argument("--category", help="Optional evidence category filter.")
    parser.add_argument("--task", help="Optional bounded task string.")
    parser.add_argument("--run-id", help="Optional deterministic context selection run id.")
    parser.add_argument("--limit", type=int, default=60, help="Maximum selected items.")
    parser.add_argument(
        "--output-root",
        default=DEFAULT_PACKET_ROOT.as_posix(),
        help="Generated context packet output root.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = compile_context_packet(
        db_path=args.db,
        world=args.world,
        category=args.category,
        task=args.task,
        run_id=args.run_id,
        limit=args.limit,
        output_root=args.output_root,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        report = build_context_selection_report(db_path=args.db, run_id=result.run_id)
        print(format_context_selection_report(report))
        print("")
        print(f"Generated JSON: `{result.json_path}`")
        print(f"Generated operator packet: `{result.operator_path}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
