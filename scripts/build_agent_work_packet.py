#!/usr/bin/env python3
"""Build Agent Work Packet v0 planning packets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_work_packet import (
    build_agent_work_packet,
    build_sample_markdown_reorg_packet,
    format_packet_result,
    stable_json,
)
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Agent Work Packet v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--intent-id", help="Source intent id. Defaults to latest intent.")
    parser.add_argument("--packet-id", help="Optional deterministic packet id.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument("--sample-markdown-reorg", action="store_true", help="Build the sample Chief Markdown packet.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.sample_markdown_reorg:
        result = build_sample_markdown_reorg_packet(db_path=args.db)
    else:
        result = build_agent_work_packet(
            db_path=args.db,
            intent_id=args.intent_id,
            packet_id=args.packet_id,
            run_id=args.run_id,
        )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_packet_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
