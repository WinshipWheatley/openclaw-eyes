#!/usr/bin/env python3
"""Build/seed OpenClaw Local Automation Services v0 registry rows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from local_automation_registry import (
    format_local_automation_report,
    seed_local_automation_registry,
    stable_json,
    build_local_automation_report,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Local Automation Services v0 registry.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--run-id")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = seed_local_automation_registry(db_path=args.db, run_id=args.run_id)
    payload = build_local_automation_report(db_path=args.db, report="summary")
    payload["run_id"] = result.run_id
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_local_automation_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
