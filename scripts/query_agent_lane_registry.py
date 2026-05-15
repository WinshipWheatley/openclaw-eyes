#!/usr/bin/env python3
"""Query Agent Lane Registry v0 rows from the Business Ops ledger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_lane_registry import build_agent_lane_report, format_agent_lane_report, stable_json
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query OpenClaw Agent Lane Registry v0 rows.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Run id. Defaults to latest.")
    parser.add_argument("--agent", help="Agent id or alias to inspect.")
    parser.add_argument(
        "--report",
        choices=("summary", "agents", "world", "source-kind", "approval-required"),
        default="summary",
        help="Report section.",
    )
    parser.add_argument("--world", help="World binding for --report world.")
    parser.add_argument("--source-kind", help="Source kind for --report source-kind.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_agent_lane_report(
        db_path=args.db,
        run_id=args.run_id,
        report=args.report,
        agent_id=args.agent,
        world=args.world,
        source_kind=args.source_kind,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_agent_lane_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
