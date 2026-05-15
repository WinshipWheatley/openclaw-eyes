#!/usr/bin/env python3
"""Query OpenClaw Local Automation Services v0 registry rows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from local_automation_registry import (
    build_local_automation_report,
    format_local_automation_report,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Local Automation Services v0 registry.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--task-id")
    parser.add_argument("--report", choices=("summary", "tasks", "services", "status"), default="summary")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_local_automation_report(db_path=args.db, report=args.report, task_id=args.task_id)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_local_automation_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
