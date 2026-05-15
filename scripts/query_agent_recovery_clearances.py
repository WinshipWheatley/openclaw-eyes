#!/usr/bin/env python3
"""Query local agent recovery clearances without starting anything."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_presence import build_agent_recovery_clearance_report, format_agent_recovery_clearance_report, stable_json
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query explicit local recovery clearances.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--agent", choices=("cassandra",))
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_agent_recovery_clearance_report(db_path=args.db, agent=args.agent)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_agent_recovery_clearance_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
