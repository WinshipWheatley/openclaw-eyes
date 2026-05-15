#!/usr/bin/env python3
"""Run the Agent Runtime start sequence as a safe dry run."""

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
    run_agent_start_sequence,
    stable_json,
)
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OpenClaw Agent Runtime start sequence.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional run id.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run only. This is the default and only v0 mode.",
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
    result = run_agent_start_sequence(
        db_path=args.db,
        dry_run=True,
        run_id=args.run_id,
    )
    payload = build_agent_runtime_readiness_report(
        db_path=args.db,
        run_id=result.run_id,
        report="start-sequence",
    )
    if args.format == "json":
        print(stable_json({"result": result.__dict__, "report": payload}), end="")
    else:
        print("Agent Runtime Start Sequence v0")
        print("")
        print(f"Run: `{result.run_id}`")
        print(f"Dry run: {result.dry_run}")
        print(f"Overall status: `{result.overall_status}`")
        print(f"Steps: pass={result.pass_count}, warn={result.warn_count}, block={result.block_count}")
        print(f"Next safe move: {result.next_safe_move}")
        print("")
        print(format_agent_runtime_readiness_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
