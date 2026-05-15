#!/usr/bin/env python3
"""Export Agent Runtime Readiness v0 generated read-model files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_runtime_readiness import export_agent_runtime_readiness_read_model, stable_json
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw Agent Runtime Readiness read-model.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument(
        "--export-root",
        default="generated/read_models",
        help="Read-model export root.",
    )
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
    summary = export_agent_runtime_readiness_read_model(
        db_path=args.db,
        export_root=args.export_root,
        run_id=args.run_id,
    )
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print("Agent Runtime Readiness Read-Model Export v0")
        print("")
        print(f"JSON: `{summary['json_path']}`")
        print(f"Operator: `{summary['operator_path']}`")
        print(f"Agents: {summary['agent_count']}")
        print(f"Ready for dry run: {summary['ready_for_dry_run_count']}")
        print(f"Partial: {summary['partial_count']}")
        print(f"Blocked: {summary['blocked_count']}")
        print(f"Smoke tests: passed={summary['smoke_passed']}, failed={summary['smoke_failed']}")
        print("")
        print("Boundary:")
        print("- Export reads `agent_runtime_*` rows and writes generated read-model files only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
