#!/usr/bin/env python3
"""Export Dropped Intent Registry v0 generated read-model files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from dropped_intent_registry import export_dropped_intents_read_model, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw Dropped Intent Registry read-model.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
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
    summary = export_dropped_intents_read_model(db_path=args.db, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print("Dropped Intent Registry Read-Model Export v0")
        print("")
        print(f"JSON: `{summary['json_path']}`")
        print(f"Operator: `{summary['operator_path']}`")
        print(f"Total: {summary['total_count']}")
        print(f"Unresolved: {summary['unresolved_count']}")
        print(f"Deferred: {summary['deferred_count']}")
        print(f"Built: {summary['built_count']}")
        print(f"Unknown review: {summary['unknown_review_count']}")
        print("")
        print("Boundary:")
        print("- Export reads `dropped_intent_*` rows and writes generated read-model files only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
