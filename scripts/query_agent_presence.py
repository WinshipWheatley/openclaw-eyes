#!/usr/bin/env python3
"""Query Agent Presence v0 reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_presence import build_agent_presence_report, format_agent_presence_report, stable_json
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query OpenClaw agent presence.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--report", choices=("summary", "offline", "expected-online", "recovery-available"), default="summary")
    parser.add_argument("--agent", choices=("chief", "cassandra", "guardian", "niles", "hermes", "report_bridge"))
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_agent_presence_report(db_path=args.db, report=args.report, agent=args.agent)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_agent_presence_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
