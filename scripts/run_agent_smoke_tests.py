#!/usr/bin/env python3
"""Run deterministic Agent Runtime smoke tests without activating agents."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_runtime_readiness import (
    build_agent_runtime_readiness_report,
    format_agent_runtime_readiness_report,
    run_agent_smoke_tests,
    stable_json,
)
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OpenClaw Agent Runtime smoke tests.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional run id.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = run_agent_smoke_tests(db_path=args.db, run_id=args.run_id)
    payload = build_agent_runtime_readiness_report(
        db_path=args.db,
        run_id=result.run_id,
        report="smoke-tests",
    )
    if args.format == "json":
        print(stable_json({"result": result.__dict__, "report": payload}), end="")
    else:
        print("Agent Runtime Smoke Tests v0")
        print("")
        print(f"Run: `{result.run_id}`")
        print(f"Smoke tests: {result.smoke_test_count}")
        print(f"Passed: {result.passed_count}")
        print(f"Failed: {result.failed_count}")
        print(f"No execution occurred: {result.no_execution_occurred}")
        print("")
        print(format_agent_runtime_readiness_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
