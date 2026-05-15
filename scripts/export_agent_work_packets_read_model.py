#!/usr/bin/env python3
"""Export Agent Work Packet generated read-model files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_work_packet import export_agent_work_packets_read_model, stable_json
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Agent Work Packet read-model.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--export-root", default="generated/read_models", help="Read-model export root.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_agent_work_packets_read_model(db_path=args.db, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print("Agent Work Packets Read-Model Export v0")
        print("")
        print(f"JSON: `{summary['json_path']}`")
        print(f"Operator: `{summary['operator_path']}`")
        print(f"Packets: {summary['packet_count']}")
        print("")
        print("Boundary:")
        print("- Export writes generated read-model files only; packets remain planning-only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
