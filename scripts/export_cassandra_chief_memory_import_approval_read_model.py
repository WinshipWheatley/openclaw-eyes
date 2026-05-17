#!/usr/bin/env python3
"""Export Cassandra/Chief memory import approval receipt read-models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassandra_chief_memory_import_approval import (
    build_cassandra_chief_memory_import_approval,
    export_cassandra_chief_memory_import_approval,
    format_cassandra_chief_memory_import_approval,
)
from cassandra_chief_memory_authority import stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Cassandra/Chief memory import approval receipt read-models."
    )
    parser.add_argument(
        "--export-root",
        default="generated/read_models",
        help="Read-model export root.",
    )
    parser.add_argument(
        "--structured-import-plan",
        default=None,
        help="Optional structured import plan JSON path.",
    )
    parser.add_argument(
        "--hitl-proof",
        default=None,
        help="Optional Guardian HITL Cassandra proposal shadow JSON path.",
    )
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_cassandra_chief_memory_import_approval(
        export_root=args.export_root,
        structured_import_plan_path=args.structured_import_plan,
        hitl_proof_path=args.hitl_proof,
    )
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        payload = build_cassandra_chief_memory_import_approval(
            structured_import_plan_path=args.structured_import_plan,
            hitl_proof_path=args.hitl_proof,
        )
        print(format_cassandra_chief_memory_import_approval(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
