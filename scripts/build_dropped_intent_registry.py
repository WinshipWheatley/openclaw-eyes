#!/usr/bin/env python3
"""Build Dropped Intent Registry v0 rows from safe OpenClaw surfaces."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from dropped_intent_registry import (
    build_dropped_intent_registry,
    export_dropped_intents_read_model,
    format_build_result,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build OpenClaw Dropped Intent Registry v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--repo-root", default=str(ROOT), help="OpenClaw repo root.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument(
        "--export-root",
        default="generated/read_models",
        help="Read-model export root.",
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
    result = build_dropped_intent_registry(
        db_path=args.db,
        repo_root=args.repo_root,
        run_id=args.run_id,
    )
    export = export_dropped_intents_read_model(db_path=args.db, export_root=args.export_root)
    payload = {
        "run_id": result.run_id,
        "db_path": result.db_path,
        "source_count": result.source_count,
        "total_count": result.total_count,
        "counts_by_status": result.counts_by_status,
        "export": export,
    }
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_build_result(result))
        print("")
        print("Generated read-models:")
        print(f"- JSON: `{export['json_path']}`")
        print(f"- Operator: `{export['operator_path']}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
