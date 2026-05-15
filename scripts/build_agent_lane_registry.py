#!/usr/bin/env python3
"""Build Agent Lane Registry v0 rows and generated read-model exports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_lane_registry import (
    build_agent_lane_report,
    export_agent_lanes_read_model,
    format_agent_lane_report,
    seed_agent_lane_registry,
    stable_json,
)
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build OpenClaw Agent Lane Registry v0 rows.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument(
        "--export-root",
        default="generated/read_models",
        help="Read-model export root. Defaults to generated/read_models.",
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
    result = seed_agent_lane_registry(db_path=args.db, run_id=args.run_id)
    export_summary = export_agent_lanes_read_model(
        db_path=args.db,
        export_root=args.export_root,
        run_id=result.run_id,
    )
    report = build_agent_lane_report(db_path=args.db, run_id=result.run_id, report="summary")
    report["export"] = export_summary
    if args.format == "json":
        print(stable_json(report), end="")
    else:
        print(format_agent_lane_report(report))
        print("")
        print(f"Read-model JSON: `{export_summary['json_path']}`")
        print(f"Read-model operator: `{export_summary['operator_path']}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
